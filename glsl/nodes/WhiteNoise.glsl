// @type WhiteNoise
// @category Texture
// @menu dimensions 3d 1d 2d 4d
// @in vec3 vector = uv
// @in float w = 0.0
// @out float value
// @out vec3 color
// @requires hash
// @enable w if dimensions 1d 4d
// A random value and colour for every distinct input (1D is w alone, 2D vector.xy, 3D vector,
// 4D vector and w): no smoothing at all, so feed it stepped coordinates (a Voronoi position, a
// floored vector) to get one random value per cell.
void matx_WhiteNoise(int dimensions, vec3 vector, float w, out float value, out vec3 color)
{
	vec4 p = vec4(vector, 0.0);
	if (dimensions == MATX_WHITENOISE_DIMENSIONS_1D)
		p = vec4(0.0, 0.0, 0.0, w);
	else if (dimensions == MATX_WHITENOISE_DIMENSIONS_2D)
		p = vec4(vector.xy, 0.0, 0.0);
	else if (dimensions == MATX_WHITENOISE_DIMENSIONS_4D)
		p = vec4(vector, w);
	vec4 h = matx_hash_float(p);
	value = h.w;
	color = h.xyz;
}
