"""Shader test bench helpers, run inside TouchDesigner: /matx/scratch/rig/harness is synced to this file.

The rig renders a POP plane (left) and a SOP plane (right) with the material of eval1, an
EvaluateShader fed by the graph_json DAT. From a textport or a script:

	H = op.Matx.op('scratch/rig/harness').module
	H.compile_all()                       # {type: problems} for every snippet, {} when all compile
	H.compile_type('VoronoiTexture', menus={'feature': 'f2'}, out='color')
	H.sheet([(label, type, kwargs), ...], 'C:/tmp/sheet.png')   # contact sheet of rendered variants (POP plane)
	H.use_ball(True)                      # a sphere instead of the SOP plane
"""
import json


def set_graph(graph):
	rig = me.parent()
	rig.op('graph_json').text = json.dumps(graph)
	ev = rig.op('eval1')
	for n in ('vertex', 'pixel', 'samplers', 'uniforms', 'attribs'):
		ev.op(n).cook(force=True)
	cb = op.Matx.op('core/td_eval_callbacks').module
	mat = ev.op('glsl_mat')
	cb.apply_samplers(ev.op('samplers'), mat)
	cb.apply_uniforms(ev.op('uniforms'), mat)
	cb.apply_attribs(ev.op('attribs'), mat)
	rig.op('render1').cook(force=True)
	problems = [str(e) for n in ('vertex', 'pixel') for e in [ev.op(n).errors()] if e]
	info = ev.op('glsl_mat_info').text
	problems += [l for l in info.splitlines() if 'ERROR' in l or 'WARNING' in l]
	if not problems and (info.count('Compiled Successfully') < 2 or 'Linked Successfully' not in info):
		problems.append('not compiled: ' + info[:200])
	if mat.warnings():
		problems.append(mat.warnings())
	return problems


def node_graph(node_type, menus=None, inputs=None, out=None, extra=None):
	"""A graph of one node with default inputs. extra: {id: node} of other nodes to link to."""
	cg = op.Matx.op('core/codegen').module
	snip = cg.parse_snippet(op.Matx.op('snippets').op(node_type).text)
	node = {'type': node_type, 'inputs': dict(inputs or {}), 'menus': dict(menus or {})}
	if snip['samplers']:
		node['samplers'] = {name: me.parent().op('ramp_test').path for (_, name) in snip['samplers']}
	nodes = dict(extra or {})
	nodes['n1'] = node
	return {'version': 1, 'nodes': nodes, 'output': ['n1', out or snip['outs'][0][1]]}


def compile_type(node_type, **kw):
	return set_graph(node_graph(node_type, **kw))


def compile_all(types=None):
	"""{type: problems} for every snippet (first output, default menus)."""
	names = types or sorted(d.name for d in op.Matx.op('snippets').children if not d.name.startswith('lib_'))
	bad = {}
	for t in names:
		p = compile_type(t)
		if p:
			bad[t] = p[:4]
	return bad


def sample(points=((0.25, 0.75), (0.5, 0.5), (0.8, 0.2))):
	"""RGB of the POP plane (left) and SOP plane (right) at the given plane uv positions."""
	a = me.parent().op('render1').numpyArray()
	h, w = a.shape[:2]
	def px(u, v):
		return [round(float(x), 3) for x in a[int(v * h), int(u * w)][:3]]
	return {'pop': [px(0.056 + u * 0.403, 0.1 + v * 0.8) for (u, v) in points],
	        'sop': [px(0.54 + u * 0.403, 0.1 + v * 0.8) for (u, v) in points]}


def sheet(variants, path, cols=4, out=None):
	"""Renders each (label, node type, kwargs) on the POP plane and saves them as one image."""
	import numpy as np, cv2
	tiles, problems = [], {}
	for (label, node_type, kw) in variants:
		kw = dict(kw)
		if out and 'out' not in kw:
			kw['out'] = out
		p = compile_type(node_type, **kw)
		if p:
			problems[label] = p[:3]
		a = me.parent().op('render1').numpyArray()
		hh, ww = a.shape[:2]
		crop = a[int(0.1 * hh):int(0.9 * hh), int(0.056 * ww):int(0.459 * ww), :3]
		img = (np.clip(np.flipud(crop), 0, 1) * 255).astype(np.uint8)[:, :, ::-1].copy()
		cv2.putText(img, label, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3)
		cv2.putText(img, label, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
		tiles.append(img)
	rows = []
	blank = np.zeros_like(tiles[0])
	for i in range(0, len(tiles), cols):
		row = tiles[i:i + cols]
		row += [blank] * (cols - len(row))
		rows.append(np.hstack(row))
	cv2.imwrite(path, np.vstack(rows))
	return problems


def use_ball(on=True):
	"""Shows a sphere (on) or the plane (off) as the SOP geometry on the right: lighting nodes
	(Fresnel, Toon BSDF, Bump) read better on a sphere."""
	geo = me.parent().op('geo_sop')
	geo.op('sphere_ball').render = geo.op('sphere_ball').display = bool(on)
	geo.op('rectangle_plane').render = geo.op('rectangle_plane').display = not on
