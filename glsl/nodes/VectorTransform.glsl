// @type VectorTransform
// @category Vector
// @menu transform_type point vector normal
// @menu convert_from world object camera
// @menu convert_to object world camera
// @in vec3 vector = 0.0
// @out vec3 result
// Converts a vector between spaces: world, the geometry's object space (the Geometry COMP's
// transform, without instancing) and the camera's space. Point moves a position (translation
// included), Vector a direction, Normal a surface normal (renormalized).
void matx_VectorTransform(int transform_type, int convert_from, int convert_to, vec3 vector, out vec3 result)
{
	int cam = iVert.cameraIndex;
	bool isPoint = transform_type == MATX_VECTORTRANSFORM_TRANSFORM_TYPE_POINT;
	bool isNormal = transform_type == MATX_VECTORTRANSFORM_TRANSFORM_TYPE_NORMAL;
	vec3 v = vector;
	// to world space
	if (convert_from == MATX_VECTORTRANSFORM_CONVERT_FROM_OBJECT)
	{
		if (isPoint)       v = (uTDMats[cam].world * vec4(v, 1.0)).xyz;
		else if (isNormal) v = uTDMats[cam].worldForNormals * v;
		else               v = mat3(uTDMats[cam].world) * v;
	}
	else if (convert_from == MATX_VECTORTRANSFORM_CONVERT_FROM_CAMERA)
	{
		if (isPoint)       v = (uTDMats[cam].camInverse * vec4(v, 1.0)).xyz;
		else if (isNormal) v = transpose(mat3(uTDMats[cam].cam)) * v;
		else               v = mat3(uTDMats[cam].camInverse) * v;
	}
	// from world space
	if (convert_to == MATX_VECTORTRANSFORM_CONVERT_TO_OBJECT)
	{
		if (isPoint)       v = (uTDMats[cam].worldInverse * vec4(v, 1.0)).xyz;
		else if (isNormal) v = transpose(mat3(uTDMats[cam].world)) * v;
		else               v = mat3(uTDMats[cam].worldInverse) * v;
	}
	else if (convert_to == MATX_VECTORTRANSFORM_CONVERT_TO_CAMERA)
	{
		if (isPoint)       v = (uTDMats[cam].cam * vec4(v, 1.0)).xyz;
		else if (isNormal) v = uTDMats[cam].camForNormals * v;
		else               v = mat3(uTDMats[cam].cam) * v;
	}
	result = (isNormal && dot(v, v) > 0.0) ? normalize(v) : v;
}
