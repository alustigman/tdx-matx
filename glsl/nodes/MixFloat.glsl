// @type MixFloat
// @category Converter
// @in float fac = 0.5
// @in float a = 0.0
// @in float b = 1.0
// @out float result
// Blends two values: fac 0 is a, 1 is b (fac is clamped to 0-1).
void matx_MixFloat(float fac, float a, float b, out float result)
{
	result = mix(a, b, clamp(fac, 0.0, 1.0));
}
