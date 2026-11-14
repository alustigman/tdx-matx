// @type DiffuseBSDF
// @category Shader
// @in vec3 color = 0.8
// @in vec3 normal = world_normal
// @out closure bsdf
// @requires lighting
// Matte surface: the diffuse part of TouchDesigner's PBR lighting only, no highlight.
void matx_DiffuseBSDF(vec3 color, vec3 normal, out MatxClosure bsdf)
{
	bsdf.radiance = matx_pbr_lighting(color, vec3(0.0), normal, 1.0, 1.0, 1.0, vec3(0.0));
	bsdf.alpha = 1.0;
}
