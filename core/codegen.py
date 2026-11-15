"""
Graph -> GLSL MAT shader generation.

Pure Python (no TouchDesigner imports) so it can be unit tested outside TD.

Snippet files (glsl/nodes/*.glsl) start with a header of `// @key value` lines:

    // @type  NoiseTexture
    // @category Texture         (the node's group in the MATX family's OP Create menu)
    // @in    vec3 vector = 0.0
    // @in    float scale = 5.0
    // @in    float angle = 0.0 [-180 180]   (optional slider range of the node's parameter)
    // @in    vec3 coord = uv    (a default naming an ATTRIBUTE reads it when unconnected)
    // @out   float fac
    // @out   vec3 result vector  (vector|color: what a vec3/vec4 carries when its name does not
                                   tell, see socket_kind; it only picks the socket's colour)
    // @attr  uv                 (vertex attribute the snippet reads, see ATTRIBUTES)
    // @requires hash            (helper file glsl/lib/hash.glsl, included once)
    // @sampler sampler2D image  (a texture per node instance, see SAMPLER_TYPES)
    // @uniform value            (an @in the node may bind to a uniform instead of a literal)
    // @uniform time = absTime.seconds   (an @in that is always a uniform, driven by an expression)
    // @menu  operation add subtract   (a constant chosen from a menu, the first item by default)
    // @attrib vec3 attribute = Tex texcoord   (a geometry attribute chosen by name, see below)
    // @enable c if operation multiply_add wrap   (when a parameter is in use, see below)
    // @differentiate height by filter_width if quality high   (see below)

The graph's `output` ([node_id, socket]) is the surface the shader renders. A closure output
supplies radiance and alpha; any other value is shaded as emission, converted to vec4 like any
link except that a float is opaque grey (float x -> vec4(vec3(x), 1.0), vec3 c -> vec4(c, 1.0)).

The body must define `void matx_<type>(<samplers...>, <menus...>, <attribs...>, <ins...>,
out <outs...>)` with parameters in the order the @sampler, @menu, @attrib, @in, then @out lines
appear (a menu is an `int`).

A menu is not a socket: the node carries `"menus": {name: item}` in the graph and the call passes
the item as a compile-time constant. Each menu item gets `const int MATX_<TYPE>_<MENU>_<ITEM>`
(upper case, numbered in header order) ahead of the snippet body, so the snippet can `switch` on
the parameter by name and the compiler folds the switch away.

A node with samplers carries `"samplers": {name: TOP path}` in the graph. Each one becomes a
`uniform sampler2D sMatx_<node>_<name>` in the pixel shader, and generate() returns the
(uniform, TOP path) pairs for the host to bind on the GLSL MAT's Samplers page.

A node can carry `"uniforms": {input: [op path, par name]}` for inputs its snippet declares with
@uniform. Each one becomes a `uniform <type> uMatx_<node>_<input>` in the pixel shader instead of
a literal, and generate() returns [uniform, op path, par name, page] rows for the host to bind
on the GLSL MAT, so the value can change without recompiling the shader. A colour input (see
is_color) goes on the MAT's Colors page, which feeds a vec4 uniform (a vec3 input reads its .rgb);
any other input goes on the Vectors page. `// @uniform <input> = <expression>` makes the input
always a uniform: the node's parameter runs the TouchDesigner expression (Time: absTime.seconds).

`// @attrib <type> <name> = <Default> [texcoord | typed]` reads a geometry attribute (a POP or SOP
attribute such as Tex, Color or a custom one) whose NAME is chosen on the node: the node carries
`"attribs": {name: [attribute name, type]}`. The vertex shader reads it with TDAttrib_<Name>()
and passes it to the pixel shader in the Vertex block (`attr_<Name>`), and generate() returns
[attribute name, MAT type] rows for the host to declare on the GLSL MAT's Attributes page, which
is what makes TDAttrib_<Name>() exist. The declared size must match the geometry's attribute, so
a `typed` attrib lets the node choose it (float..vec4; the value is converted to the snippet's
parameter type). A `texcoord` attrib (vec3) is read with TDTexAttrib_<Name>(0u), which is the POP
attribute for POPs and uv[0] for SOPs; `Tex` read that way is the built-in `uv` attribute.

`// @enable <name>... if|unless <menu> <item>...` tells the node which parameters a menu leaves
unused, the way Blender hides them: the parameters of the named @in, @menu or @attrib entries are
greyed out unless (`if`) or while (`unless`) the menu holds one of the items. Several @enable
lines on one parameter must all hold. It only drives the node's UI; the shader does not change.

`// @differentiate <input> [by <float input>] [if <menu> <item>...]` gives the snippet the input
as it is at the neighbouring pixels too, the way Blender's Bump gets its height: the function takes
two more parameters right after the input, `<input>_dx` and `<input>_dy`, holding the input as at
the pixel `by` pixels to the right and the one `by` pixels above (1.0 without `by`). The graph that
feeds the input is not differentiated: the nodes of it that read the geometry (the Vertex block,
directly, through an attribute default or an @attrib, or gl_FragCoord) are emitted twice more, with
every such read moved to the neighbouring pixel (iVert.x + by * dFdx(iVert.x)). So any texture
fed by any coordinate works, and nodes that do not depend on the pixel are not repeated. With
`if`, this happens only while the node's menu holds one of the items; otherwise, or when the input
does not depend on the pixel, `<input>_dx` and `<input>_dy` are the input itself. Within such a
repetition, a nested differentiated input keeps its values at this pixel.
"""
import re

CLOSURE = 'closure'
TYPES = ('float', 'vec2', 'vec3', 'vec4', CLOSURE)
GLSL_TYPE = {'float': 'float', 'vec2': 'vec2', 'vec3': 'vec3', 'vec4': 'vec4',
             CLOSURE: 'MatxClosure'}
COMPONENTS = {'float': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4}
SAMPLER_TYPES = ('sampler2D',)
# abstract type -> type menu value on the GLSL MAT's Attributes page
MAT_ATTRIB_TYPE = {'float': 'float', 'vec2': 'float2', 'vec3': 'float3', 'vec4': 'float4'}
ATTRIB_FLAVORS = ('texcoord', 'typed')
# a vec3/vec4 socket whose name contains one of these is a vector, otherwise a colour
SPATIAL_WORDS = ('vector', 'normal', 'pos', 'uv', 'coord', 'offset', 'dir', 'tangent', 'scale',
                 'location', 'rotation', 'axis', 'center')


class MatxError(Exception):
	pass


# name -> (glsl type, member of the Vertex interface block, vertex shader expression).
# Snippets read an attribute in the pixel shader as `iVert.<member>`. Members are emitted in
# this order and only for attributes the graph uses (SURFACE_ATTRS are always emitted: fog
# needs them). `worldSpacePos` and `normal` are locals of the vertex main().
# TDCameraIndex() only exists in the vertex stage, hence camera_index is a flat member.
ATTRIBUTES = {
	'color':        ('vec4',     'color',          'TDInstanceColor(TDColor())'),
	'world_pos':    ('vec3',     'worldSpacePos',  'worldSpacePos.xyz'),
	'world_normal': ('vec3',     'worldSpaceNorm', 'normalize(TDDeformNorm(normal))'),
	'object_pos':   ('vec3',     'objectPos',      'pos'),
	'object_normal': ('vec3',    'objectNorm',     'normal'),
	'uv':           ('vec3',     'uv',             'TDInstanceTexCoord(TDTexAttrib_Tex(0u))'),
	'camera_index': ('flat int', 'cameraIndex',    'TDCameraIndex()'),
}

# Built-in attributes that read a geometry attribute, which must then be declared on the GLSL
# MAT's Attributes page: name -> (geometry attribute, abstract type). TDTexCoord(0u) is empty
# for POPs; TDTexAttrib_Tex(0u) is Tex for POPs and uv[0] for SOPs.
ATTRIBUTE_GEO = {'uv': ('Tex', 'vec3')}

# The shader output (fog) reads these whatever the graph contains.
SURFACE_ATTRS = ('world_pos', 'camera_index')

# A snippet or helper that matches this depends on the pixel (see @differentiate).
PIXEL_READ = re.compile(r'\biVert\.|\bgl_FragCoord\b')

# What an unconnected closure input is: no light and no coverage, so adding it changes nothing
# and mixing towards it fades the surface out.
EMPTY_CLOSURE = 'MatxClosure(vec3(0.0), 0.0)'

PIXEL_PREAMBLE = '''\
struct MatxClosure {
	vec3 radiance;
	float alpha;
};
'''


# --------------------------------------------------------------------------
# Snippets
# --------------------------------------------------------------------------

def _parse_default(type_, text):
	if re.match(r'[A-Za-z_]\w*$', text):
		if text not in ATTRIBUTES:
			raise MatxError('default %r is neither a number nor an attribute' % text)
		if ATTRIBUTES[text][0] not in COMPONENTS:
			raise MatxError('attribute %r cannot be an input default' % text)
		return text   # attribute name: read iVert.<member> when the input is unconnected
	nums = [float(t) for t in text.split()]
	n = COMPONENTS[type_]
	if len(nums) == 1:
		nums = nums * n
	if len(nums) != n:
		raise MatxError('default %r does not fit type %s' % (text, type_))
	return nums[0] if n == 1 else nums


def parse_snippet(text):
	"""Returns dict(type, samplers=[(type,name)], menus=[(name,[items])], ins=[(type,name,default)],
	outs=[(type,name)], attrs, requires, uniforms, driven={uniform: expression},
	attribs=[(type,name,default attribute,flavor)], ranges={input: (low, high)},
	enables={parameter: [(menu, [items], True for `if` / False for `unless`)]},
	kinds={output: 'vector' | 'color'} (from `@out vec3 result vector`),
	differentiate={input: (by input or None, menu or None, [items])}, category, body).
	A default is a float, a list of floats, an attribute name or None. @enable only drives the
	node's UI: the shader is the same whatever is greyed out."""
	snip = {'type': None, 'samplers': [], 'ins': [], 'outs': [], 'attrs': [], 'requires': [],
	        'uniforms': [], 'driven': {}, 'menus': [], 'attribs': [], 'ranges': {}, 'enables': {},
	        'kinds': {}, 'differentiate': {}, 'category': None}
	body = []
	for line in text.splitlines():
		m = re.match(r'\s*//\s*@(\w+)\s*(.*?)\s*$', line)
		if not m:
			body.append(line)
			continue
		key, rest = m.groups()
		if key == 'type':
			snip['type'] = rest
		elif key == 'category':
			snip['category'] = rest or None
		elif key == 'in':
			m2 = re.match(r'(\w+)\s+(\w+)(?:\s*=\s*([^\[]+?))?(?:\s*\[\s*(\S+)\s+(\S+)\s*\])?$', rest)
			if not m2 or m2.group(1) not in TYPES:
				raise MatxError('bad @in line: %r' % line)
			t, name, d, low, high = m2.groups()
			snip['ins'].append((t, name, _parse_default(t, d) if d else None))
			if low is not None:
				try:
					snip['ranges'][name] = (float(low), float(high))
				except ValueError:
					raise MatxError('bad @in range: %r' % line)
		elif key == 'out':
			m2 = re.match(r'(\w+)\s+(\w+)(?:\s+(vector|color))?$', rest)
			if not m2 or m2.group(1) not in TYPES or (m2.group(3) and m2.group(1) not in ('vec3', 'vec4')):
				raise MatxError('bad @out line (want: type name [vector|color], vector/color on vec3/vec4): %r'
				                % line)
			snip['outs'].append((m2.group(1), m2.group(2)))
			if m2.group(3):
				snip['kinds'][m2.group(2)] = m2.group(3)
		elif key == 'attr':
			for a in rest.split():
				if a not in ATTRIBUTES:
					raise MatxError('unknown attribute %r' % a)
				snip['attrs'].append(a)
		elif key == 'requires':
			snip['requires'].extend(rest.split())
		elif key == 'uniform':
			if '=' in rest:   # `name = expression`: always a uniform, the parameter runs the expression
				name, expr = (x.strip() for x in rest.split('=', 1))
				if not re.match(r'\w+$', name) or not expr:
					raise MatxError('bad @uniform line: %r' % line)
				snip['uniforms'].append(name)
				snip['driven'][name] = expr
			else:
				snip['uniforms'].extend(rest.split())
		elif key == 'attrib':
			m2 = re.match(r'(\w+)\s+(\w+)\s*=\s*([A-Za-z_]\w*)(?:\s+(\w+))?$', rest)
			if not m2 or m2.group(1) not in COMPONENTS or (m2.group(4) or 'typed') not in ATTRIB_FLAVORS \
			        or (m2.group(4) == 'texcoord' and m2.group(1) != 'vec3'):
				raise MatxError('bad @attrib line (want: type name = Attribute [texcoord|typed], '
				                'texcoord being vec3): %r' % line)
			snip['attribs'].append(m2.groups())
		elif key == 'sampler':
			m2 = re.match(r'(\w+)\s+(\w+)$', rest)
			if not m2 or m2.group(1) not in SAMPLER_TYPES:
				raise MatxError('bad @sampler line: %r' % line)
			snip['samplers'].append((m2.group(1), m2.group(2)))
		elif key == 'menu':
			words = rest.split()
			if len(words) < 2 or not re.match(r'[a-z]', words[0]) \
			        or not all(re.match(r'[a-z0-9][a-z0-9_]*$', w) for w in words) \
			        or len(set(words[1:])) != len(words) - 1:
				raise MatxError('bad @menu line (want: name item item..., lower case, unique): %r' % line)
			snip['menus'].append((words[0], words[1:]))
		elif key == 'enable':
			m2 = re.match(r'(\w+(?:\s+\w+)*?)\s+(if|unless)\s+(\w+)((?:\s+\w+)+)$', rest)
			if not m2:
				raise MatxError('bad @enable line (want: name... if|unless menu item...): %r' % line)
			names, word, menu, items = m2.groups()
			for name in names.split():
				snip['enables'].setdefault(name, []).append((menu, items.split(), word == 'if'))
		elif key == 'differentiate':
			m2 = re.match(r'(\w+)(?:\s+by\s+(\w+))?(?:\s+if\s+(\w+)((?:\s+\w+)+))?$', rest)
			if not m2 or m2.group(1) in snip['differentiate']:
				raise MatxError('bad @differentiate line (want: input [by input] [if menu item...], once '
				                'per input): %r' % line)
			name, by, menu, items = m2.groups()
			snip['differentiate'][name] = (by, menu, items.split() if items else [])
		else:
			raise MatxError('unknown snippet key @%s' % key)
	if not snip['type']:
		raise MatxError('snippet has no @type')
	ins = {name: (t, d) for (t, name, d) in snip['ins']}
	taken = list(ins) + [n for (_, n) in snip['samplers']]
	for (name, _) in snip['menus']:
		if name in taken:
			raise MatxError('@menu %s clashes with an @in or @sampler of the same name' % name)
		taken.append(name)
	for (_, name, _, _) in snip['attribs']:
		if name in taken:
			raise MatxError('@attrib %s clashes with an @in, @sampler or @menu of the same name' % name)
		taken.append(name)
	for name in snip['uniforms']:
		if name not in ins or ins[name][0] == CLOSURE or isinstance(ins[name][1], str):
			raise MatxError('@uniform %s must name a non-closure @in without an attribute default' % name)
	menus = dict(snip['menus'])
	with_par = [n for n, (t, d) in ins.items() if t != CLOSURE and not isinstance(d, str)]
	with_par += list(menus) + [n for (_, n, _, _) in snip['attribs']]
	for name, conditions in snip['enables'].items():
		if name not in with_par:
			raise MatxError('@enable %s must name an @in with a parameter, a @menu or an @attrib' % name)
		for (menu, items, _) in conditions:
			if menu not in menus or menu == name:
				raise MatxError('@enable %s: %r is not another @menu of the snippet' % (name, menu))
			unknown = [i for i in items if i not in menus[menu]]
			if unknown:
				raise MatxError('@enable %s: @menu %s has no item %s' % (name, menu, ', '.join(unknown)))
	for name, (by, menu, items) in snip['differentiate'].items():
		if name not in ins or ins[name][0] == CLOSURE:
			raise MatxError('@differentiate %s must name a non-closure @in' % name)
		if by is not None and (by not in ins or ins[by][0] != 'float'):
			raise MatxError('@differentiate %s: %r is not a float @in' % (name, by))
		if menu is not None and (menu not in menus or any(i not in menus[menu] for i in items)):
			raise MatxError('@differentiate %s: %r is not a @menu holding %s' % (name, menu, ', '.join(items)))
	snip['body'] = '\n'.join(body).strip() + '\n'
	if not re.search(r'\bvoid\s+matx_%s\s*\(' % snip['type'], snip['body']):
		raise MatxError('snippet %s must define void matx_%s(...)' % (snip['type'], snip['type']))
	return snip


_PARSED = {}   # snippet text -> parse_snippet result


def parse_snippet_cached(text):
	"""parse_snippet, remembered per text: the hosts parse every snippet on each cook. The result
	is shared, so callers must not modify it."""
	snip = _PARSED.get(text)
	if snip is None:
		if len(_PARSED) > 1024:   # edited snippets leave their old texts behind
			_PARSED.clear()
		snip = _PARSED[text] = parse_snippet(text)
	return snip


def load_snippets(nodes_dir, lib_dir):
	"""Reads glsl/nodes/*.glsl and glsl/lib/*.glsl from disk."""
	import os
	snippets = {}
	for f in sorted(os.listdir(nodes_dir)):
		if f.endswith('.glsl'):
			with open(os.path.join(nodes_dir, f), encoding='utf-8') as fh:
				s = parse_snippet(fh.read())
			snippets[s['type']] = s
	lib = {}
	for f in sorted(os.listdir(lib_dir)):
		if f.endswith('.glsl'):
			with open(os.path.join(lib_dir, f), encoding='utf-8') as fh:
				lib[f[:-5]] = fh.read()
	return snippets, lib


# --------------------------------------------------------------------------
# Value / type helpers
# --------------------------------------------------------------------------

def _f(x):
	s = repr(float(x))
	return s if any(c in s for c in '.en') else s + '.0'


def literal(type_, value):
	if type_ == CLOSURE:
		raise MatxError('closure inputs cannot be literals')
	n = COMPONENTS[type_]
	if isinstance(value, (int, float)):
		value = [value] * n
	if len(value) != n:
		raise MatxError('literal %r does not fit %s' % (value, type_))
	if n == 1:
		return _f(value[0])
	return '%s(%s)' % (type_, ', '.join(_f(v) for v in value))


def convert(expr, src, dst):
	if src == dst:
		return expr
	if CLOSURE in (src, dst):
		raise MatxError('cannot convert %s to %s' % (src, dst))
	if src == 'float':
		return '%s(%s)' % (dst, expr)
	if dst == 'float':
		xyz = expr if src == 'vec3' else '(%s).xyz' % expr
		if src == 'vec2':
			return '(%s).x' % expr
		return 'dot(%s, vec3(0.2126, 0.7152, 0.0722))' % xyz
	table = {
		('vec2', 'vec3'): 'vec3(%s, 0.0)',
		('vec2', 'vec4'): 'vec4(%s, 0.0, 1.0)',
		('vec3', 'vec2'): '(%s).xy',
		('vec3', 'vec4'): 'vec4(%s, 1.0)',
		('vec4', 'vec2'): '(%s).xy',
		('vec4', 'vec3'): '(%s).xyz',
	}
	return table[(src, dst)] % expr


def is_color(type_, name):
	"""vec3/vec4 sockets are colours unless the name looks spatial (vector, normal, uv, ...)."""
	return type_ in ('vec3', 'vec4') and not any(w in name.lower() for w in SPATIAL_WORDS)


def socket_kind(snip, type_, name):
	"""What a socket carries, as Blender colours it: 'float', 'vector', 'color' or 'shader'. A
	vec3/vec4 is a colour unless its name looks spatial (is_color) or its @out line says which."""
	if type_ == CLOSURE:
		return 'shader'
	if type_ == 'float':
		return 'float'
	if name in snip.get('kinds', {}):
		return snip['kinds'][name]
	return 'color' if is_color(type_, name) else 'vector'


def _ident(node_id):
	return re.sub(r'\W', '_', str(node_id))


def _var(node_id, socket):
	return '%s_%s' % (_ident(node_id), socket)


# --------------------------------------------------------------------------
# Graph analysis
# --------------------------------------------------------------------------

def is_link(v):
	return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)


def sort_graph(graph, root_id):
	"""Post-order DFS from root_id over links. Returns node ids, dependencies first."""
	nodes = graph['nodes']
	order, state = [], {}

	def visit(nid, path):
		if nid not in nodes:
			raise MatxError('link to missing node %r' % nid)
		if state.get(nid) == 2:
			return
		if state.get(nid) == 1:
			raise MatxError('cycle in graph: ' + ' -> '.join(path + [nid]))
		state[nid] = 1
		for v in nodes[nid].get('inputs', {}).values():
			if is_link(v):
				visit(v[0], path + [nid])
		state[nid] = 2
		order.append(nid)

	visit(root_id, [])
	return order


def _collect_lib(names, lib, seen, out):
	for n in names:
		if n in seen:
			continue
		if n not in lib:
			raise MatxError('missing helper library %r' % n)
		seen.add(n)
		text = lib[n]
		deps = []
		for line in text.splitlines():
			m = re.match(r'\s*//\s*@requires\s+(.*)$', line)
			if m:
				deps.extend(m.group(1).split())
		_collect_lib(deps, lib, seen, out)
		out.append(text.strip() + '\n')


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

def generate(graph, snippets, lib=None):
	"""Shades graph['output'] (see surface_color). Returns dict(vertex=str, pixel=str,
	attributes=[...], order=[...], samplers=[[uniform, TOP path], ...],
	uniforms=[[uniform, op path, par name, 'color' | 'vector'], ...],
	attribs=[[geometry attribute, MAT attribute type], ...])."""
	lib = lib or {}
	if graph.get('error'):
		raise MatxError('upstream node failed: ' + graph['error'])
	nodes = graph['nodes']
	out = graph.get('output')
	if not out or out[0] not in nodes:
		raise MatxError('graph has no output node')
	root, socket = out
	if socket is None:
		raise MatxError('output node %s (%s) has no output socket' % (root, nodes[root]['type']))

	order = sort_graph(graph, root)
	used_types = []
	attrs = list(SURFACE_ATTRS)
	libs = []
	seen_lib = set()
	body = []
	out_types = {}   # var name -> glsl abstract type
	samplers = []    # (glsl type, uniform name, TOP path)
	uniforms = []    # (glsl type, uniform name, op path, par name, MAT page)
	named = []       # (glsl type, Vertex member, vertex expression) of @attrib attributes
	geo = {}         # geometry attribute -> abstract type, for the MAT's Attributes page

	def use_attr(a):
		if a not in attrs:
			attrs.append(a)
		if a in ATTRIBUTE_GEO:
			use_geo(*ATTRIBUTE_GEO[a])

	def use_geo(name, ty):
		if geo.setdefault(name, ty) != ty:
			raise MatxError('attribute %s is read as %s and as %s' % (name, geo[name], ty))

	# Every node's call, its arguments as (text, link) with link = (source node, source variable,
	# source type, input type) for a wired input, and whether it depends on the pixel (`varying`).
	calls = {}
	varying = {}
	reads_pixel = {}   # node type -> its snippet or helpers read the Vertex block or gl_FragCoord
	for nid in order:
		node = nodes[nid]
		t = node['type']
		if t not in snippets:
			raise MatxError('no snippet for node type %r (node %s)' % (t, nid))
		sn = snippets[t]
		if t not in used_types:
			used_types.append(t)
			for a in sn['attrs']:
				use_attr(a)
			_collect_lib(sn['requires'], lib, seen_lib, libs)
			own = []
			_collect_lib(sn['requires'], lib, set(), own)
			reads_pixel[t] = any(PIXEL_READ.search(s) for s in [sn['body']] + own)
		vary = reads_pixel[t] or bool(sn['attribs'])

		args = []
		for (ty, name) in sn['samplers']:
			path = node.get('samplers', {}).get(name)
			if not path:
				raise MatxError('node %s (%s): no TOP for sampler %r' % (nid, t, name))
			uniform = 'sMatx_' + _var(nid, name)
			samplers.append((ty, uniform, path))
			args.append(uniform)
		for (name, items) in sn['menus']:
			item = node.get('menus', {}).get(name, items[0])
			if item not in items:
				raise MatxError('node %s (%s): %r is not a %s option' % (nid, t, item, name))
			args.append(menu_constant(t, name, item))
		for (ty, name, default, flavor) in sn['attribs']:
			a_name, a_type = node.get('attribs', {}).get(name) or (default, ty)
			if not re.match(r'[A-Za-z_]\w*$', str(a_name)):
				raise MatxError('node %s (%s): %r is not an attribute name' % (nid, t, a_name))
			if a_type not in COMPONENTS or (flavor != 'typed' and a_type != ty):
				raise MatxError('node %s (%s): attribute %s cannot be read as %s' % (nid, t, a_name, a_type))
			use_geo(a_name, a_type)
			if flavor == 'texcoord' and (a_name, a_type) == ATTRIBUTE_GEO['uv']:
				use_attr('uv')
				member = ATTRIBUTES['uv'][1]
			else:
				if flavor == 'texcoord':
					member, expr = 'tex_' + a_name, 'TDInstanceTexCoord(TDTexAttrib_%s(0u))' % a_name
				else:
					member, expr = 'attr_' + a_name, 'TDAttrib_%s()' % a_name
				if member not in [m for (_, m, _) in named]:
					named.append((GLSL_TYPE[a_type], member, expr))
			args.append(convert('iVert.' + member, a_type, ty))
		links = {}   # argument index -> (source node, source variable, source type, input type)
		at = {}      # input name -> argument index
		for (ty, name, default) in sn['ins']:
			at[name] = len(args)
			v = node.get('inputs', {}).get(name, default)
			ref = node.get('uniforms', {}).get(name)
			if ref is not None and not is_link(v):
				if name not in sn['uniforms']:
					raise MatxError('node %s (%s): input %r cannot be a uniform' % (nid, t, name))
				uniform = 'uMatx_' + _var(nid, name)
				if is_color(ty, name):   # the Colors page always feeds a vec4
					uniforms.append(('vec4', uniform, ref[0], ref[1], 'color'))
					args.append(uniform + '.rgb' if ty == 'vec3' else uniform)
				else:
					uniforms.append((GLSL_TYPE[ty], uniform, ref[0], ref[1], 'vector'))
					args.append(uniform)
				continue
			if v is None and ty == CLOSURE:
				args.append(EMPTY_CLOSURE)   # an unconnected shader input
				continue
			if v is None:
				raise MatxError('node %s (%s): input %r has no value' % (nid, t, name))
			if isinstance(v, str):
				if v not in ATTRIBUTES:
					raise MatxError('node %s (%s): unknown attribute %r' % (nid, t, v))
				use_attr(v)
				a_type, member, _ = ATTRIBUTES[v]
				args.append(convert('iVert.' + member, a_type, ty))
				vary = vary or a_type in COMPONENTS
			elif is_link(v):
				src_id, src_sock = v
				key = _var(src_id, src_sock)
				if key not in out_types:
					raise MatxError('node %s: link to unknown output %s.%s' % (nid, src_id, src_sock))
				links[len(args)] = (src_id, key, out_types[key], ty)
				args.append(convert(key, out_types[key], ty))
				vary = vary or varying[src_id]
			else:
				args.append(literal(ty, v))
		diffs = {}   # argument index -> (argument index of `by` or None, whether it applies now)
		for name, (by, menu, items) in sn['differentiate'].items():
			chosen = node.get('menus', {}).get(menu, dict(sn['menus'])[menu][0]) if menu else None
			diffs[at[name]] = (at[by] if by else None, menu is None or chosen in items)
		outs = []
		for (ty, name) in sn['outs']:
			var = _var(nid, name)
			out_types[var] = ty
			outs.append((GLSL_TYPE[ty], var))
		calls[nid] = (t, args, links, diffs, outs)
		varying[nid] = vary

	repeats = []      # one entry per differentiated input whose graph is emitted again
	at_pixel = {}     # (node, argument index) -> [_dx, _dy] arguments of its call at this pixel

	def emit(nid, suffix=''):
		"""Appends the call of node nid to body. suffix '' is the call at this pixel; '_dx<k>' or
		'_dy<k>' a repetition at a neighbouring pixel, reading the repeated sources' variables."""
		t, args, links, diffs, outs = calls[nid]
		args = list(args)
		for i, (src, key, src_ty, ty) in links.items():
			if suffix and varying[src]:
				args[i] = convert(key + suffix, src_ty, ty)
		extra = {}
		for i, (by, applies) in diffs.items():
			if suffix:   # nested in a repetition: keep the values at this pixel
				args[i] = calls[nid][1][i]
				extra[i] = at_pixel[(nid, i)]
			elif applies and i in links and varying[links[i][0]]:
				extra[i] = at_pixel[(nid, i)] = repeat(links[i], args[by] if by is not None else '1.0')
			else:
				extra[i] = at_pixel[(nid, i)] = [args[i], args[i]]
		full = []
		for i, a in enumerate(args):
			full.append(a)
			full += extra.get(i, [])
		for (glsl_ty, var) in outs:
			body.append('\t%s %s;' % (glsl_ty, var + suffix))
		body.append('\tmatx_%s(%s);' % (t, ', '.join(full + [var + suffix for (_, var) in outs])))

	def repeat(link, by):
		"""Emits the pixel-dependent part of the graph feeding link twice more, as at the pixel by
		pixels to the right and the one above; returns the input's [_dx, _dy] expressions."""
		src, key, src_ty, ty = link
		k = len(repeats)
		repeats.append(src)
		part = [n for n in sort_graph(graph, src) if varying[n]]
		res = []
		body.append('\t// %s again, as at the neighbouring pixels (@differentiate)' % key)
		for axis, offset in (('dx', 'vec2(%s, 0.0)'), ('dy', 'vec2(0.0, %s)')):
			suffix = '_%s%d' % (axis, k)
			body.append('\tmatxAtPixel(%s);' % (offset % by))
			for n in part:
				emit(n, suffix)
			res.append(convert(key + suffix, src_ty, ty))
		body.append('\tmatxAtPixel(vec2(0.0));')
		return res

	for nid in order:
		emit(nid)

	key = _var(root, socket)
	if key not in out_types:
		raise MatxError('node %s (%s) has no output %r' % (root, nodes[root]['type'], socket))
	decls = [(ty, u) for (ty, u, _) in samplers] + [(ty, u) for (ty, u, _, _, _) in uniforms]
	members = [ATTRIBUTES[a] for a in ATTRIBUTES if a in attrs] + named
	pixel = _pixel(snippets, body, members, libs, used_types, surface_color(key, out_types[key]), decls,
	               bool(repeats))
	return {'vertex': _vertex(members), 'pixel': pixel, 'attributes': attrs, 'order': order,
	        'samplers': [[u, path] for (_, u, path) in samplers],
	        'uniforms': [[u, path, par, page] for (_, u, path, par, page) in uniforms],
	        'attribs': [[name, MAT_ATTRIB_TYPE[ty]] for name, ty in geo.items()]}


VERTEX_HEAD = '''\
	gl_PointSize = 2.0;
	vec3 pos = TDPos();
	vec3 normal = TDNormal();
	// TDDeform always returns values in world space
	vec4 worldSpacePos = TDDeform(pos);
	vec3 uvUnwrapCoord = TDInstanceTexCoord(TDUVUnwrapCoord());
	gl_Position = TDWorldToProj(worldSpacePos, uvUnwrapCoord);

#ifndef TD_PICKING_ACTIVE
'''

VERTEX_TAIL = '''\
#else // TD_PICKING_ACTIVE

	TDWritePickingValues();

#endif // TD_PICKING_ACTIVE
'''

PIXEL_HEAD = '''\
	// This allows things such as order independent transparency
	// and Dual-Paraboloid rendering to work properly
	TDCheckDiscard();
'''

PIXEL_TAIL = '''\
	vec4 finalColor = {surface};

	// Apply fog, this does nothing if fog is disabled
	finalColor = TDFog(finalColor, iVert.worldSpacePos.xyz, iVert.cameraIndex);

	// Dithering, does nothing if dithering is disabled
	finalColor = TDDither(finalColor);

	// Vulkan removed the implicit alpha test, so it is applied manually here.
	// This function does nothing if alpha test is disabled.
	TDAlphaTest(finalColor.a);

	{{
		vec4 outVal = finalColor;
		// When outputting directly to a window (such as node viewers)
		// convert to the window's color space.
		outVal = TDConvertColorSpace(outVal);
		oFragColor[0] = TDOutputSwizzle(outVal);
	}}

	// Output zero to every color buffer except the first one.
	for (int i = 1; i < TD_NUM_COLOR_BUFFERS; i++)
	{{
		oFragColor[i] = vec4(0.0);
	}}
'''


def _block(keyword, instance, members):
	"""The Vertex interface block for members [(glsl type, name, vertex expression)]."""
	lines = [keyword, '{']
	for (t, member, _) in members:
		lines.append('\t%s %s;' % (t, member))
	lines.append('} %s;' % instance)
	return '\n'.join(lines) + '\n'


def _vertex(members):
	assigns = ''.join('\toVert.%s = %s;\n' % (member, expr) for (_, member, expr) in members)
	return ('// generated by tdx-matx -- do not edit\n' + _block('out Vertex', 'oVert', members)
	        + '\nvoid main()\n{\n' + VERTEX_HEAD + '\n' + assigns + '\n' + VERTEX_TAIL + '}\n')


def surface_color(var, type_):
	"""The vec4 the shader outputs for the surface variable `var`: a closure's radiance and alpha,
	or any other value as opaque emission (float x -> vec4(vec3(x), 1.0), vec3 c -> vec4(c, 1.0))."""
	if type_ == CLOSURE:
		return 'vec4(%s.radiance, %s.alpha)' % (var, var)
	if type_ == 'float':
		return 'vec4(vec3(%s), 1.0)' % var
	return convert(var, type_, 'vec4')


def menu_constant(type_, menu, item):
	"""GLSL name of a menu item: Math, operation, add -> MATX_MATH_OPERATION_ADD."""
	return ('MATX_%s_%s_%s' % (type_, menu, item)).upper()


def _at_pixel(members):
	"""matxV, the Vertex block as the nodes read it, and matxAtPixel(), which moves it (and
	matxFragCoord) to the pixel d pixels away by following the derivatives of every member."""
	struct = ['struct MatxVertex', '{'] + ['\t%s %s;' % (t.replace('flat ', ''), m) for (t, m, _) in members]
	moves = []
	for (t, m, _) in members:
		if t.startswith('flat '):
			moves.append('\tmatxV.%s = iVert.%s;' % (m, m))
		else:
			moves.append('\tmatxV.{0} = iVert.{0} + d.x * dFdx(iVert.{0}) + d.y * dFdy(iVert.{0});'.format(m))
	return '\n'.join(
		['// The Vertex block and gl_FragCoord as the nodes read them: at this pixel, or at a',
		 '// neighbouring one while an input is evaluated there again (@differentiate)']
		+ struct + ['};', 'MatxVertex matxV;', 'vec4 matxFragCoord;', '',
		            'void matxAtPixel(vec2 d)', '{'] + moves
		+ ['\tmatxFragCoord = gl_FragCoord + vec4(d, 0.0, 0.0);', '}']) + '\n'


def _read_at_pixel(text):
	"""Points the reads of the Vertex block and gl_FragCoord at matxV and matxFragCoord."""
	return re.sub(r'\bgl_FragCoord\b', 'matxFragCoord', re.sub(r'\biVert\.', 'matxV.', text))


def _pixel(snippets, body, members, libs, used_types, surface, decls, differentiating=False):
	moved = _read_at_pixel if differentiating else (lambda s: s)
	lines = ['// generated by tdx-matx -- do not edit', '#include <TDColorSpace>', '',
	         _block('in Vertex', 'iVert', members),
	         '// Output variable for the color',
	         'layout(location = 0) out vec4 oFragColor[TD_NUM_COLOR_BUFFERS];', '']
	if decls:
		lines += ['uniform %s %s;' % (ty, u) for (ty, u) in decls] + ['']
	lines += [PIXEL_PREAMBLE]
	if differentiating:
		lines += [_at_pixel(members)]
	lines += [moved(s) for s in libs]
	for t in used_types:
		consts = ['const int %s = %d;' % (menu_constant(t, name, item), i)
		          for (name, items) in snippets[t]['menus'] for i, item in enumerate(items)]
		lines += consts + [''] * bool(consts) + [moved(snippets[t]['body'])]
	lines += ['void main()', '{', PIXEL_HEAD]
	if differentiating:
		lines += ['\tmatxAtPixel(vec2(0.0));']
	lines += [moved(s) for s in body]
	lines += ['', PIXEL_TAIL.format(surface=surface) + '}']
	return '\n'.join(lines) + '\n'


FALLBACK_VERTEX = '''\
// tdx-matx fallback shader: the graph could not be generated (see the vertex/pixel DAT errors)
void main()
{
	vec4 worldSpacePos = TDDeform(TDPos());
	vec3 uvUnwrapCoord = TDInstanceTexCoord(TDUVUnwrapCoord());
	gl_Position = TDWorldToProj(worldSpacePos, uvUnwrapCoord);

#ifdef TD_PICKING_ACTIVE
	TDWritePickingValues();
#endif
}
'''

FALLBACK_PIXEL = '''\
// tdx-matx fallback shader: the graph could not be generated (see the vertex/pixel DAT errors)
layout(location = 0) out vec4 oFragColor[TD_NUM_COLOR_BUFFERS];

void main()
{
	TDCheckDiscard();
	oFragColor[0] = TDOutputSwizzle(vec4(1.0, 0.0, 1.0, 1.0));
	for (int i = 1; i < TD_NUM_COLOR_BUFFERS; i++)
	{
		oFragColor[i] = vec4(0.0);
	}
}
'''


def fallback():
	"""A valid flat-magenta shader pair. A GLSL MAT must never get empty or broken source:
	TouchDesigner crashes cooking a rendered GLSL MAT whose shader DATs are empty."""
	return {'vertex': FALLBACK_VERTEX, 'pixel': FALLBACK_PIXEL}


if __name__ == '__main__':
	import json, os, sys
	root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
	snips, lib = load_snippets(os.path.join(root, 'glsl', 'nodes'), os.path.join(root, 'glsl', 'lib'))
	with open(sys.argv[1], encoding='utf-8') as fh:
		res = generate(json.load(fh), snips, lib)
	base = sys.argv[2] if len(sys.argv) > 2 else None
	if base:
		for k, ext in (('vertex', 'vert'), ('pixel', 'frag')):
			with open('%s.%s' % (base, ext), 'w', encoding='utf-8') as fh:
				fh.write(res[k])
	else:
		print(res['vertex']); print(res['pixel'])
