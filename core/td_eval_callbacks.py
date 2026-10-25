"""
Script DAT callbacks for the EvaluateShader COMP: the DAT named `vertex` or `pixel` outputs that
stage of codegen.generate() for the graph arriving in the COMP's `in_graph` In DAT (the Surface
input: a shading node, or any value, shaded as emission). The DAT named `samplers` outputs a
(name, top) table of the sampler uniforms the pixel shader declares, and the DAT named `uniforms`
a (name, op, par, page) table of the value uniforms (Value/RGB nodes with As Uniform on). The
COMP's `sampler_exec` and `uniform_exec` DAT Executes call apply_samplers() / apply_uniforms()
when a table changes, which bind them on glsl_mat's Samplers, Colors and Vectors pages.

When the graph is missing or cannot be generated (for example a sampler has no TOP) the shader DATs output codegen.fallback() instead and report why. The GLSL
MAT must never receive empty source: TouchDesigner crashes cooking a rendered GLSL MAT whose
shader DATs are empty.
"""
from typing import Optional


# Script DATs that output a binding table instead of shader text: name -> header row
BINDING_TABLES = {'samplers': ['name', 'top'], 'uniforms': ['name', 'op', 'par', 'page']}


def load_library(snippets_comp: COMP) -> tuple:
	"""Parses every snippet DAT: node snippets by @type, `lib_<name>` DATs as helper libraries."""
	codegen = op.Matx.op('core/codegen').module
	snippets, lib = {}, {}
	for d in snippets_comp.findChildren(type=textDAT, maxDepth=1):
		if d.name.startswith('lib_'):
			lib[d.name[4:]] = d.text
		else:
			s = codegen.parse_snippet(d.text)
			snippets[s['type']] = s
	return snippets, lib


def onCook(scriptOp: scriptDAT) -> None:
	core = op.Matx.op('core')
	matx = core.op('matx').module
	codegen = core.op('codegen').module
	scriptOp.clear()
	result, problem = None, None
	src = scriptOp.parent().op('in_graph')
	if src is None or not src.text.strip():
		problem = 'Connect a shader or any node output to the Surface input'
	else:
		try:
			graph = matx.parse_graph(src.text)
			snippets, lib = load_library(op.Matx.op('snippets'))
			result = codegen.generate(graph, snippets, lib)
		except Exception as e:
			problem = '%s: %s' % (type(e).__name__, e)

	if scriptOp.name in BINDING_TABLES:
		# the shader DATs report the problem; an empty table unbinds everything
		scriptOp.textFormat = False
		scriptOp.appendRow(BINDING_TABLES[scriptOp.name])
		for row in (result[scriptOp.name] if result else []):
			scriptOp.appendRow(row)
		return

	if result is None:
		if src is None or not src.text.strip():
			scriptOp.addWarning(problem)
		else:
			scriptOp.addError(problem)
		text = codegen.fallback()[scriptOp.name]
	else:
		text = result[scriptOp.name]
	# text mode first: assigning .text to a table-mode DAT splits the shader into tab-separated cells
	scriptOp.textFormat = True
	scriptOp.text = text


def apply_samplers(table: DAT, mat: glslMAT) -> None:
	"""Makes mat's Samplers page match the (name, top) rows of table.

	The block count is derived from the graph, so extra blocks are removed (TD keeps at least
	one, left blank). TOPs are written as paths relative to mat. Unchanged values are not
	rewritten, so the MAT does not recook for nothing.
	"""
	rows = [(table[r, 0].val, table[r, 1].val) for r in range(1, table.numRows)]
	seq = mat.seq.sampler
	if seq.numBlocks != max(1, len(rows)):
		seq.numBlocks = max(1, len(rows))
	for i in range(seq.numBlocks):
		name, path = rows[i] if i < len(rows) else ('', '')
		top = op(path) if path else None
		values = {'name': name, 'top': mat.relativePath(top) if top is not None else ''}
		for key, val in values.items():
			par = mat.par['sampler%d%s' % (i, key)]
			if par.val != val:
				par.val = val


# uniform page -> (glsl_mat sequence, value parameter suffixes in component order, fewest blocks:
# TD keeps at least one block on both pages, left blank when unused)
UNIFORM_PAGES = {
	'vector': ('vec', ('valuex', 'valuey', 'valuez', 'valuew'), 1),
	'color':  ('color', ('rgbr', 'rgbg', 'rgbb', 'alpha'), 1),
}


def apply_uniforms(table: DAT, mat: glslMAT) -> None:
	"""Makes mat's Colors and Vectors pages match the (name, op, par, page) rows of table.

	Each block gets the uniform's name and, per component, an expression reading the node COMP's
	parameter (a path relative to mat), so animating the parameter only changes the uniform: the
	graph and the shader stay the same. Block counts are derived from the graph; unused blocks are
	blanked and unused components (a vec3 colour's alpha) go back to their constant default.
	Unchanged values and expressions are not rewritten.
	"""
	rows = [[table[r, c].val for c in range(4)] for r in range(1, table.numRows)]
	for page, (seq_name, suffixes, fewest) in UNIFORM_PAGES.items():
		page_rows = [r[:3] for r in rows if r[3] == page]
		seq = getattr(mat.seq, seq_name)
		if seq.numBlocks != max(fewest, len(page_rows)):
			seq.numBlocks = max(fewest, len(page_rows))
		for i in range(seq.numBlocks):
			name, path, tuplet = page_rows[i] if i < len(page_rows) else ('', '', '')
			_bind_block(mat, '%s%d' % (seq_name, i), suffixes, name, op(path) if path else None, tuplet)


def _bind_block(mat: glslMAT, prefix: str, suffixes: tuple, name: str, comp: Optional[COMP],
                tuplet: str) -> None:
	pars = sorted((p for p in comp.customPars if p.tupletName == tuplet),
	              key=lambda p: p.vecIndex) if comp is not None else []
	name_par = mat.par[prefix + 'name']
	if name_par.val != name:
		name_par.val = name
	rel = mat.relativePath(comp) if comp is not None else ''
	for j, suffix in enumerate(suffixes):
		par = mat.par[prefix + suffix]
		if j < len(pars):
			expr = 'op(%r).par.%s' % (rel, pars[j].name)
			if par.expr != expr:
				par.expr = expr
			if par.mode != ParMode.EXPRESSION:
				par.mode = ParMode.EXPRESSION
		elif par.mode != ParMode.CONSTANT or par.val != par.default:
			par.val = par.default   # also switches back to constant mode
