// @type Flipbook
// @category Vector
// @in vec3 vector = uv
// @in float columns = 4.0 [1 16]
// @in float rows = 4.0 [1 16]
// @in float frame = 0.0 [0 16]
// @out vec3 result vector
// Texture coordinates of one cell of a sprite sheet of columns by rows cells, for a Sampler's
// vector. frame counts from the top-left cell, row by row, and wraps around; drive it with a
// Time node to play the sheet.
void matx_Flipbook(vec3 vector, float columns, float rows, float frame, out vec3 result)
{
	columns = max(floor(columns + 0.5), 1.0);
	rows = max(floor(rows + 0.5), 1.0);
	float tile = mod(floor(frame), columns * rows);
	float column = mod(tile, columns);
	float row = rows - 1.0 - floor(tile / columns);
	result = vec3((fract(vector.xy) + vec2(column, row)) / vec2(columns, rows), vector.z);
}
