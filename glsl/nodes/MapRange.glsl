// @type MapRange
// @category Converter
// @menu interpolation linear stepped_linear smoothstep smootherstep
// @menu clamp_result on off
// @in float value = 1.0
// @in float from_min = 0.0
// @in float from_max = 1.0
// @in float to_min = 0.0
// @in float to_max = 1.0
// @in float steps = 4.0 [1 16]
// @out float result
// Blender's Map Range: remaps value from the range from_min..from_max to to_min..to_max.
// stepped_linear quantizes it into `steps` steps; smoothstep and smootherstep ease in and out
// (and always stay inside the target range). clamp_result limits linear and stepped results to
// the target range.
void matx_MapRange(int interpolation, int clamp_result, float value, float from_min, float from_max,
                   float to_min, float to_max, float steps, out float result)
{
	float range = from_max - from_min;
	float factor = range != 0.0 ? (value - from_min) / range : 0.0;
	switch (interpolation)
	{
		case MATX_MAPRANGE_INTERPOLATION_STEPPED_LINEAR:
			factor = steps > 0.0 ? floor(factor * (steps + 1.0)) / steps : 0.0;
			break;
		case MATX_MAPRANGE_INTERPOLATION_SMOOTHSTEP:
			factor = clamp(factor, 0.0, 1.0);
			factor = factor * factor * (3.0 - 2.0 * factor);
			break;
		case MATX_MAPRANGE_INTERPOLATION_SMOOTHERSTEP:
			factor = clamp(factor, 0.0, 1.0);
			factor = factor * factor * factor * (factor * (factor * 6.0 - 15.0) + 10.0);
			break;
		default: break;
	}
	result = range != 0.0 ? to_min + factor * (to_max - to_min) : 0.0;
	if (clamp_result == MATX_MAPRANGE_CLAMP_RESULT_ON)
		result = clamp(result, min(to_min, to_max), max(to_min, to_max));
}
