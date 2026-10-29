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
		self.assertEqual(sorted(r['attributes']),
		                 ['camera_index', 'color', 'uv', 'world_normal', 'world_pos'])
		v, p = r['vertex'], r['pixel']
		self.assertIn('out Vertex', v)
		self.assertIn('} oVert;', v)
		self.assertIn('oVert.cameraIndex = TDCameraIndex();', v)
		self.assertIn('TDWritePickingValues();', v)
		self.assertIn('in Vertex', p)
		self.assertIn('flat int cameraIndex;', p)
		self.assertIn('} iVert;', p)
		self.assertNotIn('TDCameraIndex', p)
		self.assertIn('matx_PrincipledBSDF(', p)
		for call in ('#include <TDColorSpace>', 'TDCheckDiscard();',
		             'TDFog(finalColor, iVert.worldSpacePos.xyz, iVert.cameraIndex)',
		             'TDDither(finalColor)', 'TDAlphaTest(finalColor.a)',
		             'TDConvertColorSpace(outVal)', 'oFragColor[0] = TDOutputSwizzle(outVal)'):
			self.assertIn(call, p)
		o = r['order']
		self.assertLess(o.index('n_uv'), o.index('n_noise'))
		self.assertLess(o.index('n_mix'), o.index('n_bsdf'))
		self.assertEqual(o[-1], 'n_bsdf')
		self.assertIn('vec4 finalColor = vec4(n_bsdf_bsdf.radiance, n_bsdf_bsdf.alpha);', p)

	def test_unused_attribute_not_emitted(self):
		g = example()
		for k in ('n_uv', 'n_noise'):
			del g['nodes'][k]
		g['nodes']['n_mix']['inputs']['fac'] = 0.25
		r = codegen.generate(g, SNIPS, LIB)
		self.assertNotIn('oVert.uv', r['vertex'])
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

	def test_missing_or_bad_output(self):
		g = example()
		g['output'] = None
		with self.assertRaises(codegen.MatxError):
			codegen.generate(g, SNIPS, LIB)
		g['output'] = ['n_bsdf', 'nope']
		with self.assertRaisesRegex(codegen.MatxError, 'no output'):
			codegen.generate(g, SNIPS, LIB)

	def test_value_surface_is_emission(self):
		# a non-closure surface is shaded as emission, converted to vec4 like any link
		for out, ty, expected in ((['n_mix', 'result'], 'vec3', 'vec4(n_mix_result, 1.0)'),
		                          (['n_noise', 'fac'], 'float', 'vec4(vec3(n_noise_fac), 1.0)')):
			g = example()
			del g['nodes']['n_bsdf']
			g['output'] = out
			r = codegen.generate(g, SNIPS, LIB)
			self.assertIn('vec4 finalColor = %s;' % expected, r['pixel'], ty)
			self.assertNotIn('matx_PrincipledBSDF', r['pixel'])
			# fog still gets its attributes without a shading node
			self.assertIn('oVert.worldSpacePos = ', r['vertex'])
			self.assertIn('oVert.cameraIndex = ', r['vertex'])

	def test_upstream_error_reported(self):
		g = example()
		g['error'] = '/project1/foo: boom'
		with self.assertRaisesRegex(codegen.MatxError, 'boom'):
			codegen.generate(g, SNIPS, LIB)

	def test_fallback_is_complete(self):
		# EvaluateShader outputs this on any error; empty shaders crash TD's GLSL MAT
		fb = codegen.fallback()
		self.assertIn('gl_Position = TDWorldToProj', fb['vertex'])
		self.assertIn('TDWritePickingValues', fb['vertex'])
		self.assertIn('oFragColor[0] = TDOutputSwizzle', fb['pixel'])
		self.assertNotIn('iVert', fb['pixel'])

	def _sampler_graph(self, top='/project1/moviefilein1'):
		g = example()
		g['nodes']['n_tex'] = {'type': 'Sampler', 'inputs': {}, 'samplers': {'image': top} if top else {}}
		g['nodes']['n_mix']['inputs']['a'] = ['n_tex', 'color']
		return g

	def test_sampler_uniform_and_binding(self):
		r = codegen.generate(self._sampler_graph(), SNIPS, LIB)
		self.assertEqual(r['samplers'], [['sMatx_n_tex_image', '/project1/moviefilein1']])
		p = r['pixel']
		self.assertIn('uniform sampler2D sMatx_n_tex_image;', p)
		self.assertIn('matx_Sampler(sMatx_n_tex_image, iVert.uv, n_tex_color, n_tex_alpha);', p)
		self.assertLess(p.index('uniform sampler2D'), p.index('void matx_Sampler'))

	def test_sampler_without_top_fails(self):
		with self.assertRaisesRegex(codegen.MatxError, 'no TOP for sampler'):
			codegen.generate(self._sampler_graph(top=None), SNIPS, LIB)

	def test_attribute_default_adds_attribute(self):
		g = self._sampler_graph()
		for k in ('n_uv', 'n_noise'):
			del g['nodes'][k]
		g['nodes']['n_mix']['inputs']['fac'] = 0.5
		r = codegen.generate(g, SNIPS, LIB)
		self.assertIn('uv', r['attributes'])
		self.assertIn('oVert.uv = ', r['vertex'])
		g['nodes']['n_tex']['inputs']['vector'] = [0.5, 0.5, 0.0]
		r = codegen.generate(g, SNIPS, LIB)
		self.assertNotIn('uv', r['attributes'])

	def test_no_samplers_by_default(self):
		r = codegen.generate(example(), SNIPS, LIB)
		self.assertEqual(r['samplers'], [])
		self.assertNotIn('uniform sampler2D', r['pixel'])

	def _uniform_graph(self):
		g = example()
		g['nodes']['n_a']['inputs'] = {}
		g['nodes']['n_a']['uniforms'] = {'color': ['/demo/RGB1', 'Color']}
		g['nodes']['n_val'] = {'type': 'Value', 'inputs': {}, 'uniforms': {'value': ['/demo/Value1', 'Value']}}
		g['nodes']['n_bsdf']['inputs']['roughness'] = ['n_val', 'value_out']
		return g

	def test_uniform_inputs(self):
		r = codegen.generate(self._uniform_graph(), SNIPS, LIB)
		p = r['pixel']
		self.assertIn('uniform vec4 uMatx_n_a_color;', p)   # the Colors page feeds a vec4
		self.assertIn('uniform float uMatx_n_val_value;', p)
		self.assertIn('matx_RGB(uMatx_n_a_color.rgb, n_a_color_out);', p)
		self.assertIn('matx_Value(uMatx_n_val_value, n_val_value_out);', p)
		self.assertNotIn('0.05', p)   # n_a's old literal is gone
		self.assertEqual(sorted(r['uniforms']), [['uMatx_n_a_color', '/demo/RGB1', 'Color', 'color'],
		                                         ['uMatx_n_val_value', '/demo/Value1', 'Value', 'vector']])
		self.assertTrue(codegen.is_color('vec3', 'base_color'))
		self.assertFalse(codegen.is_color('vec3', 'vector'))
		self.assertFalse(codegen.is_color('float', 'value'))
		self.assertEqual(codegen.generate(example(), SNIPS, LIB)['uniforms'], [])

	def test_uniform_only_where_declared(self):
		g = self._uniform_graph()
		g['nodes']['n_mix']['uniforms'] = {'fac': ['/demo/Mix', 'Fac']}
		g['nodes']['n_mix']['inputs'].pop('fac')
		with self.assertRaisesRegex(codegen.MatxError, 'cannot be a uniform'):
			codegen.generate(g, SNIPS, LIB)
		with self.assertRaisesRegex(codegen.MatxError, '@uniform'):
			codegen.parse_snippet('// @type X\n// @in closure s\n// @uniform s\nvoid matx_X() {}')

	def _math_graph(self, menus=None):
		return {'version': 1, 'output': ['n_m', 'value'], 'nodes': {
			'n_m': {'type': 'Math', 'inputs': {'a': 0.25, 'b': 2.0}, 'menus': menus or {}}}}

	def test_menu_is_a_constant_argument(self):
		self.assertEqual(SNIPS['Math']['menus'][0][1][:3], ['add', 'subtract', 'multiply'])
		self.assertEqual([n for (_, n, _) in SNIPS['Math']['ins']], ['a', 'b'])   # no socket for the menu
		p = codegen.generate(self._math_graph({'operation': 'power'}), SNIPS, LIB)['pixel']
		self.assertIn('const int MATX_MATH_OPERATION_ADD = 0;', p)
		self.assertIn('const int MATX_MATH_OPERATION_POWER = 4;', p)
		self.assertIn('matx_Math(MATX_MATH_OPERATION_POWER, 0.25, 2.0, n_m_value);', p)
		self.assertLess(p.index('MATX_MATH_OPERATION_ADD = 0'), p.index('void matx_Math('))
		p = codegen.generate(self._math_graph(), SNIPS, LIB)['pixel']   # unset: first item
		self.assertIn('matx_Math(MATX_MATH_OPERATION_ADD, ', p)
		self.assertEqual(p.count('const int MATX_MATH_OPERATION_ADD'), 1)
		with self.assertRaisesRegex(codegen.MatxError, 'not a operation option'):
			codegen.generate(self._math_graph({'operation': 'bogus'}), SNIPS, LIB)
		self.assertNotIn('const int', codegen.generate(example(), SNIPS, LIB)['pixel'])

	def test_menu_recorded_on_node(self):
		spec = matx.spec_from_snippet(SNIPS['Math'])
		self.assertNotIn('operation', spec['inputs'])
		g = matx.make_node(spec, 'n1', {'a': 1.0}, {}, menus={'operation': 'sine', 'other': 'x'})
		self.assertEqual(g['nodes']['n1']['menus'], {'operation': 'sine'})
		self.assertNotIn('menus', matx.make_node(Graph.SPEC, 'n2', {}, {})['nodes']['n2'])

	def test_bad_snippet_headers(self):
		for bad in ('// @menu op', '// @menu op Add', '// @menu op a a', '// @menu a x y\n// @in float a'):
			with self.assertRaisesRegex(codegen.MatxError, '@menu'):
				codegen.parse_snippet('// @type X\n%s\nvoid matx_X() {}' % bad)
		with self.assertRaisesRegex(codegen.MatxError, '@sampler'):
			codegen.parse_snippet('// @type X\n// @sampler samplerCube s\nvoid matx_X() {}')
		with self.assertRaisesRegex(codegen.MatxError, 'neither'):
			codegen.parse_snippet('// @type X\n// @in vec3 v = bogus\nvoid matx_X() {}')


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

	def test_samplers_recorded_on_node(self):
		spec = matx.spec_from_snippet(SNIPS['Sampler'])
		self.assertEqual(spec['samplers'], {'image': 'sampler2D'})
		g = matx.make_node(spec, 'n1', {}, {}, samplers={'image': '/a/b', 'other': '/x'})
		self.assertEqual(g['nodes']['n1']['samplers'], {'image': '/a/b'})
		g = matx.make_node(spec, 'n1', {}, {}, samplers={'image': None})
		self.assertEqual(g['nodes']['n1']['samplers'], {})
		g = matx.make_node(self.SPEC, 'n2', {}, {})
		self.assertNotIn('samplers', g['nodes']['n2'])

	def test_uniform_replaces_literal_not_link(self):
		spec = matx.spec_from_snippet(SNIPS['Value'])
		self.assertEqual(spec['uniforms'], ['value'])
		g = matx.make_node(spec, 'n1', {'value': 0.3}, {}, uniforms={'value': ['/a/Value1', 'Value']})
		self.assertEqual(g['nodes']['n1'], {'type': 'Value', 'inputs': {},
		                                    'uniforms': {'value': ['/a/Value1', 'Value']}})
		up = matx.make_node(spec, 'n0', {'value': 1.0}, {})
		g = matx.make_node(spec, 'n1', {}, {'value': up}, uniforms={'value': ['/a/Value1', 'Value']})
		self.assertEqual(g['nodes']['n1']['inputs'], {'value': ['n0', 'value_out']})
		self.assertNotIn('uniforms', g['nodes']['n1'])

	def test_error_propagates_and_roundtrip(self):
		bad = {'version': 1, 'nodes': {}, 'output': None, 'error': 'x'}
		g = matx.make_node(self.SPEC, 'n2', {}, {'a': bad})
		self.assertEqual(g['error'], 'x')
		self.assertEqual(matx.parse_graph(matx.dump_graph(g)), g)
		self.assertNotIn('\n', matx.dump_graph(g))


if __name__ == '__main__':
	unittest.main()
