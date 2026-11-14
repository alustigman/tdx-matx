// @type InvertColor
// @category Color
// @in float fac = 1.0
// @in vec3 color = 0.8
// @out vec3 result
// Inverts the colour (1 - color), blended in by fac.
void matx_InvertColor(float fac, vec3 color, out vec3 result)
{
	result = mix(color, vec3(1.0) - color, clamp(fac, 0.0, 1.0));
}
