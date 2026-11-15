// @type NormalMap
// @category Texture
// @sampler sampler2D image
// @in float strength = 1.0 [0 2]
// @in vec3 vector = uv
// @out vec3 normal
// @attr world_pos world_normal world_tangent
// Samples the TOP set on the node as a tangent-space normal map and turns it into a world-space
// normal for a shader's normal input, as TouchDesigner's PBR MAT does: the tangent frame comes
// from the geometry's T attribute (xyz the tangent, w the handedness), so the geometry needs
// one (a Normal POP with tangents on, or an Attribute Create SOP with Compute Tangents).
// strength scales the map's x and y (the PBR MAT's Bump Scale). `vector` defaults to the mesh
// UV; only .xy is used.
void matx_NormalMap(sampler2D image, float strength, vec3 vector, out vec3 normal)
{
	vec3 N = normalize(iVert.worldSpaceNorm);
	vec3 T = iVert.worldSpaceTangent.xyz;
	if (dot(T, T) <= 0.0)
	{
		normal = N;   // no T attribute: the surface normal
		return;
	}
	mat3 tangentToWorld = TDCreateTBNMatrix(N, normalize(T), iVert.worldSpaceTangent.w);
	vec3 n = 2.0 * (texture(image, vector.xy).xyz - 0.5);
	n.xy *= strength;
	n = tangentToWorld * n;
	normal = dot(n, n) > 0.0 ? normalize(n) : N;
}
