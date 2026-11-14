// @type NormalMap
// @category Vector
// @menu space tangent object world
// @in float strength = 1.0 [0 2]
// @in vec3 color = 0.5 0.5 1.0
// @in vec3 uv = uv
// @out vec3 normal
// @attr world_pos world_normal camera_index
// @requires view
// Turns a normal map's colour into a world-space normal for a shader's normal input. In
// tangent space (the usual blue-ish maps) the tangent frame is rebuilt per pixel from the
// surface and the uv input (connect the same coordinates the map is sampled with), so the
// geometry needs no tangent attribute. strength blends between the surface normal (0) and the
// mapped one (1, and beyond to exaggerate).
void matx_NormalMap(int space, float strength, vec3 color, vec3 uv, out vec3 normal)
{
	vec3 N = matx_shading_normal(iVert.worldSpaceNorm);
	vec3 mapped = color * 2.0 - 1.0;
	if (space == MATX_NORMALMAP_SPACE_OBJECT)
		mapped = uTDMats[iVert.cameraIndex].worldForNormals * mapped;
	else if (space == MATX_NORMALMAP_SPACE_TANGENT)
	{
		// cotangent frame from screen-space derivatives (Schueler, "Followup: Normal Mapping
		// Without Precomputed Tangents")
		vec3 dp1 = dFdx(iVert.worldSpacePos.xyz);
		vec3 dp2 = dFdy(iVert.worldSpacePos.xyz);
		vec2 duv1 = dFdx(uv.xy);
		vec2 duv2 = dFdy(uv.xy);
		vec3 dp2perp = cross(dp2, N);
		vec3 dp1perp = cross(N, dp1);
		vec3 T = dp2perp * duv1.x + dp1perp * duv2.x;
		vec3 B = dp2perp * duv1.y + dp1perp * duv2.y;
		float len2 = max(dot(T, T), dot(B, B));
		mapped = len2 > 0.0 ? mat3(T * inversesqrt(len2), B * inversesqrt(len2), N) * mapped : N;
	}
	mapped = dot(mapped, mapped) > 0.0 ? normalize(mapped) : N;
	vec3 blended = N + (mapped - N) * max(strength, 0.0);
	normal = dot(blended, blended) > 0.0 ? normalize(blended) : N;
}
