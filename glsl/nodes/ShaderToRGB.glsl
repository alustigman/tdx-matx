// @type ShaderToRGB
// @category Converter
// @in closure surface
// @out vec3 rgbOut
// @out float alpha
// The lit colour of a shader as a plain colour, so it can go through colour nodes (a Color
// Ramp for toon bands, a Posterize) before being shaded again as emission.
void matx_ShaderToRGB(MatxClosure surface, out vec3 rgbOut, out float alpha)
{
	rgbOut = surface.radiance;
	alpha = surface.alpha;
}
