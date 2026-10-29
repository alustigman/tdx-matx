// @type Math
// @category Converter
// @menu operation add subtract multiply divide power logarithm sqrt inverse_sqrt absolute exponent minimum maximum less_than greater_than sign round floor ceil truncate fraction modulo snap sine cosine tangent arcsine arccosine arctangent arctan2 radians degrees
// @in float a = 0.5
// @in float b = 0.5
// @out float value
// Blender's Math node: operations that can fail (divide, logarithm, power, sqrt, modulo, snap)
// return 0.0 instead of NaN or infinity, as Blender's safe_* variants do. `b` is unused by the
// one-operand operations.
void matx_Math(int operation, float a, float b, out float value)
{
	switch (operation)
	{
		case MATX_MATH_OPERATION_ADD:          value = a + b; break;
		case MATX_MATH_OPERATION_SUBTRACT:     value = a - b; break;
		case MATX_MATH_OPERATION_MULTIPLY:     value = a * b; break;
		case MATX_MATH_OPERATION_DIVIDE:       value = b != 0.0 ? a / b : 0.0; break;
		case MATX_MATH_OPERATION_POWER:
			// a negative base only has a real power for an integer exponent
			if (a >= 0.0)
				value = pow(a, b);
			else if (b == floor(b))
				value = pow(-a, b) * (mod(b, 2.0) == 0.0 ? 1.0 : -1.0);
			else
				value = 0.0;
			break;
		case MATX_MATH_OPERATION_LOGARITHM:    value = (a > 0.0 && b > 0.0 && b != 1.0) ? log(a) / log(b) : 0.0; break;
		case MATX_MATH_OPERATION_SQRT:         value = a > 0.0 ? sqrt(a) : 0.0; break;
		case MATX_MATH_OPERATION_INVERSE_SQRT: value = a > 0.0 ? inversesqrt(a) : 0.0; break;
		case MATX_MATH_OPERATION_ABSOLUTE:     value = abs(a); break;
		case MATX_MATH_OPERATION_EXPONENT:     value = exp(a); break;
		case MATX_MATH_OPERATION_MINIMUM:      value = min(a, b); break;
		case MATX_MATH_OPERATION_MAXIMUM:      value = max(a, b); break;
		case MATX_MATH_OPERATION_LESS_THAN:    value = a < b ? 1.0 : 0.0; break;
		case MATX_MATH_OPERATION_GREATER_THAN: value = a > b ? 1.0 : 0.0; break;
		case MATX_MATH_OPERATION_SIGN:         value = sign(a); break;
		case MATX_MATH_OPERATION_ROUND:        value = floor(a + 0.5); break;
		case MATX_MATH_OPERATION_FLOOR:        value = floor(a); break;
		case MATX_MATH_OPERATION_CEIL:         value = ceil(a); break;
		case MATX_MATH_OPERATION_TRUNCATE:     value = trunc(a); break;
		case MATX_MATH_OPERATION_FRACTION:     value = a - floor(a); break;
		// truncated modulo (the result takes a's sign), like Blender's Truncated Modulo / C fmod
		case MATX_MATH_OPERATION_MODULO:       value = b != 0.0 ? a - b * trunc(a / b) : 0.0; break;
		case MATX_MATH_OPERATION_SNAP:         value = b != 0.0 ? floor(a / b) * b : 0.0; break;
		case MATX_MATH_OPERATION_SINE:         value = sin(a); break;
		case MATX_MATH_OPERATION_COSINE:       value = cos(a); break;
		case MATX_MATH_OPERATION_TANGENT:      value = tan(a); break;
		case MATX_MATH_OPERATION_ARCSINE:      value = asin(clamp(a, -1.0, 1.0)); break;
		case MATX_MATH_OPERATION_ARCCOSINE:    value = acos(clamp(a, -1.0, 1.0)); break;
		case MATX_MATH_OPERATION_ARCTANGENT:   value = atan(a); break;
		case MATX_MATH_OPERATION_ARCTAN2:      value = atan(a, b); break;
		case MATX_MATH_OPERATION_RADIANS:      value = radians(a); break;
		case MATX_MATH_OPERATION_DEGREES:      value = degrees(a); break;
		default:                               value = 0.0; break;
	}
}
