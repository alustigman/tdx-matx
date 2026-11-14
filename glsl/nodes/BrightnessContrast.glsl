// @type BrightnessContrast
// @category Color
// @in vec3 color = 0.8
// @in float bright = 0.0 [-1 1]
// @in float contrast = 0.0 [-1 1]
// @out vec3 result
// Blender's Brightness/Contrast: contrast scales around mid grey, bright offsets; both are 0
// for no change. The result is not allowed below 0.
void matx_BrightnessContrast(vec3 color, float bright, float contrast, out vec3 result)
{
	float a = 1.0 + contrast;
	float b = bright - contrast * 0.5;
	result = max(a * color + b, vec3(0.0));
}
