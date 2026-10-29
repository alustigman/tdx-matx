// @type VectorMath
// @category Converter
// @menu operation add subtract multiply divide multiply_add cross_product project reflect refract faceforward dot_product distance length scale normalize absolute minimum maximum floor ceil fraction modulo wrap snap sine cosine tangent
// @in vec3 vector_a = 0
// @in vec3 vector_b = 0
// @in vec3 vector_c = 0
// @in float scale = 1
// @out vec3 vector
// @out float value
// Blender's Vector Math node. Vector C is read by multiply_add, faceforward and wrap; Scale by
// scale and refract (as the IOR). dot_product, distance and length write Value and leave Vector at
// 0; the other operations write Vector and leave Value at 0. Operations that can fail (divide,
// project, normalize, modulo, wrap, snap) return 0 per component instead of NaN, as Blender's
// safe_* variants do.
float matx_vm_safe_div(float a, float b) { return b != 0.0 ? a / b : 0.0; }
vec3 matx_vm_safe_div(vec3 a, vec3 b)
{
	return vec3(matx_vm_safe_div(a.x, b.x), matx_vm_safe_div(a.y, b.y), matx_vm_safe_div(a.z, b.z));
}
float matx_vm_wrap(float v, float mx, float mn)
{
	float range = mx - mn;
	return range != 0.0 ? v - range * floor((v - mn) / range) : mn;
}

void matx_VectorMath(int operation, vec3 vector_a, vec3 vector_b, vec3 vector_c, float scale,
                     out vec3 vector, out float value)
{
	vec3 a = vector_a, b = vector_b, c = vector_c;
	vector = vec3(0.0);
	value = 0.0;
	switch (operation)
	{
		case MATX_VECTORMATH_OPERATION_ADD:           vector = a + b; break;
		case MATX_VECTORMATH_OPERATION_SUBTRACT:      vector = a - b; break;
		case MATX_VECTORMATH_OPERATION_MULTIPLY:      vector = a * b; break;
		case MATX_VECTORMATH_OPERATION_DIVIDE:        vector = matx_vm_safe_div(a, b); break;
		case MATX_VECTORMATH_OPERATION_MULTIPLY_ADD:  vector = a * b + c; break;
		case MATX_VECTORMATH_OPERATION_CROSS_PRODUCT: vector = cross(a, b); break;
		case MATX_VECTORMATH_OPERATION_PROJECT:
		{
			float len2 = dot(b, b);
			vector = len2 != 0.0 ? b * (dot(a, b) / len2) : vec3(0.0);
			break;
		}
		case MATX_VECTORMATH_OPERATION_REFLECT:       vector = reflect(a, normalize(b)); break;
		case MATX_VECTORMATH_OPERATION_REFRACT:       vector = refract(a, normalize(b), scale); break;
		case MATX_VECTORMATH_OPERATION_FACEFORWARD:   vector = faceforward(a, b, c); break;
		case MATX_VECTORMATH_OPERATION_DOT_PRODUCT:   value = dot(a, b); break;
		case MATX_VECTORMATH_OPERATION_DISTANCE:      value = distance(a, b); break;
		case MATX_VECTORMATH_OPERATION_LENGTH:        value = length(a); break;
		case MATX_VECTORMATH_OPERATION_SCALE:         vector = a * scale; break;
		case MATX_VECTORMATH_OPERATION_NORMALIZE:     vector = dot(a, a) != 0.0 ? normalize(a) : vec3(0.0); break;
		case MATX_VECTORMATH_OPERATION_ABSOLUTE:      vector = abs(a); break;
		case MATX_VECTORMATH_OPERATION_MINIMUM:       vector = min(a, b); break;
		case MATX_VECTORMATH_OPERATION_MAXIMUM:       vector = max(a, b); break;
		case MATX_VECTORMATH_OPERATION_FLOOR:         vector = floor(a); break;
		case MATX_VECTORMATH_OPERATION_CEIL:          vector = ceil(a); break;
		case MATX_VECTORMATH_OPERATION_FRACTION:      vector = a - floor(a); break;
		// truncated modulo (the result takes a's sign), like the Math node's modulo
		case MATX_VECTORMATH_OPERATION_MODULO:        vector = a - b * trunc(matx_vm_safe_div(a, b)); break;
		// wrap a into [c, b), per component
		case MATX_VECTORMATH_OPERATION_WRAP:
			vector = vec3(matx_vm_wrap(a.x, b.x, c.x), matx_vm_wrap(a.y, b.y, c.y), matx_vm_wrap(a.z, b.z, c.z));
			break;
		case MATX_VECTORMATH_OPERATION_SNAP:          vector = floor(matx_vm_safe_div(a, b)) * b; break;
		case MATX_VECTORMATH_OPERATION_SINE:          vector = sin(a); break;
		case MATX_VECTORMATH_OPERATION_COSINE:        vector = cos(a); break;
		case MATX_VECTORMATH_OPERATION_TANGENT:       vector = tan(a); break;
	}
}
