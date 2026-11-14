// @type ColorRamp
// @category Converter
// @sampler sampler2D ramp
// @in float fac = 0.5
// @out vec3 color
// @out float alpha
// Maps fac (0-1) to a colour by reading a TOP from left to right: set a Ramp TOP on the node
// and edit its keys. Any TOP works as a lookup (a gradient image, a CHOP to TOP).
void matx_ColorRamp(sampler2D ramp, float fac, out vec3 color, out float alpha)
{
	vec4 c = texture(ramp, vec2(clamp(fac, 0.0, 1.0), 0.5));
	color = c.rgb;
	alpha = c.a;
}
