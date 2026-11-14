// @type TransparentBSDF
// @category Shader
// @in vec3 color = 1.0
// @out closure bsdf
// See-through surface: white is fully transparent, black is opaque black. Mix it with another
// shader to cut holes. The GLSL MAT needs Blending on (Common page) for alpha to show.
void matx_TransparentBSDF(vec3 color, out MatxClosure bsdf)
{
	bsdf.radiance = vec3(0.0);
	bsdf.alpha = 1.0 - clamp(dot(color, vec3(0.2126, 0.7152, 0.0722)), 0.0, 1.0);
}
