// @type EmissionShader
// @category Shader
// @in vec3 emissionColor = 1.0
// @in float strength = 1.0
// @out closure bsdf
// Unlit colour: the surface emits emissionColor * strength whatever the lights are.
void matx_EmissionShader(vec3 emissionColor, float strength, out MatxClosure bsdf)
{
	bsdf.radiance = emissionColor * strength;
	bsdf.alpha = 1.0;
}
