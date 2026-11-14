// @type MixVector
// @category Converter
// @in float fac = 0.5
// @in vec3 vector_a = 0.0
// @in vec3 vector_b = 1.0
// @out vec3 vector
// Blends two vectors: fac 0 is vector_a, 1 is vector_b (fac is clamped to 0-1).
void matx_MixVector(float fac, vec3 vector_a, vec3 vector_b, out vec3 vector)
{
	vector = mix(vector_a, vector_b, clamp(fac, 0.0, 1.0));
}
