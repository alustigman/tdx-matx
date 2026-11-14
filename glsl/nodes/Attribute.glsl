// @type Attribute
// @category Input
// @attrib vec4 attribute = Color typed
// @out vec3 color
// @out vec3 vector
// @out float fac
// @out float alpha
// Reads a geometry attribute by name (a POP attribute such as Color, PartVel or a custom one).
// Set the type to the attribute's size. A float fills every component; a vec2 or vec3 has
// alpha 1. `fac` is the first component.
void matx_Attribute(vec4 value, out vec3 color, out vec3 vector, out float fac, out float alpha)
{
	color = value.rgb;
	vector = value.xyz;
	fac = value.x;
	alpha = value.a;
}
