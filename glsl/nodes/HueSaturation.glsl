// @type HueSaturation
// @category Color
// @in float hue = 0.5
// @in float saturation = 1.0 [0 2]
// @in float value = 1.0 [0 2]
// @in float fac = 1.0
// @in vec3 color = 0.8
// @out vec3 result
// Blender's Hue/Saturation/Value: hue 0.5 leaves the hue alone (0 and 1 are a half turn),
// saturation and value multiply; fac blends the result in.
void matx_HueSaturation(float hue, float saturation, float value, float fac, vec3 color, out vec3 result)
{
	vec3 hsv = TDRGBToHSV(color);
	hsv.x = fract(hsv.x + hue + 0.5);
	hsv.y = clamp(hsv.y * saturation, 0.0, 1.0);
	hsv.z *= value;
	result = mix(color, TDHSVToRGB(hsv), clamp(fac, 0.0, 1.0));
}
