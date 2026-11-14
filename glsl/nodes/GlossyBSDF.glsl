// @type GlossyBSDF
// @category Shader
// @in vec3 color = 0.8
// @in float roughness = 0.5
// @in vec3 normal = world_normal
// @out closure bsdf
// @requires lighting
// Reflective surface: the specular part of TouchDesigner's PBR lighting only, tinted by color
// (like a metal). Environment Light COMPs give it something to reflect.
void matx_GlossyBSDF(vec3 color, float roughness, vec3 normal, out MatxClosure bsdf)
{
	bsdf.radiance = matx_pbr_lighting(vec3(0.0), color, normal, roughness, 1.0, 1.0, vec3(0.0));
	bsdf.alpha = 1.0;
}
