// @type ShaderToRGB
// @in closure surface
// @out vec3 rgbOut
void matx_ShaderToRGB(MatxClosure surface, out vec3 rgbOut)
{
	rgbOut = surface.radiance;
}
