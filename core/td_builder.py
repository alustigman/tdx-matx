"""
Builds the tdx-matx library inside the `matx` COMP (op shortcut `Matx`) from the repo files.

	core/      Text DATs synced to core/*.py (created by hand once, see bootstrap in README)
	snippets/  one Text DAT per glsl/nodes/*.glsl (named after its @type) and per
	           glsl/lib/*.glsl (named lib_<name>), synced to the files
	nodes/     one node COMP per snippet, plus EvaluateShader

Run it with the Matx COMP's `Build` pulse, or `op.Matx.op('core/td_builder').module.build_all(op.Matx)`.
Re-running is safe: existing COMPs and the values of their parameters are kept; In/Out DATs and
parameters are added to match the snippet headers. Sockets that disappeared from a header lose
their DATs, but their parameters are only reported, never destroyed.
"""
import math
import os
import re

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

def _place_columns(columns: list) -> None:
	"""Places lists of ops as left-to-right columns, top-aligned, spaced by their real sizes."""
	x = 0
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


SPATIAL_WORDS = ('vector', 'normal', 'pos', 'uv', 'coord', 'offset', 'dir', 'tangent', 'scale')


def _par_style(type_: str, socket: str) -> str:
	"""vec3/vec4 sockets are colours (RGB/RGBA swatches) unless the name looks spatial."""
	spatial = any(w in socket.lower() for w in SPATIAL_WORDS)
	return {('float', False): 'Float', ('float', True): 'Float',
	        ('vec2', False): 'XY', ('vec2', True): 'XY',
	        ('vec3', False): 'RGB', ('vec3', True): 'XYZ',
	        ('vec4', False): 'RGBA', ('vec4', True): 'XYZW'}[(type_, spatial)]


# TD reports a tuplet's style by family: RGB reads RGBA, XY/XYZ read XYZW
_STYLE_FAMILY = {'RGB': ('RGB', 'RGBA'), 'XY': ('XY', 'XYZW'), 'XYZ': ('XYZ', 'XYZW')}


def _ensure_par(comp: COMP, page, name: str, style: str, report: list, label: str, help_: str,
                default=None, norm=None, read_only=False) -> list:
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
	if comp is None:
		comp = library.create(baseCOMP, t)
		report.append('created %s' % comp.path)
	matx_page = _page(comp, 'Matx')
	_ensure_par(comp, matx_page, 'Nodetype', 'Str', report, 'Node Type',
	            'Snippet type this node evaluates (glsl/nodes/<type>.glsl). Set by the builder.',
	            default=t, read_only=True)
	comp.par.Nodetype.val = t

	matx = op.Matx.op('core/matx').module
	inputs_page = _page(comp, 'Inputs')
	ins, outs = [], []
	for i, (ty, name, default) in enumerate(snip['ins']):
		label = _label(name)
		ins.append(_ensure_io(comp, inDAT, 'in_' + name, i, label))
		if ty == 'closure':
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
	_place_columns([ins, scripts, outs])
	return comp


def ensure_evaluate_comp(library: COMP, report: list) -> COMP:
	comp = library.op('EvaluateShader')
	if comp is None:
		comp = library.create(baseCOMP, 'EvaluateShader')
		report.append('created %s' % comp.path)
	src = _ensure_io(comp, inDAT, 'in_graph', 0, 'Graph')
	vertex = _ensure_script(comp, 'vertex', EVAL_CALLBACKS)
	pixel = _ensure_script(comp, 'pixel', EVAL_CALLBACKS)
	mat = comp.op('glsl_mat')
	if mat is None:
		mat = comp.create(glslMAT, 'glsl_mat')
		for d in list(mat.docked):   # keep only the info DAT; the shaders come from vertex/pixel
			if d.type != 'info':
				d.destroy()
	mat.par.vdat = 'vertex'
	mat.par.pdat = 'pixel'
	_place_columns([[src], [vertex, pixel], [mat]])
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
	comps = []
	for d in ensure_snippets(snippets, report):
		comps.append(ensure_node_comp(library, codegen.parse_snippet(d.text), report))
	comps.append(ensure_evaluate_comp(library, report))
	_place_grid(comps, COLUMNS)
	_place_columns([[matx_comp.op('build_exec')], [matx_comp.op('core')], [snippets], [library]])
	return report
