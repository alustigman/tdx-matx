"""
Graph -> GLSL MAT shader generation.

Pure Python (no TouchDesigner imports) so it can be unit tested outside TD.

Snippet files (glsl/nodes/*.glsl) start with a header of `// @key value` lines:

    // @type  NoiseTexture
    // @category Texture         (the node's group in the MATX family's OP Create menu)
    // @in    vec3 vector = 0.0
    // @in    float scale = 5.0
    // @in    vec3 coord = uv    (a default naming an ATTRIBUTE reads it when unconnected)
    // @out   float fac
    // @attr  uv                 (vertex attribute the snippet reads, see ATTRIBUTES)
    // @requires hash            (helper file glsl/lib/hash.glsl, included once)
    // @sampler sampler2D image  (a texture per node instance, see SAMPLER_TYPES)
    // @uniform value            (an @in the node may bind to a uniform instead of a literal)
    // @menu  operation add subtract   (a constant chosen from a menu, the first item by default)

The graph's `output` ([node_id, socket]) is the surface the shader renders. A closure output
supplies radiance and alpha; any other value is shaded as emission, converted to vec4 like any
link except that a float is opaque grey (float x -> vec4(vec3(x), 1.0), vec3 c -> vec4(c, 1.0)).

The body must define `void matx_<type>(<samplers...>, <menus...>, <ins...>, out <outs...>)` with
parameters in the order the @sampler, @menu, @in, then @out lines appear (a menu is an `int`).

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
any other input goes on the Vectors page.
"""
import re

CLOSURE = 'closure'
TYPES = ('float', 'vec2', 'vec3', 'vec4', CLOSURE)
GLSL_TYPE = {'float': 'float', 'vec2': 'vec2', 'vec3': 'vec3', 'vec4': 'vec4',
             CLOSURE: 'MatxClosure'}
COMPONENTS = {'float': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4}
SAMPLER_TYPES = ('sampler2D',)
# a vec3/vec4 socket whose name contains one of these is a vector, otherwise a colour
SPATIAL_WORDS = ('vector', 'normal', 'pos', 'uv', 'coord', 'offset', 'dir', 'tangent', 'scale')


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
	'uv':           ('vec3',     'uv',             'TDInstanceTexCoord(TDTexCoord(0u))'),
	'camera_index': ('flat int', 'cameraIndex',    'TDCameraIndex()'),
}

# The shader output (fog) reads these whatever the graph contains.
SURFACE_ATTRS = ('world_pos', 'camera_index')

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
	outs=[(type,name)], attrs, requires, uniforms, category, body). A default is a float, a list of floats, an attribute name or None."""
	snip = {'type': None, 'samplers': [], 'ins': [], 'outs': [], 'attrs': [], 'requires': [],
	        'uniforms': [], 'menus': [], 'category': None}
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
			m2 = re.match(r'(\w+)\s+(\w+)(?:\s*=\s*(.+))?$', rest)
			if not m2 or m2.group(1) not in TYPES:
				raise MatxError('bad @in line: %r' % line)
			t, name, d = m2.groups()
			snip['ins'].append((t, name, _parse_default(t, d) if d else None))
		elif key == 'out':
			m2 = re.match(r'(\w+)\s+(\w+)$', rest)
			if not m2 or m2.group(1) not in TYPES:
				raise MatxError('bad @out line: %r' % line)
			snip['outs'].append((m2.group(1), m2.group(2)))
		elif key == 'attr':
			for a in rest.split():
				if a not in ATTRIBUTES:
					raise MatxError('unknown attribute %r' % a)
				snip['attrs'].append(a)
		elif key == 'requires':
			snip['requires'].extend(rest.split())
		elif key == 'uniform':
			snip['uniforms'].extend(rest.split())
		elif key == 'sampler':
			m2 = re.match(r'(\w+)\s+(\w+)$', rest)
			if not m2 or m2.group(1) not in SAMPLER_TYPES:
				raise MatxError('bad @sampler line: %r' % line)
			snip['samplers'].append((m2.group(1), m2.group(2)))
		elif key == 'menu':
			words = rest.split()
			if len(words) < 2 or not all(re.match(r'[a-z][a-z0-9_]*$', w) for w in words) \
			        or len(set(words[1:])) != len(words) - 1:
				raise MatxError('bad @menu line (want: name item item..., lower case, unique): %r' % line)
			snip['menus'].append((words[0], words[1:]))
		else:
			raise MatxError('unknown snippet key @%s' % key)
	if not snip['type']:
		raise MatxError('snippet has no @type')
	ins = {name: (t, d) for (t, name, d) in snip['ins']}
	for (name, _) in snip['menus']:
		if name in ins or name in [n for (_, n) in snip['samplers']]:
			raise MatxError('@menu %s clashes with an @in or @sampler of the same name' % name)
	for name in snip['uniforms']:
		if name not in ins or ins[name][0] == CLOSURE or isinstance(ins[name][1], str):
			raise MatxError('@uniform %s must name a non-closure @in without an attribute default' % name)
	snip['body'] = '\n'.join(body).strip() + '\n'
	if not re.search(r'\bvoid\s+matx_%s\s*\(' % snip['type'], snip['body']):
		raise MatxError('snippet %s must define void matx_%s(...)' % (snip['type'], snip['type']))
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
	uniforms=[[uniform, op path, par name, 'color' | 'vector'], ...])."""
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

	for nid in order:
		node = nodes[nid]
		t = node['type']
		if t not in snippets:
			raise MatxError('no snippet for node type %r (node %s)' % (t, nid))
		sn = snippets[t]
		if t not in used_types:
			used_types.append(t)
			for a in sn['attrs']:
				if a not in attrs:
					attrs.append(a)
			_collect_lib(sn['requires'], lib, seen_lib, libs)

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
		for (ty, name, default) in sn['ins']:
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
			if v is None:
				raise MatxError('node %s (%s): input %r has no value' % (nid, t, name))
			if isinstance(v, str):
				if v not in ATTRIBUTES:
					raise MatxError('node %s (%s): unknown attribute %r' % (nid, t, v))
				if v not in attrs:
					attrs.append(v)
				a_type, member, _ = ATTRIBUTES[v]
				args.append(convert('iVert.' + member, a_type, ty))
			elif is_link(v):
				src_id, src_sock = v
				key = _var(src_id, src_sock)
				if key not in out_types:
					raise MatxError('node %s: link to unknown output %s.%s' % (nid, src_id, src_sock))
				args.append(convert(key, out_types[key], ty))
			else:
				args.append(literal(ty, v))
		outs = []
		for (ty, name) in sn['outs']:
			var = _var(nid, name)
			out_types[var] = ty
			body.append('\t%s %s;' % (GLSL_TYPE[ty], var))
			outs.append(var)
		body.append('\tmatx_%s(%s);' % (t, ', '.join(args + outs)))

	key = _var(root, socket)
	if key not in out_types:
		raise MatxError('node %s (%s) has no output %r' % (root, nodes[root]['type'], socket))
	decls = [(ty, u) for (ty, u, _) in samplers] + [(ty, u) for (ty, u, _, _, _) in uniforms]
	pixel = _pixel(snippets, body, attrs, libs, used_types, surface_color(key, out_types[key]), decls)
	return {'vertex': _vertex(attrs), 'pixel': pixel, 'attributes': attrs, 'order': order,
	        'samplers': [[u, path] for (_, u, path) in samplers],
	        'uniforms': [[u, path, par, page] for (_, u, path, par, page) in uniforms]}


def _ordered(attrs):
	return [a for a in ATTRIBUTES if a in attrs]


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


def _block(keyword, instance, attrs):
	lines = [keyword, '{']
	for a in _ordered(attrs):
		t, member, _ = ATTRIBUTES[a]
		lines.append('\t%s %s;' % (t, member))
	lines.append('} %s;' % instance)
	return '\n'.join(lines) + '\n'


def _vertex(attrs):
	assigns = ''.join('\toVert.%s = %s;\n' % (ATTRIBUTES[a][1], ATTRIBUTES[a][2]) for a in _ordered(attrs))
	return ('// generated by tdx-matx -- do not edit\n' + _block('out Vertex', 'oVert', attrs)
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


def _pixel(snippets, body, attrs, libs, used_types, surface, decls):
	lines = ['// generated by tdx-matx -- do not edit', '#include <TDColorSpace>', '',
	         _block('in Vertex', 'iVert', attrs),
	         '// Output variable for the color',
	         'layout(location = 0) out vec4 oFragColor[TD_NUM_COLOR_BUFFERS];', '']
	if decls:
		lines += ['uniform %s %s;' % (ty, u) for (ty, u) in decls] + ['']
	lines += [PIXEL_PREAMBLE]
	lines += libs
	for t in used_types:
		consts = ['const int %s = %d;' % (menu_constant(t, name, item), i)
		          for (name, items) in snippets[t]['menus'] for i, item in enumerate(items)]
		lines += consts + [''] * bool(consts) + [snippets[t]['body']]
	lines += ['void main()', '{', PIXEL_HEAD]
	lines += body
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
