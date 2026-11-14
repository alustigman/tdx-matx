// @type MixColor
// @category Color
// @menu blend_type mix darken multiply burn lighten screen dodge add overlay soft_light linear_light difference exclusion subtract divide hue saturation color value
// @menu clamp_result off on
// @in float fac = 0.5
// @in vec3 a = 0.5
// @in vec3 b = 0.5
// @out vec3 result
// Blender's Mix Color: blends b over a with the chosen blend type, by fac (clamped to 0-1).
// clamp_result limits the result to 0-1.
void matx_MixColor(int blend_type, int clamp_result, float fac, vec3 a, vec3 b, out vec3 result)
{
	fac = clamp(fac, 0.0, 1.0);
	float facm = 1.0 - fac;
	switch (blend_type)
	{
		case MATX_MIXCOLOR_BLEND_TYPE_DARKEN:   result = mix(a, min(a, b), fac); break;
		case MATX_MIXCOLOR_BLEND_TYPE_MULTIPLY: result = mix(a, a * b, fac); break;
		case MATX_MIXCOLOR_BLEND_TYPE_BURN:
			for (int i = 0; i < 3; i++)
			{
				float t = facm + fac * b[i];
				result[i] = t <= 0.0 ? 0.0 : clamp(1.0 - (1.0 - a[i]) / t, 0.0, 1.0);
			}
			break;
		case MATX_MIXCOLOR_BLEND_TYPE_LIGHTEN:  result = mix(a, max(a, b), fac); break;
		case MATX_MIXCOLOR_BLEND_TYPE_SCREEN:   result = vec3(1.0) - (vec3(facm) + fac * (vec3(1.0) - b)) * (vec3(1.0) - a); break;
		case MATX_MIXCOLOR_BLEND_TYPE_DODGE:
			for (int i = 0; i < 3; i++)
			{
				float t = 1.0 - fac * b[i];
				result[i] = a[i] == 0.0 ? 0.0 : (t <= 0.0 ? 1.0 : min(a[i] / t, 1.0));
			}
			break;
		case MATX_MIXCOLOR_BLEND_TYPE_ADD:      result = mix(a, a + b, fac); break;
		case MATX_MIXCOLOR_BLEND_TYPE_OVERLAY:
			for (int i = 0; i < 3; i++)
			{
				result[i] = a[i] < 0.5 ? a[i] * (facm + 2.0 * fac * b[i])
				                       : 1.0 - (facm + 2.0 * fac * (1.0 - b[i])) * (1.0 - a[i]);
			}
			break;
		case MATX_MIXCOLOR_BLEND_TYPE_SOFT_LIGHT:
		{
			vec3 scr = vec3(1.0) - (vec3(1.0) - b) * (vec3(1.0) - a);
			result = facm * a + fac * ((vec3(1.0) - a) * b * a + a * scr);
			break;
		}
		case MATX_MIXCOLOR_BLEND_TYPE_LINEAR_LIGHT: result = a + fac * (2.0 * (b - vec3(0.5))); break;
		case MATX_MIXCOLOR_BLEND_TYPE_DIFFERENCE:   result = mix(a, abs(a - b), fac); break;
		case MATX_MIXCOLOR_BLEND_TYPE_EXCLUSION:    result = max(mix(a, a + b - 2.0 * a * b, fac), vec3(0.0)); break;
		case MATX_MIXCOLOR_BLEND_TYPE_SUBTRACT:     result = mix(a, a - b, fac); break;
		case MATX_MIXCOLOR_BLEND_TYPE_DIVIDE:
			for (int i = 0; i < 3; i++)
				result[i] = b[i] != 0.0 ? facm * a[i] + fac * a[i] / b[i] : a[i];
			break;
		case MATX_MIXCOLOR_BLEND_TYPE_HUE:
		{
			vec3 hsv2 = TDRGBToHSV(b);
			result = a;
			if (hsv2.y != 0.0)
			{
				vec3 hsv = TDRGBToHSV(a);
				hsv.x = hsv2.x;
				result = mix(a, TDHSVToRGB(hsv), fac);
			}
			break;
		}
		case MATX_MIXCOLOR_BLEND_TYPE_SATURATION:
		{
			vec3 hsv = TDRGBToHSV(a);
			result = a;
			if (hsv.y != 0.0)
			{
				hsv.y = facm * hsv.y + fac * TDRGBToHSV(b).y;
				result = TDHSVToRGB(hsv);
			}
			break;
		}
		case MATX_MIXCOLOR_BLEND_TYPE_COLOR:
		{
			vec3 hsv2 = TDRGBToHSV(b);
			result = a;
			if (hsv2.y != 0.0)
			{
				vec3 hsv = TDRGBToHSV(a);
				hsv.xy = hsv2.xy;
				result = mix(a, TDHSVToRGB(hsv), fac);
			}
			break;
		}
		case MATX_MIXCOLOR_BLEND_TYPE_VALUE:
		{
			vec3 hsv = TDRGBToHSV(a);
			hsv.z = facm * hsv.z + fac * TDRGBToHSV(b).z;
			result = TDHSVToRGB(hsv);
			break;
		}
		default: result = mix(a, b, fac); break;
	}
	if (clamp_result == MATX_MIXCOLOR_CLAMP_RESULT_ON)
		result = clamp(result, 0.0, 1.0);
}
