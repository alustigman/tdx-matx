// @type CheckerTexture
// @category Texture
// @in vec3 vector = uv
// @in vec3 color1 = 0.8
// @in vec3 color2 = 0.2
// @in float scale = 5.0
// @out vec3 color
// @out float fac
// A 3D checkerboard of the two colours; fac is 1 on color1 cells and 0 on color2 cells.
void matx_CheckerTexture(vec3 vector, vec3 color1, vec3 color2, float scale, out vec3 color, out float fac)
{
	vec3 p = vector * scale;
	p = (p + 0.000001) * 0.999999;   // avoids precision issues on unit coordinates
	ivec3 cell = ivec3(abs(floor(p)));
	bool check = ((cell.x % 2) == (cell.y % 2)) == ((cell.z % 2) == 1);
	color = check ? color1 : color2;
	fac = check ? 1.0 : 0.0;
}
