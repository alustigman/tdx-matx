// @type Gamma
// @category Color
// @in vec3 color = 0.8
// @in float gamma = 1.0 [0 4]
// @out vec3 result
// Raises the colour to the power gamma (negative channels are left alone).
void matx_Gamma(vec3 color, float gamma, out vec3 result)
{
	result = color;
	for (int i = 0; i < 3; i++)
	{
		if (color[i] > 0.0)
			result[i] = pow(color[i], gamma);
	}
}
