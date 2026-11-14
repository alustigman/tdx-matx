// @type AddShader
// @category Shader
// @in closure shader_a
// @in closure shader_b
// @out closure shader
// Adds the light of two shaders (a glossy coat over a diffuse base, an emission over a BSDF).
void matx_AddShader(MatxClosure shader_a, MatxClosure shader_b, out MatxClosure shader)
{
	shader.radiance = shader_a.radiance + shader_b.radiance;
	shader.alpha = min(shader_a.alpha + shader_b.alpha, 1.0);
}
