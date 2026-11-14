// @type MixShader
// @category Shader
// @in float fac = 0.5
// @in closure shader_a
// @in closure shader_b
// @out closure shader
// Blends two shaders: fac 0 is shader_a, 1 is shader_b. An unconnected shader is transparent
// black, so mixing with nothing fades the surface out.
void matx_MixShader(float fac, MatxClosure shader_a, MatxClosure shader_b, out MatxClosure shader)
{
	fac = clamp(fac, 0.0, 1.0);
	shader.radiance = mix(shader_a.radiance, shader_b.radiance, fac);
	shader.alpha = mix(shader_a.alpha, shader_b.alpha, fac);
}
