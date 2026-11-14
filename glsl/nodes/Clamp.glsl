// @type Clamp
// @category Converter
// @menu clamp_type minmax range
// @in float value = 1.0
// @in float min = 0.0
// @in float max = 1.0
// @out float result
// Limits value to min..max. Range also works when min is greater than max.
void matx_Clamp(int clamp_type, float value, float lo, float hi, out float result)
{
	if (clamp_type == MATX_CLAMP_CLAMP_TYPE_RANGE)
		result = clamp(value, min(lo, hi), max(lo, hi));
	else
		result = min(max(value, lo), hi);
}
