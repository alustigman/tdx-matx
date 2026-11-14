// @type MatcapUV
// @category Vector
// @in vec3 normal = world_normal
// @out vec3 uv
// Texture coordinates for a matcap (an image of a lit sphere): the normal as the camera sees
// it, mapped to 0-1. Plug it into a Sampler's vector and the sphere's lighting wraps the object.
void matx_MatcapUV(vec3 normal, out vec3 uv)
{
	vec3 n = normalize(uTDMats[iVert.cameraIndex].camForNormals * normalize(normal));
	uv = vec3(n.xy * 0.5 + 0.5, 0.0);
}
