// @type TexCoord
// @category Input
// @attrib vec3 attribute = Tex texcoord
// @out vec3 uv
// @out vec3 window vector
// Texture coordinates. `uv` is the geometry attribute named on the node (Tex by default: the
// POP texture attribute, and texture layer 0 of a SOP). `window` is the pixel's position in the
// render, 0-1 from the bottom left.
void matx_TexCoord(vec3 value, out vec3 uv, out vec3 window)
{
	uv = value;
	window = vec3((gl_FragCoord.xy - uTDGeneral.viewport.xy) * uTDGeneral.viewport.zw, 0.0);
}
