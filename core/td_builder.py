"""
Builds the tdx-matx library inside the `matx` COMP (op shortcut `Matx`) from the repo files.

	core/      Text DATs synced to core/*.py (created by hand once, see bootstrap in README)
	snippets/  one Text DAT per glsl/nodes/*.glsl (named after its @type) and per
	           glsl/lib/*.glsl (named lib_<name>), synced to the files
	nodes/     one node COMP per snippet, plus EvaluateShader

A node COMP gets an In DAT per @in socket, a Menu parameter per @menu (no socket: a shader
constant), a custom parameter per literal input (none for a
closure, nor for an input whose default is a vertex attribute such as `uv`), a TOP parameter per
@sampler, an `Asuniform` toggle when the snippet declares @uniform inputs, and a Script DAT + Out
DAT per @out socket. A node with outputs also gets a `Preview` toggle on its first page (Matx) and
a `preview_exec` that creates or removes its `preview` COMP (see set_preview).

Run it with the Matx COMP's `Build` pulse, or `op.Matx.op('core/td_builder').module.build_all(op.Matx)`.
Re-running is safe: existing COMPs and the values of their parameters are kept; In/Out DATs and
parameters are added to match the snippet headers. Sockets that disappeared from a header lose
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


def _label(socket: str) -> str:
	"""base_color -> Base Color, emissionColor -> Emission Color."""
	words = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', socket).replace('_', ' ').split()
	return ' '.join(w[:1].upper() + w[1:] for w in words)


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
                default=None, norm=None, read_only=False, menu=None) -> list:
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
	preview_exec = None
	if snip['outs']:
		_ensure_par(comp, matx_page, 'Preview', 'Toggle', report, 'Preview',
		            "On: the node's viewer shows its %s output shaded on a plane, in a geometry viewer "
		            'you can pan and orbit. Off: no preview, nothing extra cooks.' % _label(snip['outs'][0][1]),
		            default=False)
		preview_exec = comp.op('preview_exec')
		if preview_exec is None:
			preview_exec = comp.create(parameterexecuteDAT, 'preview_exec')
		preview_exec.par.op = '..'   # watch the node COMP itself
		preview_exec.par.pars = 'Preview'
		preview_exec.par.custom = True
		preview_exec.par.builtin = False
		preview_exec.par.valuechange = True
		preview_exec.par.onpulse = False
		preview_exec.text = PREVIEW_EXEC

	matx = op.Matx.op('core/matx').module
	inputs_page = _page(comp, 'Inputs')
	for (name, items) in snip['menus']:
		label = _label(name)
		_ensure_par(comp, inputs_page, matx.par_name(name), 'Menu', report, label,
		            '%s of this node. A constant compiled into the shader (changing it recompiles), '
		            'not an input socket.' % label,
		            default=items[0], menu=(items, [_label(i) for i in items]))
	if snip['uniforms']:
		_ensure_par(comp, inputs_page, 'Asuniform', 'Toggle', report, 'As Uniform',
		            'On: %s becomes a uniform on the GLSL MAT, so animating it does not recompile '
		            'the shader. Off: the value is baked into the shader as a literal.'
		            % ', '.join(_label(n) for n in snip['uniforms']), default=False)
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
		_ensure_par(comp, inputs_page, matx.par_name(name), _par_style(ty, name), report, label,
		            '%s (%s) used when the %s input is not connected.' % (label, ty, label),
		            default=default, norm=_norm_range(default))
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
	_place_columns([ins + ([preview_exec] if preview_exec else []), scripts, outs])
	set_preview(comp, report)
	return comp


PREVIEW_EXEC = '''\
# Generated by core/td_builder.py: shows or hides the node's preview when Preview changes.
def onValueChange(par, prev):
	op.Matx.op('core/td_builder').module.set_preview(par.owner)
'''


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
	callbacks = op.Matx.op('core/td_eval_callbacks').module
	callbacks.apply_samplers(preview.op('samplers'), preview.op('glsl_mat'))
	callbacks.apply_uniforms(preview.op('uniforms'), preview.op('glsl_mat'))
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
	mat = comp.op('glsl_mat')
	if mat is None:
		mat = comp.create(glslMAT, 'glsl_mat')
		for d in list(mat.docked):   # keep only the info DAT; the shaders come from vertex/pixel
			if d.type != 'info':
				d.destroy()
	mat.par.vdat = 'vertex'
	mat.par.pdat = 'pixel'
	execs = []
	for ex_name, table, text in (('sampler_exec', 'samplers', SAMPLER_EXEC),
	                             ('uniform_exec', 'uniforms', UNIFORM_EXEC)):
		ex = comp.op(ex_name)
		if ex is None:
			ex = comp.create(datexecuteDAT, ex_name)
			report.append('created %s' % ex.path)
		ex.par.dat = table
		ex.par.tablechange = True
		ex.text = text
		execs.append(ex)
	callbacks = op.Matx.op('core/td_eval_callbacks').module
	callbacks.apply_samplers(samplers, mat)
	callbacks.apply_uniforms(uniforms, mat)
	out = None
	if material_out:
		out = _ensure_io(comp, outMAT, 'out1', 0, 'Material')
		if not out.inputs or out.inputs[0] != mat:
			mat.outputConnectors[0].connect(out.inputConnectors[0])
	_place_columns([[src], [vertex, pixel, samplers, uniforms], execs, [mat]] + ([[out]] if out else []))
	for d in mat.docked:
		d.nodeX = mat.nodeX + (mat.nodeWidth - d.nodeWidth) / 2
		d.nodeY = mat.nodeY - d.nodeHeight - 30
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
	fam = ensure_fam(matx_comp, library, menu_info, report)
	_place_columns([[matx_comp.op('build_exec')], [matx_comp.op('core')], [snippets], [library],
	                [o for o in (fam, matx_comp.op('scratch')) if o is not None]])
	return report


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
		manifest = dat.parent()   # TDFam drops it at a fixed spot: move it under the node's ops
		others = [c for c in library.op(name).children if c != manifest]
		manifest.nodeX = 0
		manifest.nodeY = min(c.nodeY for c in others) - _snap(manifest.nodeHeight + 60) if others else 0
	deploy()
	return fam
