// @type NoiseTexture
// @in vec3 vector = 0.0
// @in float scale = 5.0
// @out float fac
// @out vec3 color
void matx_NoiseTexture(vec3 vector, float scale, out float fac, out vec3 color)
{
	fac = TDPerlinNoise(vector * scale) * 0.5 + 0.5;
	color = vec3(fac);
}
