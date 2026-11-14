// @type RGBToBW
// @category Converter
// @in vec3 color = 0.5
// @out float val
// The luminance of a colour (Rec.709 weights, TDLuminance).
void matx_RGBToBW(vec3 color, out float val)
{
	val = TDLuminance(color);
}
