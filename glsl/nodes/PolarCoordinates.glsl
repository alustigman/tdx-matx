// @type PolarCoordinates
// @category Vector
// @in vec3 vector = uv
// @in vec3 center = 0.5 0.5 0.0 [0 1]
// @in float radial_scale = 1.0
// @in float length_scale = 1.0
// @out vec3 result vector
// Converts xy coordinates to polar ones around center: result.x is the distance from the centre
// (times 2, so the edge of a 0-1 square is 1), result.y the angle as 0-1 around the circle.
// Feed it to a texture to wrap the pattern into rings and spokes.
void matx_PolarCoordinates(vec3 vector, vec3 center, float radial_scale, float length_scale, out vec3 result)
{
	vec2 delta = vector.xy - center.xy;
	float radius = length(delta) * 2.0 * radial_scale;
	float angle = (delta == vec2(0.0)) ? 0.0 : atan(delta.y, delta.x) / 6.28318530718 + 0.5;
	result = vec3(radius, angle * length_scale, vector.z);
}
