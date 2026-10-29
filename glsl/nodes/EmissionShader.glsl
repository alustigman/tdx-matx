// @type EmissionShader
// @category Shader
// @in vec3 emissionColor = 1.0
// @out closure bsdf
void matx_EmissionShader(vec3 emissionColor, out MatxClosure bsdf)
{
	bsdf.radiance = emissionColor;
	bsdf.alpha = 1.0;
}
