// @type Blackbody
// @category Converter
// @in float temperature = 6500.0 [1000 12000]
// @out vec3 color
// The colour of a glowing black body at this temperature in kelvin: 1500 is ember red, 3000 a
// tungsten bulb, 6500 daylight white, 10000 and above blue sky. Uses Tanner Helland's
// approximation (valid from 1000 K to 40000 K).
void matx_Blackbody(float temperature, out vec3 color)
{
	float t = clamp(temperature, 1000.0, 40000.0) / 100.0;
	float r = t <= 66.0 ? 255.0 : 329.698727446 * pow(t - 60.0, -0.1332047592);
	float g = t <= 66.0 ? 99.4708025861 * log(t) - 161.1195681661
	                    : 288.1221695283 * pow(t - 60.0, -0.0755148492);
	float b = t >= 66.0 ? 255.0 : (t <= 19.0 ? 0.0 : 138.5177312231 * log(t - 10.0) - 305.0447927307);
	color = clamp(vec3(r, g, b) / 255.0, 0.0, 1.0);
}
