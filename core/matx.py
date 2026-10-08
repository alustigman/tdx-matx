"""
Graph JSON helpers shared by every node's Script DAT.

Only `build_node` and `read_graph_dat` touch TouchDesigner objects; everything else
is plain Python and unit tested in tests/.

A node COMP is expected to contain:
  - an In DAT named `in_<socket>` per input socket (JSON text, empty if unconnected)
  - one Script DAT per output socket, calling build_node(scriptOp, NODE, out_socket)
and to carry one custom parameter per literal input, named after the socket with
underscores removed and capitalised (`base_color` -> `Basecolor`; vectors use TD
tuplets, e.g. Basecolorr/g/b).
"""
import json

VERSION = 1


class MatxError(Exception):
	pass


def empty_graph():
	return {'version': VERSION, 'nodes': {}, 'output': None}


def parse_graph(text):
	text = (text or '').strip()
	if not text:
		return empty_graph()
	g = json.loads(text)
	if g.get('version') != VERSION:
		raise MatxError('unsupported graph version %r' % g.get('version'))
	g.setdefault('nodes', {})
	return g


def dump_graph(graph):
	"""Compact single-line JSON (Script DAT .text strips newlines)."""
	return json.dumps(graph, separators=(',', ':'), sort_keys=True)


def merge_graphs(graphs):
	"""Union of the nodes of several graphs. Same id must mean same node."""
	merged = empty_graph()
	for g in graphs:
		for nid, node in g['nodes'].items():
			if nid in merged['nodes'] and merged['nodes'][nid] != node:
				raise MatxError('node id %r appears twice with different contents' % nid)
			merged['nodes'][nid] = node
	return merged


def make_node(spec, node_id, literals, upstream, out_socket=None):
	"""
	spec:      {'type': str, 'inputs': {socket: type}, 'outputs': {socket: type}}
	literals:  {socket: value} from the COMP's parameters
	upstream:  {socket: graph} parsed graph of each connected input (absent/empty = unconnected)
	Returns the graph including this node, with `output` -> [node_id, out_socket].
	"""
	outputs = list(spec.get('outputs', {}))
	if out_socket is None:
		out_socket = outputs[0] if outputs else None
	elif out_socket not in outputs:
		raise MatxError('%s has no output %r' % (spec['type'], out_socket))

	graphs, inputs, errors = [], {}, []
	for socket in spec['inputs']:
		g = upstream.get(socket)
		if g is not None and g.get('error'):
			errors.append(g['error'])
		elif g is not None and g.get('output'):
			graphs.append(g)
			src_id, src_sock = g['output']
			if src_sock is None:
				raise MatxError('%s.%s connected to a node without outputs' % (spec['type'], socket))
			inputs[socket] = [src_id, src_sock]
		elif socket in literals:
			inputs[socket] = literals[socket]
	merged = merge_graphs(graphs)
	merged['nodes'][node_id] = {'type': spec['type'], 'inputs': inputs}
	merged['output'] = [node_id, out_socket]
	if errors:
		merged['error'] = errors[0]   # first upstream failure wins; Evaluate Shader reports it
	return merged


# --------------------------------------------------------------------------
# TouchDesigner adapters
# --------------------------------------------------------------------------

def par_name(socket):
	return socket.replace('_', '').capitalize()


def read_literal(comp, socket, type_):
	"""Reads a node COMP's parameter for `socket`; None if the COMP has none (default applies)."""
	name = par_name(socket)
	pars = comp.pars(name + '*')
	pars = [p for p in pars if p.name == name or p.tupletName == name]
	if not pars:
		return None
	pars.sort(key=lambda p: p.vecIndex)
	vals = [p.eval() for p in pars]
	return vals[0] if type_ == 'float' else vals


def build_node(scriptOp, spec, out_socket=None):
	"""Standard onCook body for a node's Script DAT."""
	comp = scriptOp.parent()
	upstream, literals = {}, {}
	for socket, type_ in spec['inputs'].items():
		d = comp.op('in_' + socket)
		upstream[socket] = parse_graph(d.text) if d is not None and d.text.strip() else None
		if type_ != 'closure':
			v = read_literal(comp, socket, type_)
			if v is not None:
				literals[socket] = v
	try:
		g = make_node(spec, 'n%d' % comp.id, literals, upstream, out_socket)
	except (MatxError, ValueError) as e:
		g = empty_graph()
		g['error'] = '%s: %s' % (comp.path, e)
	scriptOp.clear()
	scriptOp.text = dump_graph(g)
	scriptOp.textFormat = True   # must be last: adding rows reverts to table
