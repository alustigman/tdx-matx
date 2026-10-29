// @type MixColor
// @category Color
// @in float fac = 0.5
// @in vec3 a = 0.5
// @in vec3 b = 0.5
// @out vec3 result
void matx_MixColor(float fac, vec3 a, vec3 b, out vec3 result)
{
	result = mix(a, b, clamp(fac, 0.0, 1.0));
}
