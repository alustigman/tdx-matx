// @type CombineColor
// @category Converter
// @menu mode rgb hsv hsl
// @in float red = 0.0
// @in float green = 0.0
// @in float blue = 0.0
// @out vec3 color
// Builds a colour from three channels. In HSV mode the inputs are hue, saturation and value;
// in HSL mode hue, saturation and lightness.
vec3 matx_hsl_to_rgb(vec3 hsl)
{
	float nr = abs(hsl.x * 6.0 - 3.0) - 1.0;
	float ng = 2.0 - abs(hsl.x * 6.0 - 2.0);
	float nb = 2.0 - abs(hsl.x * 6.0 - 4.0);
	vec3 n = clamp(vec3(nr, ng, nb), 0.0, 1.0);
	float chroma = (1.0 - abs(2.0 * hsl.z - 1.0)) * hsl.y;
	return (n - 0.5) * chroma + hsl.z;
}

void matx_CombineColor(int mode, float red, float green, float blue, out vec3 color)
{
	color = vec3(red, green, blue);
	if (mode == MATX_COMBINECOLOR_MODE_HSV)
		color = TDHSVToRGB(color);
	else if (mode == MATX_COMBINECOLOR_MODE_HSL)
		color = matx_hsl_to_rgb(color);
}
