import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'core'))
import codegen
import matx

SNIPS, LIB = codegen.load_snippets(os.path.join(ROOT, 'glsl', 'nodes'), os.path.join(ROOT, 'glsl', 'lib'))


def example():
	with open(os.path.join(ROOT, 'examples', 'noise_pbr.json'), encoding='utf-8') as f:
		return json.load(f)


class Codegen(unittest.TestCase):
	def test_example_generates(self):
		r = codegen.generate(example(), SNIPS, LIB)
		self.assertEqual(sorted(r['attributes']), ['uv', 'world_normal', 'world_pos'])
		self.assertIn('out vec3 vUV;', r['vertex'])
		self.assertIn('in vec3 vWorldNormal;', r['pixel'])
		self.assertIn('matx_PrincipledBSDF(', r['pixel'])
		self.assertIn('fragColor = TDOutputSwizzle', r['pixel'])
		o = r['order']
		self.assertLess(o.index('n_uv'), o.index('n_noise'))
		self.assertLess(o.index('n_mix'), o.index('n_bsdf'))
		self.assertEqual(o[-1], 'n_out')

	def test_unused_attribute_not_emitted(self):
		g = example()
		for k in ('n_uv', 'n_noise'):
			del g['nodes'][k]
		g['nodes']['n_mix']['inputs']['fac'] = 0.25
		r = codegen.generate(g, SNIPS, LIB)
		self.assertNotIn('vUV', r['vertex'])
		self.assertNotIn('matx_NoiseTexture', r['pixel'])

	def test_conversion_and_literals(self):
		self.assertEqual(codegen.literal('vec3', 0.5), 'vec3(0.5, 0.5, 0.5)')
		self.assertEqual(codegen.literal('float', 1), '1.0')
		self.assertEqual(codegen.convert('x', 'float', 'vec3'), 'vec3(x)')
		self.assertEqual(codegen.convert('x', 'vec4', 'vec3'), '(x).xyz')

	def test_cycle(self):
		g = example()
		g['nodes']['n_a'] = {'type': 'MixColor', 'inputs': {'a': ['n_mix', 'result']}}
		g['nodes']['n_mix']['inputs']['a'] = ['n_a', 'result']
		with self.assertRaisesRegex(codegen.MatxError, 'cycle'):
			codegen.generate(g, SNIPS, LIB)

	def test_missing_output_and_wrong_root(self):
		g = example()
		g['output'] = None
		with self.assertRaises(codegen.MatxError):
			codegen.generate(g, SNIPS, LIB)
		g = example()
		g['output'] = ['n_mix', 'result']
		with self.assertRaisesRegex(codegen.MatxError, 'MaterialOutput'):
			codegen.generate(g, SNIPS, LIB)

	def test_closure_type_check(self):
		g = example()
		g['nodes']['n_out']['inputs']['surface'] = ['n_mix', 'result']
		with self.assertRaisesRegex(codegen.MatxError, 'closure'):
			codegen.generate(g, SNIPS, LIB)

	def test_upstream_error_reported(self):
		g = example()
		g['error'] = '/project1/foo: boom'
		with self.assertRaisesRegex(codegen.MatxError, 'boom'):
			codegen.generate(g, SNIPS, LIB)


class Graph(unittest.TestCase):
	SPEC = {'type': 'MixColor', 'inputs': {'fac': 'float', 'a': 'vec3', 'b': 'vec3'},
	        'outputs': {'result': 'vec3'}}

	def test_make_node_links_and_literals(self):
		up = matx.make_node({'type': 'RGB', 'inputs': {'color': 'vec3'}, 'outputs': {'color_out': 'vec3'}},
		                    'n1', {'color': [1, 0, 0]}, {})
		g = matx.make_node(self.SPEC, 'n2', {'fac': 0.3, 'a': [0, 0, 0]}, {'b': up})
		self.assertEqual(g['nodes']['n2']['inputs'],
		                 {'fac': 0.3, 'a': [0, 0, 0], 'b': ['n1', 'color_out']})
		self.assertEqual(g['output'], ['n2', 'result'])
		self.assertIn('n1', g['nodes'])

	def test_merge_conflict(self):
		a = {'version': 1, 'nodes': {'n1': {'type': 'A'}}}
		b = {'version': 1, 'nodes': {'n1': {'type': 'B'}}}
		with self.assertRaises(matx.MatxError):
			matx.merge_graphs([a, b])

	def test_diamond_merge_ok(self):
		root = matx.make_node({'type': 'Value', 'inputs': {}, 'outputs': {'value_out': 'float'}}, 'n0', {}, {})
		spec = {'type': 'Math', 'inputs': {'x': 'float'}, 'outputs': {'r': 'float'}}
		l = matx.make_node(spec, 'nl', {}, {'x': root})
		r = matx.make_node(spec, 'nr', {}, {'x': root})
		spec2 = {'type': 'Math2', 'inputs': {'x': 'float', 'y': 'float'}, 'outputs': {'r': 'float'}}
		g = matx.make_node(spec2, 'nm', {}, {'x': l, 'y': r})
		self.assertEqual(set(g['nodes']), {'n0', 'nl', 'nr', 'nm'})

	def test_error_propagates_and_roundtrip(self):
		bad = {'version': 1, 'nodes': {}, 'output': None, 'error': 'x'}
		g = matx.make_node(self.SPEC, 'n2', {}, {'a': bad})
		self.assertEqual(g['error'], 'x')
		self.assertEqual(matx.parse_graph(matx.dump_graph(g)), g)
		self.assertNotIn('\n', matx.dump_graph(g))


if __name__ == '__main__':
	unittest.main()
