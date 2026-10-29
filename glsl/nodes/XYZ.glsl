// @type XYZ
// @category Input
// @in vec3 vector = 0
// @uniform vector
// @out vec3 vector_out
// A constant vector. Its socket name makes it an XYZ parameter, and as a uniform it goes on the
// GLSL MAT's Vectors page (RGB's colour goes on the Colors page).
void matx_XYZ(vec3 vector, out vec3 vector_out)
{
	vector_out = vector;
}
