"""
Builds the tdx-matx library inside the `matx` COMP (op shortcut `Matx`) from the repo files.

	core/      Text DATs synced to core/*.py (created by hand once, see bootstrap in README)
	snippets/  one Text DAT per glsl/nodes/*.glsl (named after its @type) and per
	           glsl/lib/*.glsl (named lib_<name>), synced to the files
	nodes/     one node COMP per snippet, plus EvaluateShader

A node COMP gets an In DAT per @in socket, a Menu parameter per @menu (no socket: a shader
constant), a custom parameter per literal input (none for a
closure, nor for an input whose default is a vertex attribute such as `uv`), a TOP parameter per
@sampler, a Str parameter per @attrib (the geometry attribute's name, plus a `<Name>type` Menu
for a `typed` one), an `Asuniform` toggle when the snippet declares @uniform inputs (a driven
uniform's parameter runs its expression instead), and a Script DAT + Out DAT per @out socket. Every node gets an `Editshader` pulse on its first page (Matx) that opens its
snippet in the external editor (see edit_shader); a node with outputs also gets a `Preview` toggle
there that creates or removes its `preview` COMP (see set_preview). One `par_exec` Parameter
Execute handles both.

Run it with the Matx COMP's `Build` pulse, or `op.Matx.op('core/td_builder').module.build_all(op.Matx)`.
Re-running is safe: existing COMPs and the values of their parameters are kept; In/Out DATs and
parameters are added to match the snippet headers. Build also upgrades every copy of a node in
the project (see upgrade_copies), so the copies follow a snippet whose sockets changed. Sockets that disappeared from a header lose
their DATs, but their parameters are only reported, never destroyed.
"""
import json
import math
import os
import re
from typing import Optional

GRID = 200
NODES_DIR = 'glsl/nodes'
LIB_DIR = 'glsl/lib'
NODE_CALLBACKS = "op.Matx.op('core/td_node_callbacks')"
EVAL_CALLBACKS = "op.Matx.op('core/td_eval_callbacks')"
COLUMNS = 5   # node COMPs per row in nodes/


def _snap(v: float) -> int:
	return int(math.ceil(v / GRID) * GRID)


# lower-case words shown in capitals in labels
ACRONYMS = ('rgb', 'hsv', 'hsl', 'ior', 'uv', 'bw', 'xyz', 'bsdf', 'ao')


def _label(socket: str) -> str:
	"""base_color -> Base Color, emissionColor -> Emission Color, RGBToBW -> RGB To BW,
	3d -> 3D, ior -> IOR."""
	spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', socket))
	words = spaced.replace('_', ' ').split()
	return ' '.join(w.upper() if w in ACRONYMS or re.match(r'\d+d$|f\d+$', w) else w[:1].upper() + w[1:]
	                for w in words)


def _norm_range(default) -> tuple:
	"""Slider range: 0-1, widened to twice the largest default component when that exceeds 1."""
	vals = default if isinstance(default, list) else [default or 0.0]
	top = max(vals)
	return (0.0, 2.0 * top if top > 1.0 else 1.0)


def _remove_stale(parent: COMP, prefix: str, keep: set, report: list) -> None:
	for o in parent.findChildren(name=prefix + '*', maxDepth=1):
		if o.name not in keep:
			report.append('removed %s' % o.path)
			o.destroy()


# --------------------------------------------------------------------------
# Layout helpers
# --------------------------------------------------------------------------

def _place_columns(columns: list, x: int = 0) -> None:
	"""Places lists of ops as left-to-right columns, top-aligned, spaced by their real sizes."""
	for col in columns:
		if not col:
			continue
		step = _snap(max(o.nodeHeight for o in col) + 60)
		for i, o in enumerate(col):
			o.nodeX, o.nodeY = x, -i * step
		x += _snap(max(o.nodeWidth for o in col) + GRID)


def _place_grid(ops: list, columns: int) -> None:
	if not ops:
		return
	sx = _snap(max(o.nodeWidth for o in ops) + GRID)
	sy = _snap(max(o.nodeHeight for o in ops) + GRID)
	for i, o in enumerate(ops):
		o.nodeX, o.nodeY = (i % columns) * sx, -(i // columns) * sy


# --------------------------------------------------------------------------
# Custom parameters (get-or-create: code owns the schema, the user owns the value)
# --------------------------------------------------------------------------

def _page(comp: COMP, name: str):
	for p in comp.customPages:
		if p.name == name:
			return p
	return comp.appendCustomPage(name)


def _par_style(type_: str, socket: str) -> str:
	"""vec3/vec4 sockets are colours (RGB/RGBA swatches) unless the name looks spatial
	(codegen.is_color, which also decides that a uniform goes on the MAT's Colors page)."""
	spatial = not op.Matx.op('core/codegen').module.is_color(type_, socket) and type_ != 'float'
	return {('float', False): 'Float', ('float', True): 'Float',
	        ('vec2', False): 'XY', ('vec2', True): 'XY',
	        ('vec3', False): 'RGB', ('vec3', True): 'XYZ',
	        ('vec4', False): 'RGBA', ('vec4', True): 'XYZW'}[(type_, spatial)]


# TD reports a tuplet's style by family: RGB reads RGBA, XY/XYZ read XYZW
_STYLE_FAMILY = {'RGB': ('RGB', 'RGBA'), 'XY': ('XY', 'XYZW'), 'XYZ': ('XYZ', 'XYZW')}


def _ensure_par(comp: COMP, page, name: str, style: str, report: list, label: str, help_: str,
                default=None, norm=None, read_only=False, menu=None, expr: Optional[str] = None) -> list:
	"""Get-or-create a custom parameter (the Pars of its tuplet). `expr` makes expression mode
	running it the parameter's default, applied to the value only when the parameter is created."""
	found = [p for p in comp.customPars if p.tupletName == name]
	created = not found
	if created:
		getattr(page, 'append' + style)(name, label=label)
		found = [p for p in comp.customPars if p.tupletName == name]
	elif found[0].style not in _STYLE_FAMILY.get(style, (style,)):
		report.append('%s.%s is %s, snippet wants %s: left as is' % (comp.path, name, found[0].style, style))
		return found
	found.sort(key=lambda p: p.vecIndex)
	defaults = default if isinstance(default, (list, tuple)) else [default] * len(found)
	for p, d in zip(found, defaults):
		p.label = label
		p.help = help_
		p.readOnly = read_only
		if menu is not None:   # (names, labels), set before the default, which must be one of them
			p.menuNames, p.menuLabels = menu
		if d is not None:
			p.default = d
			if created:
				p.val = d
		if norm is not None:
			p.normMin, p.normMax = norm
		if expr is not None:
			p.defaultExpr = expr
			p.defaultMode = ParMode.EXPRESSION
			if created:
				p.expr = expr
				p.mode = ParMode.EXPRESSION
	return found


# --------------------------------------------------------------------------
# Snippet library
# --------------------------------------------------------------------------

def ensure_snippets(snippets_comp: COMP, report: list) -> list:
	"""One Text DAT per .glsl file, synced to the file. Returns the node snippet DATs."""
	codegen = op.Matx.op('core/codegen').module
	node_dats, keep = [], set()
	for rel_dir, is_lib in ((NODES_DIR, False), (LIB_DIR, True)):
		folder = os.path.join(project.folder, rel_dir)
		for f in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
			if not f.endswith('.glsl'):
				continue
			stem = f[:-5]
			name = ('lib_' + stem) if is_lib else stem
			d = snippets_comp.op(name)
			if d is None:
				d = snippets_comp.create(textDAT, name)
				report.append('created %s' % d.path)
			d.par.file = rel_dir + '/' + f
			d.par.syncfile = True
			d.par.language = 'glsl'
			keep.add(name)
			if not is_lib:
				t = codegen.parse_snippet(d.text)['type']
				if t != stem:
					report.append('%s: @type %s does not match the file name' % (f, t))
				node_dats.append(d)
	for d in snippets_comp.findChildren(type=textDAT, maxDepth=1):
		if d.name not in keep:
			report.append('%s has no file any more: left in place' % d.path)
	_place_grid(sorted(snippets_comp.children, key=lambda o: o.name), COLUMNS)
	return node_dats


# --------------------------------------------------------------------------
# Node COMPs
# --------------------------------------------------------------------------

def _ensure_script(comp: COMP, name: str, callbacks_expr: str) -> OP:
	s = comp.op(name)
	if s is None:
		s = comp.create(scriptDAT, name)
		for d in list(s.docked):   # the auto-created callbacks DAT; we share one in core/
			d.destroy()
	s.par.callbacks.expr = callbacks_expr
	return s


def _ensure_io(comp: COMP, op_type, name: str, order: int, label: str) -> OP:
	o = comp.op(name) or comp.create(op_type, name)
	o.par.connectorder = order
	if hasattr(o.par, 'label'):
		o.par.label = label
	return o


def ensure_node_comp(library: COMP, snip: dict, report: list) -> COMP:
	t = snip['type']
	comp = library.op(t)
	if comp is None:   # a renamed library node (NoiseTexture -> Noise) is still that type's node
		typed = [c for c in library.children
		         if c.isCOMP and c.par['Nodetype'] is not None and c.par.Nodetype.eval() == t]
		comp = sorted(typed, key=lambda c: c.name)[0] if typed else None
	if comp is None:
		comp = library.create(baseCOMP, t)
		report.append('created %s' % comp.path)
	return ensure_node_contents(comp, snip, report)


def ensure_node_contents(comp: COMP, snip: dict, report: list) -> COMP:
	"""Creates or updates the inside and parameters of a node COMP (the library one or a copy)."""
	t = snip['type']
	matx_page = _page(comp, 'Matx')
	_ensure_par(comp, matx_page, 'Nodetype', 'Str', report, 'Node Type',
	            'Snippet type this node evaluates (glsl/nodes/<type>.glsl). Set by the builder.',
	            default=t, read_only=True)
	comp.par.Nodetype.val = t
	_ensure_par(comp, matx_page, 'Editshader', 'Pulse', report, 'Edit Shader',
	            "Opens this node's GLSL snippet (glsl/nodes/%s.glsl) in the external text editor, by "
	            "pulsing Edit on its DAT in /matx/snippets. Saving the file updates every %s node." % (t, t))
	if snip['outs']:
		_ensure_par(comp, matx_page, 'Preview', 'Toggle', report, 'Preview',
		            "On: the node's viewer shows its %s output shaded on a plane, in a geometry viewer "
		            'you can pan and orbit. Off: no preview, nothing extra cooks.' % _label(snip['outs'][0][1]),
		            default=False)
	par_exec = comp.op('par_exec')
	if par_exec is None:
		par_exec = comp.op('preview_exec')   # its name before it also handled Editshader
		if par_exec is not None:
			par_exec.name = 'par_exec'
		else:
			par_exec = comp.create(parameterexecuteDAT, 'par_exec')
	par_exec.par.op = '..'   # watch the node COMP itself
	par_exec.par.pars = 'Preview Editshader'
	par_exec.par.custom = True
	par_exec.par.builtin = False
	par_exec.par.valuechange = True
	par_exec.par.onpulse = True
	par_exec.text = PAR_EXEC

	matx = op.Matx.op('core/matx').module
	inputs_page = _page(comp, 'Inputs')
	for (name, items) in snip['menus']:
		label = _label(name)
		_ensure_par(comp, inputs_page, matx.par_name(name), 'Menu', report, label,
		            '%s of this node. A constant compiled into the shader (changing it recompiles), '
		            'not an input socket.' % label,
		            default=items[0], menu=(items, [_label(i) for i in items]))
	choosable = [n for n in snip['uniforms'] if n not in snip['driven']]
	if choosable:
		_ensure_par(comp, inputs_page, 'Asuniform', 'Toggle', report, 'As Uniform',
		            'On: %s becomes a uniform on the GLSL MAT, so animating it does not recompile '
		            'the shader. Off: the value is baked into the shader as a literal.'
		            % ', '.join(_label(n) for n in choosable), default=False)
	for (ty, name, default, flavor) in snip['attribs']:
		label = _label(name)
		_ensure_par(comp, inputs_page, matx.par_name(name), 'Str', report, label,
		            'Name of the geometry attribute this node reads (a POP or SOP attribute such as '
		            'Tex, Color or a custom one). It is declared on the Attributes page of the Evaluate '
		            "Shader's GLSL MAT.%s" % (' For SOPs this is texture layer 0 (uv).' if flavor == 'texcoord' else ''),
		            default=default)
		if flavor == 'typed':
			types = ['float', 'vec2', 'vec3', 'vec4']
			_ensure_par(comp, inputs_page, matx.par_name(name) + 'type', 'Menu', report, label + ' Type',
			            "Size of the attribute. It must match the geometry's attribute, or the values "
			            'read are wrong.', default=ty, menu=(types, ['Float', 'Vec2', 'Vec3', 'Vec4']))
	for (ty, name) in snip['samplers']:
		label = _label(name)
		_ensure_par(comp, inputs_page, matx.par_name(name), 'TOP', report, label,
		            "TOP sampled by this node (a %s uniform bound on the Evaluate Shader's GLSL MAT)." % ty)
	ins, outs = [], []
	for i, (ty, name, default) in enumerate(snip['ins']):
		label = _label(name)
		ins.append(_ensure_io(comp, inDAT, 'in_' + name, i, label))
		if ty == 'closure' or isinstance(default, str):   # closures and attribute defaults: connector only
			continue
		help_ = '%s (%s) used when the %s input is not connected.' % (label, ty, label)
		if name in snip['driven']:
			help_ += (' Always a uniform on the GLSL MAT: the expression (%s by default) animates '
			          'it without recompiling the shader.' % snip['driven'][name])
		pars = _ensure_par(comp, inputs_page, matx.par_name(name), _par_style(ty, name), report, label,
		                   help_, default=default, norm=snip['ranges'].get(name) or _norm_range(default),
		                   expr=snip['driven'].get(name))
		# greyed out while a wire feeds the socket (in_<name> is connector i)
		enable = 'len(me.inputConnectors[%d].connections) == 0' % i
		for p in pars:
			if p.enableExpr != enable:
				p.enableExpr = enable
	_remove_stale(comp, 'in_', {o.name for o in ins}, report)

	sockets = [name for (_, name) in snip['outs']] or [None]
	scripts = []
	for i, sock in enumerate(sockets):
		sname = 'graph_' + sock if sock else 'graph'
		s = _ensure_script(comp, sname, NODE_CALLBACKS)
		o = _ensure_io(comp, outDAT, 'out_' + (sock or 'graph'), i, _label(sock) if sock else 'Graph')
		if not o.inputs or o.inputs[0] != s:
			s.outputConnectors[0].connect(o.inputConnectors[0])
		scripts.append(s)
		outs.append(o)
	_remove_stale(comp, 'graph', {s.name for s in scripts}, report)
	_remove_stale(comp, 'out_', {o.name for o in outs}, report)
	_place_columns([ins + [par_exec], scripts, outs])
	_place_manifest(comp)
	set_preview(comp, report)
	return comp


def _place_manifest(comp: COMP) -> None:
	"""Moves a node's TDFam manifest (dropped by TDFam at a fixed spot) under its other operators."""
	manifest = comp.op('FamManifest')
	others = [c for c in comp.children if c != manifest]
	if manifest is None or not others:
		return
	manifest.nodeX = 0
	manifest.nodeY = min(c.nodeY for c in others) - _snap(manifest.nodeHeight + 60)


PAR_EXEC = '''\
# Generated by core/td_builder.py: Preview shows or hides the node's preview, Edit Shader opens
# its snippet.
def onValueChange(par, prev):
	if par.name == 'Preview':
		op.Matx.op('core/td_builder').module.set_preview(par.owner)

def onPulse(par):
	if par.name == 'Editshader':
		op.Matx.op('core/td_builder').module.edit_shader(par.owner)
'''


def edit_shader(comp: COMP) -> None:
	"""Opens the snippet of a node COMP's type in the external editor (the DAT's Edit pulse)."""
	t = comp.par.Nodetype.eval()
	snippet = op.Matx.op('snippets').op(t)
	if snippet is None:
		raise ValueError('no snippet DAT for node type %r (press Build on /matx)' % t)
	snippet.par.edit.pulse()


def set_preview(comp: COMP, report: Optional[list] = None) -> None:
	"""Makes a node COMP's `preview` match its Preview toggle.

	On: a `preview` COMP inside the node, fed by the first output's graph, evaluates it like
	EvaluateShader and shades a plane with it in a Geometry COMP; the node's Operator Viewer points
	at that Geometry COMP and its viewer is turned on. Off: the COMP is destroyed,
	so a node that is not previewed costs nothing.
	"""
	report = report if report is not None else []
	preview = comp.op('preview')
	if comp.par['Preview'] is None or not comp.par.Preview.eval():
		if preview is not None:
			preview.destroy()
			comp.par.opviewer = ''
			comp.viewer = False
		return
	if preview is None:
		preview = comp.create(baseCOMP, 'preview')
		report.append('created %s' % preview.path)
	ensure_evaluate_contents(preview, report, material_out=False)
	geo = _ensure_preview_scene(preview)
	out = comp.op('out_' + _first_output(comp))
	src = out.inputs[0] if out is not None and out.inputs else None   # that output's graph Script DAT
	if src is not None and (not preview.inputs or preview.inputs[0] != src):
		src.outputConnectors[0].connect(preview.inputConnectors[0])
	outs = comp.findChildren(type=outDAT, name='out_*', maxDepth=1)
	if outs:   # a column right of the Out DATs, level with the first one
		preview.nodeX = _snap(max(o.nodeX + o.nodeWidth for o in outs) + GRID)
		preview.nodeY = max(o.nodeY for o in outs)
	# bind now: the DAT Executes were created this frame and miss the tables' first change
	bind_evaluate(preview)
	comp.par.opviewer = './preview/' + geo.name
	comp.viewer = True


def _first_output(comp: COMP) -> str:
	"""Socket of the node's first output connector (out_<socket> with connectorder 0)."""
	outs = sorted(comp.findChildren(type=outDAT, name='out_*', maxDepth=1),
	              key=lambda o: o.par.connectorder.eval())
	return outs[0].name[len('out_'):] if outs else 'graph'


def _ensure_preview_scene(preview: COMP) -> OP:
	"""A Geometry COMP holding a plane shaded by glsl_mat, right of it. Returns the Geometry COMP,
	whose viewer is the preview (interactive: pan, orbit and zoom with the viewer's own camera)."""
	geo = preview.op('geo1')
	if geo is None:
		geo = preview.create(geometryCOMP, 'geo1')
		for c in list(geo.children):   # the default torus renders unless removed
			c.destroy()
		plane = geo.create(rectangleSOP, 'plane')
		plane.render = plane.display = True
	geo.par.material = 'glsl_mat'
	mat = preview.op('glsl_mat')
	_place_columns([[geo]], _snap(mat.nodeX + mat.nodeWidth + GRID))
	return geo


SAMPLER_EXEC = '''\
# Generated by core/td_builder.py: binds the sampler uniforms of the generated shader on glsl_mat.
def onTableChange(dat):
	op.Matx.op('core/td_eval_callbacks').module.apply_samplers(dat, dat.parent().op('glsl_mat'))
'''

UNIFORM_EXEC = '''\
# Generated by core/td_builder.py: binds the value uniforms of the generated shader on glsl_mat.
def onTableChange(dat):
	op.Matx.op('core/td_eval_callbacks').module.apply_uniforms(dat, dat.parent().op('glsl_mat'))
'''

ATTRIB_EXEC = '''\
# Generated by core/td_builder.py: declares the geometry attributes of the generated shader on glsl_mat.
def onTableChange(dat):
	op.Matx.op('core/td_eval_callbacks').module.apply_attribs(dat, dat.parent().op('glsl_mat'))
'''


def ensure_evaluate_comp(library: COMP, report: list) -> COMP:
	comp = library.op('EvaluateShader')
	if comp is None:
		comp = library.create(baseCOMP, 'EvaluateShader')
		report.append('created %s' % comp.path)
	return ensure_evaluate_contents(comp, report)


def ensure_evaluate_contents(comp: COMP, report: list, material_out: bool = True) -> COMP:
	"""Creates or updates the inside of an EvaluateShader COMP (the library one or a copy).

	material_out adds an Out MAT `out1` fed by glsl_mat, so the generated material leaves the
	COMP on a connector (wire it to a Null MAT and point Geometry COMPs at that)."""
	src = _ensure_io(comp, inDAT, 'in_graph', 0, 'Surface')
	vertex = _ensure_script(comp, 'vertex', EVAL_CALLBACKS)
	pixel = _ensure_script(comp, 'pixel', EVAL_CALLBACKS)
	samplers = _ensure_script(comp, 'samplers', EVAL_CALLBACKS)
	uniforms = _ensure_script(comp, 'uniforms', EVAL_CALLBACKS)
	attribs = _ensure_script(comp, 'attribs', EVAL_CALLBACKS)
	mat = comp.op('glsl_mat')
	if mat is None:
		mat = comp.create(glslMAT, 'glsl_mat')
		for d in list(mat.docked):   # keep only the info DAT; the shaders come from vertex/pixel
			if d.type != 'info':
				d.destroy()
		# compile in a background thread, showing the previous shader meanwhile, so editing the
		# graph does not stall the frame; set once, so a user's own choice is kept
		mat.par.compilebehavior = 'threadedprevious'
	mat.par.vdat = 'vertex'
	mat.par.pdat = 'pixel'
	execs = []
	for ex_name, table, text in (('sampler_exec', 'samplers', SAMPLER_EXEC),
	                             ('uniform_exec', 'uniforms', UNIFORM_EXEC),
	                             ('attrib_exec', 'attribs', ATTRIB_EXEC)):
		ex = comp.op(ex_name)
		if ex is None:
			ex = comp.create(datexecuteDAT, ex_name)
			report.append('created %s' % ex.path)
		ex.par.dat = table
		ex.par.tablechange = True
		ex.text = text
		execs.append(ex)
	bind_evaluate(comp)
	out = None
	if material_out:
		out = _ensure_io(comp, outMAT, 'out1', 0, 'Material')
		if not out.inputs or out.inputs[0] != mat:
			mat.outputConnectors[0].connect(out.inputConnectors[0])
	_place_columns([[src], [vertex, pixel, samplers, uniforms, attribs], execs, [mat]]
	               + ([[out]] if out else []))
	for d in mat.docked:
		d.nodeX = mat.nodeX + (mat.nodeWidth - d.nodeWidth) / 2
		d.nodeY = mat.nodeY - d.nodeHeight - 30
	_place_manifest(comp)
	return comp


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

BUILD_EXEC = '''\
# Generated by core/td_builder.py: runs the builder when the Build pulse is pressed.
def onPulse(par):
	if par.name == 'Build':
		for line in op.Matx.op('core/td_builder').module.build_all(op.Matx):
			debug(line)
'''


def ensure_build_button(matx_comp: COMP, report: list) -> None:
	page = _page(matx_comp, 'Matx')
	_ensure_par(matx_comp, page, 'Build', 'Pulse', report, 'Build Nodes',
	            'Creates or updates the snippet DATs and node COMPs from glsl/nodes/*.glsl.')
	ex = matx_comp.op('build_exec')
	if ex is None:
		ex = matx_comp.create(parameterexecuteDAT, 'build_exec')
	ex.par.op = '..'   # watch matx_comp itself
	ex.par.pars = 'Build'
	ex.par.custom = True
	ex.par.builtin = False
	ex.par.valuechange = False
	ex.par.onpulse = True
	ex.text = BUILD_EXEC


def build_all(matx_comp: COMP) -> list:
	"""Creates or updates snippets/ and nodes/ inside matx_comp. Returns a report of changes."""
	report = []
	ensure_build_button(matx_comp, report)
	snippets = matx_comp.op('snippets') or matx_comp.create(baseCOMP, 'snippets')
	library = matx_comp.op('nodes') or matx_comp.create(baseCOMP, 'nodes')
	codegen = matx_comp.op('core/codegen').module
	comps, menu_info = [], {}
	for d in ensure_snippets(snippets, report):
		snip = codegen.parse_snippet(d.text)
		comp = ensure_node_comp(library, snip, report)
		comps.append(comp)
		menu_info[comp.name] = (_label(snip['type']), snip['category'])
	comp = ensure_evaluate_comp(library, report)
	comps.append(comp)
	menu_info[comp.name] = (_label(comp.name), 'Output')
	_place_grid(comps, COLUMNS)
	upgrade_copies(matx_comp, library, snippets, report)
	fam = ensure_fam(matx_comp, library, menu_info, report)
	_place_columns([[matx_comp.op('build_exec')], [matx_comp.op('core')], [snippets], [library],
	                [o for o in (fam, matx_comp.op('scratch')) if o is not None]])
	return report


def upgrade_copies(matx_comp: COMP, library: COMP, snippets: COMP, report: list) -> None:
	"""Brings every copy of a library node in the project up to date with its snippet, and every
	copy of EvaluateShader up to date with the builder: the same get-or-create as the library
	nodes, so parameter values and wires of sockets that still exist are kept."""
	codegen = matx_comp.op('core/codegen').module
	skip = ('/sys/', '/ui/', '/local/', library.path + '/')
	for comp in root.findChildren(type=baseCOMP):
		if (comp.path + '/').startswith(skip) or comp.name == 'preview':
			continue
		node_type = comp.par['Nodetype']
		if node_type is not None:
			snippet = snippets.op(str(node_type.eval()))
			if snippet is not None:
				ensure_node_contents(comp, codegen.parse_snippet(snippet.text), report)
		elif comp.op('in_graph') is not None and comp.op('glsl_mat') is not None and comp.op('pixel') is not None:
			ensure_evaluate_contents(comp, report)


# --------------------------------------------------------------------------
# TDFam: the library as the MATX operator family in the OP Create (TAB) menu
# --------------------------------------------------------------------------

FAM_TOX = 'third_party/TDFam/TDFam_create.tox'
FAM_NAME = 'MATX'


def ensure_fam(matx_comp: COMP, library: COMP, menu_info: dict, report: list) -> Optional[COMP]:
	"""Creates or updates matx_comp's `fam` TDFam component, which publishes every COMP in library.

	The component is loaded from FAM_TOX (vendored TDFam) when missing, named FAM_NAME and pointed
	at library. Its manifests are then deployed, each node's OpInfo gets the label and group in
	menu_info ({comp name: (label, group)}), and they are deployed again so the menu shows them.
	"""
	fam = matx_comp.op('fam')
	if fam is None:
		path = os.path.join(project.folder, FAM_TOX)
		if not os.path.isfile(path):
			report.append('no %s: the MATX family was not created' % FAM_TOX)
			return None
		fam = matx_comp.loadTox(path)
		fam.name = 'fam'
		fam.par.Family = FAM_NAME
		report.append('created %s from %s' % (fam.path, FAM_TOX))
	if fam.par.Opcomp.eval() != library:
		fam.par.Opcomp = matx_comp.relativePath(library)
	callbacks = ensure_fam_callbacks(matx_comp, report)
	if fam.par.Callbackdat.eval() != callbacks:
		fam.par.Callbackdat = fam.relativePath(callbacks)
	ext = fam.ext.OpFamExt   # TDFam reads Callbackdat only when its extension initializes
	if ext.callbackDat != callbacks:
		ext.callbackDat = callbacks
		ext.InvalidateCallbackCache()
	deploy = fam.ext.OpFamExt.onParEnsuremanifests   # the Ensure Manifests pulse's handler, run now
	deploy()
	for name, (label, group) in menu_info.items():
		dat = library.op(name + '/FamManifest/OpInfo')
		if dat is None:
			report.append('%s has no TDFam manifest' % name)
			continue
		info = json.loads(dat.text or '{}')
		wanted = dict(info, op_label=label, **({'op_group': group} if group else {}))
		if wanted != info:
			dat.text = json.dumps(wanted, indent=4)
		_place_manifest(library.op(name))
	deploy()
	reinstall_fam(fam, library, report)
	return fam


FAM_CALLBACKS = 'core/td_fam_callbacks.py'


def ensure_fam_callbacks(matx_comp: COMP, report: list) -> DAT:
	"""The family's callbacks DAT in matx_comp's core, synced to FAM_CALLBACKS (it turns Preview
	on for every placed node)."""
	core = matx_comp.op('core')
	d = core.op('td_fam_callbacks')
	if d is None:
		d = core.create(textDAT, 'td_fam_callbacks')
		d.nodeX, d.nodeY = 800, -200   # the free cell of core's 3-column grid, under td_builder
		report.append('created %s' % d.path)
	d.par.file = FAM_CALLBACKS
	d.par.syncfile = True
	d.par.language = 'python'
	return d


def reinstall_fam(fam: COMP, library: COMP, report: list) -> None:
	"""Turns fam's Install toggle off, then on, when a library node (a new one, say) is not in the
	family colour: installing is what gives TDFam's masters their colour. The flips are deferred
	a few frames so that the manifest deploy has settled, and the second is scheduled by the first
	(see uninstall_then_install) so that they land in different frames even when the build made
	TD drop frames: flipped in one frame, TDFam's Parameter Execute sees no change."""
	color = tuple(round(c, 3) for c in fam.parGroup.Color.eval()[:3])
	stale = [c.name for c in library.children
	         if c.isCOMP and tuple(round(x, 3) for x in c.color) != color]
	if not stale or not fam.par.Install.eval():
		return
	run("op.Matx.op('core/td_builder').module.uninstall_then_install(args[0])", fam, delayFrames=5)
	report.append('reinstalling %s for the family colour of %s' % (fam.path, ', '.join(stale)))


def uninstall_then_install(fam: COMP) -> None:
	"""Turns fam's Install toggle off now and back on two frames later."""
	fam.par.Install = False
	run('args[0].par.Install = True', fam, delayFrames=2)


def bind_evaluate(comp: COMP) -> None:
	"""Applies an EvaluateShader COMP's binding tables to its glsl_mat now. Its DAT Executes do
	this whenever a table changes, except for a change in the frame the COMP was created."""
	callbacks = op.Matx.op('core/td_eval_callbacks').module
	mat = comp.op('glsl_mat')
	callbacks.apply_samplers(comp.op('samplers'), mat)
	callbacks.apply_uniforms(comp.op('uniforms'), mat)
	callbacks.apply_attribs(comp.op('attribs'), mat)
