// @type SeparateColor
// @category Converter
// @menu mode rgb hsv hsl
// @in vec3 color = 0.8
// @out float red
// @out float green
// @out float blue
// Splits a colour into its channels. In HSV mode the outputs are hue, saturation and value; in
// HSL mode hue, saturation and lightness.
vec3 matx_rgb_to_hsl(vec3 c)
{
	float cmax = max(c.r, max(c.g, c.b));
	float cmin = min(c.r, min(c.g, c.b));
	float l = min(1.0, (cmax + cmin) / 2.0);
	if (cmax == cmin)
		return vec3(0.0, 0.0, l);
	float d = cmax - cmin;
	float s = l > 0.5 ? d / (2.0 - cmax - cmin) : d / (cmax + cmin);
	float h;
	if (cmax == c.r)
		h = (c.g - c.b) / d + (c.g < c.b ? 6.0 : 0.0);
	else if (cmax == c.g)
		h = (c.b - c.r) / d + 2.0;
	else
		h = (c.r - c.g) / d + 4.0;
	return vec3(h / 6.0, s, l);
}

void matx_SeparateColor(int mode, vec3 color, out float red, out float green, out float blue)
{
	vec3 c = color;
	if (mode == MATX_SEPARATECOLOR_MODE_HSV)
		c = TDRGBToHSV(color);
	else if (mode == MATX_SEPARATECOLOR_MODE_HSL)
		c = matx_rgb_to_hsl(color);
	red = c.r;
	green = c.g;
	blue = c.b;
}
