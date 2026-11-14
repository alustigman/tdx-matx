// @type MagicTexture
// @category Texture
// @in vec3 vector = uv
// @in float scale = 5.0
// @in float distortion = 1.0
// @in float depth = 2.0
// @out vec3 color
// @out float fac
// Blender's Magic Texture: psychedelic colour bands made of nested sines. depth (0 to 10, a
// whole number) is how many times the pattern is folded back on itself, distortion how hard.
void matx_MagicTexture(vec3 vector, float scale, float distortion, float depth, out vec3 color, out float fac)
{
	vec3 p = vector * scale;
	int turns = int(depth + 0.5);
	float x = sin((p.x + p.y + p.z) * 5.0);
	float y = cos((-p.x + p.y - p.z) * 5.0);
	float z = -cos((-p.x - p.y + p.z) * 5.0);
	if (turns > 0)
	{
		x *= distortion;
		y *= distortion;
		z *= distortion;
		y = -cos(x - y + z) * distortion;
	}
	if (turns > 1) x = cos(x - y - z) * distortion;
	if (turns > 2) z = sin(-x - y - z) * distortion;
	if (turns > 3) x = -cos(-x + y - z) * distortion;
	if (turns > 4) y = -sin(-x + y + z) * distortion;
	if (turns > 5) y = -cos(-x + y + z) * distortion;
	if (turns > 6) x = cos(x + y + z) * distortion;
	if (turns > 7) z = sin(x + y - z) * distortion;
	if (turns > 8) x = -cos(-x - y + z) * distortion;
	if (turns > 9) y = -sin(x - y + z) * distortion;
	if (distortion != 0.0)
	{
		x /= 2.0 * distortion;
		y /= 2.0 * distortion;
		z /= 2.0 * distortion;
	}
	color = vec3(0.5 - x, 0.5 - y, 0.5 - z);
	fac = (color.r + color.g + color.b) / 3.0;
}
