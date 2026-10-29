// @type SeparateXYZ
// @category Converter
// @in vec3 vector = 0
// @out float x
// @out float y
// @out float z
void matx_SeparateXYZ(vec3 vector, out float x, out float y, out float z)
{
	x = vector.x;
	y = vector.y;
	z = vector.z;
}
