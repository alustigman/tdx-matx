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
		self.assertIn('matx_PBR(', p)
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
			self.assertNotIn('matx_PBR', r['pixel'])
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
		self.assertEqual([n for (_, n, _) in SNIPS['Math']['ins']], ['a', 'b', 'c'])   # no socket for the menu
		p = codegen.generate(self._math_graph({'operation': 'power'}), SNIPS, LIB)['pixel']
		self.assertIn('const int MATX_MATH_OPERATION_ADD = 0;', p)
		self.assertIn('const int MATX_MATH_OPERATION_POWER = 4;', p)
		self.assertIn('matx_Math(MATX_MATH_OPERATION_POWER, 0.25, 2.0, 0.5, n_m_value);', p)
		self.assertLess(p.index('MATX_MATH_OPERATION_ADD = 0'), p.index('void matx_Math('))
		p = codegen.generate(self._math_graph(), SNIPS, LIB)['pixel']   # unset: first item
		self.assertIn('matx_Math(MATX_MATH_OPERATION_ADD, ', p)
		self.assertEqual(p.count('const int MATX_MATH_OPERATION_ADD'), 1)
		with self.assertRaisesRegex(codegen.MatxError, 'not a operation option'):
			codegen.generate(self._math_graph({'operation': 'bogus'}), SNIPS, LIB)
		g = example()   # the constants are only declared for the node types in use
		g['output'] = ['n_a', 'color_out']
		self.assertNotIn('const int', codegen.generate(g, SNIPS, LIB)['pixel'])

	def test_vector_nodes(self):
		g = {'version': 1, 'output': ['n_vm', 'vector'], 'nodes': {
			'n_xyz': {'type': 'XYZ', 'inputs': {}, 'uniforms': {'vector': ['/demo/XYZ1', 'Vector']}},
			'n_sep': {'type': 'SeparateXYZ', 'inputs': {'vector': ['n_xyz', 'vector_out']}},
			'n_comb': {'type': 'CombineXYZ', 'inputs': {'x': ['n_sep', 'z'], 'y': ['n_sep', 'y'], 'z': 1.0}},
			'n_vm': {'type': 'VectorMath', 'menus': {'operation': 'cross_product'},
			         'inputs': {'vector_a': ['n_xyz', 'vector_out'], 'vector_b': ['n_comb', 'vector']}}}}
		r = codegen.generate(g, SNIPS, LIB)
		p = r['pixel']
		self.assertIn('uniform vec3 uMatx_n_xyz_vector;', p)   # the Vectors page, not the Colors page
		self.assertEqual(r['uniforms'], [['uMatx_n_xyz_vector', '/demo/XYZ1', 'Vector', 'vector']])
		self.assertIn('matx_CombineXYZ(n_sep_z, n_sep_y, 1.0, n_comb_vector);', p)
		self.assertIn('matx_VectorMath(MATX_VECTORMATH_OPERATION_CROSS_PRODUCT, n_xyz_vector_out, '
		              'n_comb_vector, vec3(0.0, 0.0, 0.0), 1.0, n_vm_vector, n_vm_value);', p)
		self.assertEqual([n for (_, n, _) in SNIPS['VectorMath']['ins']],
		                 ['vector_a', 'vector_b', 'vector_c', 'scale'])

	def test_geometry_attributes(self):
		g = {'version': 1, 'output': ['n_mix', 'result'], 'nodes': {
			'n_uv': {'type': 'TexCoord', 'inputs': {}},
			'n_uv2': {'type': 'TexCoord', 'inputs': {}, 'attribs': {'attribute': ['Tex2', 'vec3']}},
			'n_c': {'type': 'Attribute', 'inputs': {}},
			'n_f': {'type': 'Attribute', 'inputs': {}, 'attribs': {'attribute': ['Age', 'float']}},
			'n_f2': {'type': 'Attribute', 'inputs': {}, 'attribs': {'attribute': ['Age', 'float']}},
			'n_add': {'type': 'VectorMath', 'inputs': {'vector_a': ['n_uv', 'uv'], 'vector_b': ['n_uv2', 'uv'],
			                                           'scale': ['n_f2', 'fac']}},
			'n_mix': {'type': 'MixColor', 'inputs': {'fac': ['n_f', 'fac'], 'a': ['n_c', 'color'],
			                                         'b': ['n_add', 'vector']}}}}
		r = codegen.generate(g, SNIPS, LIB)
		v, p = r['vertex'], r['pixel']
		# Tex read as a texture coordinate is the built-in uv; TDTexCoord(0u) is empty for POPs
		self.assertIn('oVert.uv = TDInstanceTexCoord(TDTexAttrib_Tex(0u));', v)
		self.assertIn('oVert.tex_Tex2 = TDInstanceTexCoord(TDTexAttrib_Tex2(0u));', v)
		self.assertIn('oVert.attr_Color = TDAttrib_Color();', v)
		self.assertEqual(v.count('oVert.attr_Age = TDAttrib_Age();'), 1)   # shared by both nodes
		self.assertIn('\tvec4 attr_Color;', p)
		self.assertIn('\tfloat attr_Age;', p)
		self.assertIn('matx_TexCoord(iVert.uv, n_uv_uv, n_uv_window);', p)
		self.assertIn('matx_Attribute(vec4(iVert.attr_Age), n_f_color', p)   # typed: converted to vec4
		self.assertEqual(sorted(r['attribs']), [['Age', 'float'], ['Color', 'float4'],
		                                        ['Tex', 'float3'], ['Tex2', 'float3']])
		self.assertEqual(codegen.generate(example(), SNIPS, LIB)['attribs'], [['Tex', 'float3']])
		g['nodes']['n_f']['attribs'] = {'attribute': ['Color', 'vec3']}
		with self.assertRaisesRegex(codegen.MatxError, 'Color is read as'):
			codegen.generate(g, SNIPS, LIB)
		g['nodes']['n_f']['attribs'] = {'attribute': ['not a name', 'vec3']}
		with self.assertRaisesRegex(codegen.MatxError, 'not an attribute name'):
			codegen.generate(g, SNIPS, LIB)
		g['nodes']['n_f']['attribs'] = {'attribute': ['Age', 'float']}
		g['nodes']['n_uv']['attribs'] = {'attribute': ['Tex', 'vec2']}   # not typed: fixed size
		with self.assertRaisesRegex(codegen.MatxError, 'cannot be read as vec2'):
			codegen.generate(g, SNIPS, LIB)

	def test_attribs_recorded_on_node(self):
		spec = matx.spec_from_snippet(SNIPS['Attribute'])
		self.assertEqual(spec['attribs'], {'attribute': ('vec4', 'Color', 'typed')})
		g = matx.make_node(spec, 'n1', {}, {}, attribs={'attribute': ['Foo', 'vec3'], 'other': ['X', 'float']})
		self.assertEqual(g['nodes']['n1']['attribs'], {'attribute': ['Foo', 'vec3']})
		self.assertNotIn('attribs', matx.make_node(Graph.SPEC, 'n2', {}, {})['nodes']['n2'])

	def test_every_snippet_generates(self):
		"""Each node type alone, on defaults, through every output."""
		for t, sn in SNIPS.items():
			nodes = {'n_em': {'type': 'EmissionShader', 'inputs': {}}}
			node = {'type': t, 'inputs': {name: ['n_em', 'bsdf'] for (ty, name, _) in sn['ins'] if ty == 'closure'},
			        'samplers': {name: '/top' for (_, name) in sn['samplers']}}
			nodes['n1'] = node
			for (_, out) in sn['outs']:
				r = codegen.generate({'version': 1, 'nodes': nodes, 'output': ['n1', out]}, SNIPS, LIB)
				self.assertIn('matx_%s(' % t, r['pixel'], t)

	def test_unconnected_closure_is_empty(self):
		g = {'version': 1, 'output': ['n1', 'shader'], 'nodes': {
			'n_em': {'type': 'EmissionShader', 'inputs': {}},
			'n1': {'type': 'MixShader', 'inputs': {'shader_a': ['n_em', 'bsdf']}}}}
		p = codegen.generate(g, SNIPS, LIB)['pixel']
		self.assertIn('matx_MixShader(0.5, n_em_bsdf, MatxClosure(vec3(0.0), 0.0), n1_shader);', p)

	def test_lib_requires_are_included_once_in_order(self):
		g = {'version': 1, 'output': ['n1', 'shader'], 'nodes': {
			'n_a': {'type': 'DiffuseBSDF', 'inputs': {}}, 'n_b': {'type': 'GlossyBSDF', 'inputs': {}},
			'n1': {'type': 'AddShader', 'inputs': {'shader_a': ['n_a', 'bsdf'], 'shader_b': ['n_b', 'bsdf']}}}}
		r = codegen.generate(g, SNIPS, LIB)
		p = r['pixel']
		self.assertEqual(p.count('vec3 matx_view_vector()'), 1)
		self.assertEqual(p.count('vec3 matx_pbr_lighting('), 1)
		self.assertLess(p.index('vec3 matx_view_vector()'), p.index('vec3 matx_pbr_lighting('))   # lighting requires view
		self.assertLess(p.index('vec3 matx_pbr_lighting('), p.index('void matx_DiffuseBSDF('))
		self.assertIn('world_normal', r['attributes'])   # the unconnected normal reads the attribute

	def test_driven_uniform(self):
		spec = matx.spec_from_snippet(SNIPS['Time'])
		self.assertEqual((spec['uniforms'], spec['driven']), (['time'], ['time']))
		self.assertEqual(matx.spec_from_snippet(SNIPS['Value'])['driven'], [])

	def test_enable_conditions(self):
		snip = codegen.parse_snippet(
			'// @type X\n// @menu mode a b c\n// @menu other on off\n// @in float x\n// @in float y\n'
			'// @enable x y if mode b c\n// @enable y unless other off\n// @enable other if mode a\n'
			'void matx_X() {}')
		self.assertEqual(snip['enables'], {'x': [('mode', ['b', 'c'], True)],
		                                   'y': [('mode', ['b', 'c'], True), ('other', ['off'], False)],
		                                   'other': [('mode', ['a'], True)]})
		self.assertEqual(SNIPS['Math']['enables']['c'][0][0], 'operation')
		self.assertIn('4d', SNIPS['NoiseTexture']['enables']['w'][0][1])
		for bad in ('// @enable x if mode', '// @enable x when mode a', '// @enable z if mode a',
		            '// @enable x if nomenu a', '// @enable x if mode d', '// @enable mode if mode a',
		            '// @enable v if mode a'):
			with self.assertRaisesRegex(codegen.MatxError, '@enable'):
				codegen.parse_snippet('// @type X\n// @menu mode a b c\n// @in float x\n// @in closure v\n'
				                      '%s\nvoid matx_X() {}' % bad)

	def test_socket_kinds(self):
		kind = codegen.socket_kind
		self.assertEqual([kind(SNIPS['Mapping'], 'vec3', 'result'), kind(SNIPS['MixColor'], 'vec3', 'result'),
		                  kind(SNIPS['NoiseTexture'], 'float', 'fac'),
		                  kind(SNIPS['PBR'], 'closure', 'bsdf'), kind(SNIPS['Mapping'], 'vec3', 'vector')],
		                 ['vector', 'color', 'float', 'shader', 'vector'])
		self.assertEqual(SNIPS['TexCoord']['kinds'], {'window': 'vector'})
		with self.assertRaisesRegex(codegen.MatxError, '@out'):
			codegen.parse_snippet('// @type X\n// @out float f vector\nvoid matx_X() {}')

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
		for bad in ('// @attrib vec3 a', '// @attrib vec2 a = Tex texcoord', '// @attrib vec3 a = Tex other',
		            '// @attrib closure a = Tex', '// @in float a\n// @attrib vec3 a = Tex'):
			with self.assertRaisesRegex(codegen.MatxError, '@attrib'):
				codegen.parse_snippet('// @type X\n%s\nvoid matx_X() {}' % bad)
		with self.assertRaisesRegex(codegen.MatxError, '@uniform'):
			codegen.parse_snippet('// @type X\n// @in float t\n// @uniform t =\nvoid matx_X() {}')
		s = codegen.parse_snippet('// @type X\n// @in float t = 0\n// @uniform t = absTime.seconds\n'
		                          '// @menu dims 3d 2d\nvoid matx_X() {}')
		self.assertEqual((s['uniforms'], s['driven']), (['t'], {'t': 'absTime.seconds'}))
		self.assertEqual(s['menus'], [('dims', ['3d', '2d'])])   # an item may start with a digit
		s = codegen.parse_snippet('// @type X\n// @in vec3 axis = 0 0 1 [-1 1]\n// @in float a [0 10]\n'
		                          '// @in vec3 v = uv\nvoid matx_X() {}')
		self.assertEqual(s['ins'], [('vec3', 'axis', [0.0, 0.0, 1.0]), ('float', 'a', None), ('vec3', 'v', 'uv')])
		self.assertEqual(s['ranges'], {'axis': (-1.0, 1.0), 'a': (0.0, 10.0)})   # slider range of the parameter
		with self.assertRaisesRegex(codegen.MatxError, 'range'):
			codegen.parse_snippet('// @type X\n// @in float a = 0 [lo hi]\nvoid matx_X() {}')
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
