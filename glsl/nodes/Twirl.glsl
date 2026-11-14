// @type Twirl
// @category Vector
// @in vec3 vector = uv
// @in vec3 center = 0.5 0.5 0.0 [0 1]
// @in float strength = 10.0 [-20 20]
// @out vec3 result vector
// Twists xy coordinates around center: the further from the centre, the more they turn.
void matx_Twirl(vec3 vector, vec3 center, float strength, out vec3 result)
{
	vec2 delta = vector.xy - center.xy;
	float angle = strength * length(delta);
	float c = cos(angle);
	float s = sin(angle);
	result = vec3(c * delta.x - s * delta.y + center.x, s * delta.x + c * delta.y + center.y, vector.z);
}
