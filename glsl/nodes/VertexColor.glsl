// @type VertexColor
// @category Input
// @out vec3 color
// @out float alpha
// @attr color
// The geometry's point colour (the POP Color attribute, Cd of a SOP), times the instance colour
// when the Geometry COMP is instancing. White when the geometry has none.
void matx_VertexColor(out vec3 color, out float alpha)
{
	vec4 c = TDPixelColor(iVert.color);
	color = c.rgb;
	alpha = c.a;
}
