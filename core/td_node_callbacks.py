"""
Shared Script DAT callbacks for every generated node COMP (see td_builder.py).

The node COMP carries its type in the read-only `Nodetype` parameter; the Script DAT is named
`graph_<output socket>` (or `graph` for a node without outputs). The node's sockets come from
its snippet in op.Matx's `snippets` COMP, so editing a .glsl header re-cooks every node of that
type.
"""


def onCook(scriptOp: scriptDAT) -> None:
	core = op.Matx.op('core')
	matx = core.op('matx').module
	codegen = core.op('codegen').module
	comp = scriptOp.parent()
	node_type = comp.par.Nodetype.eval()
	snippet = op.Matx.op('snippets').op(node_type)
	if snippet is None:
		raise ValueError('no snippet DAT for node type %r' % node_type)
	spec = matx.spec_from_snippet(codegen.parse_snippet(snippet.text))
	name = scriptOp.name
	out_socket = name[len('graph_'):] if name.startswith('graph_') else None
	matx.build_node(scriptOp, spec, out_socket)
