// @type Sampler
// @category Texture
// @sampler sampler2D image
// @in vec3 vector = uv
// @out vec3 color
// @out float alpha
// Samples the TOP set on the node. `vector` defaults to the mesh UV (uv set 0); connect any
// vec3 to remap it (only .xy is used).
void matx_Sampler(sampler2D image, vec3 vector, out vec3 color, out float alpha)
{
	vec4 c = texture(image, vector.xy);
	color = c.rgb;
	alpha = c.a;
}
