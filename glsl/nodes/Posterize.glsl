// @type Posterize
// @category Color
// @in vec3 color = 0.8
// @in float steps = 4.0 [1 16]
// @out vec3 result
// Reduces each channel to `steps` levels.
void matx_Posterize(vec3 color, float steps, out vec3 result)
{
	steps = max(steps, 1.0);
	result = floor(color * steps) / steps;
}
