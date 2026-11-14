// @type BrickTexture
// @category Texture
// @in vec3 vector = uv
// @in vec3 color1 = 0.8
// @in vec3 color2 = 0.2
// @in vec3 mortar = 0.0
// @in float scale = 5.0
// @in float mortar_size = 0.02
// @in float mortar_smooth = 0.1
// @in float bias = 0.0
// @in float brick_width = 0.5
// @in float row_height = 0.25
// @in float offset_amount = 0.5
// @in float offset_frequency = 2.0
// @in float squash_amount = 1.0
// @in float squash_frequency = 2.0
// @out vec3 color
// @out float fac
// @requires hash
// Blender's Brick Texture, in the vector's xy plane. Each brick is a random blend of color1 and
// color2 (bias pushes towards one of them); fac is 1 in the mortar. Every offset_frequency-th
// row is shifted by offset_amount of a brick, and every squash_frequency-th row has its bricks
// scaled by squash_amount (both frequencies are whole numbers).
void matx_BrickTexture(vec3 vector, vec3 color1, vec3 color2, vec3 mortar, float scale, float mortar_size,
                       float mortar_smooth, float bias, float brick_width, float row_height,
                       float offset_amount, float offset_frequency, float squash_amount,
                       float squash_frequency, out vec3 color, out float fac)
{
	vec3 p = vector * scale;
	brick_width = max(brick_width, 0.00001);
	row_height = max(row_height, 0.00001);
	int offsetFrequency = int(offset_frequency + 0.5);
	int squashFrequency = int(squash_frequency + 0.5);

	float row = floor(p.y / row_height);
	float offset = 0.0;
	if (offsetFrequency > 0 && squashFrequency > 0)
	{
		if (mod(row, float(squashFrequency)) == 0.0)
			brick_width *= squash_amount;
		if (mod(row, float(offsetFrequency)) == 0.0)
			offset = brick_width * offset_amount;
	}
	brick_width = max(brick_width, 0.00001);
	float brick = floor((p.x + offset) / brick_width);
	float x = (p.x + offset) - brick_width * brick;
	float y = p.y - row_height * row;

	float tint = clamp(matx_hash_cell(vec4(brick, row, 0.0, 0.0)).x + bias, 0.0, 1.0);
	float edge = min(min(x, y), min(brick_width - x, row_height - y));
	if (edge >= mortar_size)
		fac = 0.0;
	else if (mortar_smooth == 0.0)
		fac = 1.0;
	else
		fac = smoothstep(0.0, mortar_smooth, 1.0 - edge / mortar_size);

	color = mix(mix(color1, color2, tint), mortar, fac);
}
