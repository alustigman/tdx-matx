"""
Script DAT callbacks for the EvaluateShader COMP: the DAT named `vertex` or `pixel` outputs that
stage of codegen.generate() for the graph arriving in the COMP's `in_graph` In DAT, and the DAT
named `samplers` outputs a (name, top) table of the sampler uniforms the pixel shader declares.
The COMP's `sampler_exec` DAT Execute calls apply_samplers() when that table changes, which binds
them on glsl_mat's Samplers page.

When the graph is missing or cannot be generated (for example it does not end in a
MaterialOutput node) the shader DATs output codegen.fallback() instead and report why. The GLSL
MAT must never receive empty source: TouchDesigner crashes cooking a rendered GLSL MAT whose
shader DATs are empty.
"""


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
		problem = 'Connect a MaterialOutput node to the Graph input'
	else:
		try:
			graph = matx.parse_graph(src.text)
			snippets, lib = load_library(op.Matx.op('snippets'))
			result = codegen.generate(graph, snippets, lib)
		except Exception as e:
			problem = '%s: %s' % (type(e).__name__, e)

	if scriptOp.name == 'samplers':
		# the shader DATs report the problem; an empty table unbinds every sampler
		scriptOp.textFormat = False
		scriptOp.appendRow(['name', 'top'])
		for row in (result['samplers'] if result else []):
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
