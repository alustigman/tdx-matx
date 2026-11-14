// @type VectorRotate
// @category Vector
// @menu rotation_type axis_angle x_axis y_axis z_axis euler_xyz
// @menu invert off on
// @in vec3 vector = 0.0
// @in vec3 center = 0.0 [-1 1]
// @in vec3 axis = 0.0 0.0 1.0 [-1 1]
// @in float angle = 0.0 [-180 180]
// @in vec3 rotation = 0.0 [-180 180]
// @out vec3 result
// @enable axis if rotation_type axis_angle
// @enable angle unless rotation_type euler_xyz
// @enable rotation if rotation_type euler_xyz
// Blender's Vector Rotate: turns the vector around center. axis_angle uses axis and angle, the
// three axis types use angle only, euler_xyz uses rotation; angles are in degrees. invert turns
// the other way.
void matx_VectorRotate(int rotation_type, int invert, vec3 vector, vec3 center, vec3 axis, float angle,
                       vec3 rotation, out vec3 result)
{
	float a = radians(angle);
	mat3 rot;
	switch (rotation_type)
	{
		case MATX_VECTORROTATE_ROTATION_TYPE_X_AXIS: rot = TDRotateX(a); break;
		case MATX_VECTORROTATE_ROTATION_TYPE_Y_AXIS: rot = TDRotateY(a); break;
		case MATX_VECTORROTATE_ROTATION_TYPE_Z_AXIS: rot = TDRotateZ(a); break;
		case MATX_VECTORROTATE_ROTATION_TYPE_EULER_XYZ:
		{
			vec3 r = radians(rotation);
			rot = TDRotateZ(r.z) * TDRotateY(r.y) * TDRotateX(r.x);
			break;
		}
		default:
			rot = dot(axis, axis) > 0.0 ? TDRotateOnAxis(a, normalize(axis)) : mat3(1.0);
			break;
	}
	if (invert == MATX_VECTORROTATE_INVERT_ON)
		rot = transpose(rot);
	result = rot * (vector - center) + center;
}
