"""
Script DAT callbacks for the EvaluateShader COMP: the DAT named `vertex` or `pixel` outputs that
stage of codegen.generate() for the graph arriving in the COMP's `in_graph` In DAT.

When the graph is missing or cannot be generated (for example it does not end in a
MaterialOutput node) the DAT outputs codegen.fallback() instead and reports why. The GLSL MAT
must never receive empty source: TouchDesigner crashes cooking a rendered GLSL MAT whose shader
DATs are empty.
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
	src = scriptOp.parent().op('in_graph')
	if src is None or not src.text.strip():
		scriptOp.addWarning('Connect a MaterialOutput node to the Graph input')
		text = codegen.fallback()[scriptOp.name]
	else:
		try:
			graph = matx.parse_graph(src.text)
			snippets, lib = load_library(op.Matx.op('snippets'))
			text = codegen.generate(graph, snippets, lib)[scriptOp.name]
		except Exception as e:
			scriptOp.addError('%s: %s' % (type(e).__name__, e))
			text = codegen.fallback()[scriptOp.name]
	# text mode first: assigning .text to a table-mode DAT splits the shader into tab-separated cells
	scriptOp.textFormat = True
	scriptOp.text = text
