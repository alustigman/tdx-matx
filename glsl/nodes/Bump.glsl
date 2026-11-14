// @type Bump
// @category Vector
// @menu invert off on
// @in float strength = 1.0 [0 1]
// @in float distance = 1.0 [0 1]
// @in float height = 1.0
// @in vec3 normal = world_normal
// @out vec3 result vector
// Blender's Bump: perturbs the normal as if the surface were displaced by height (connect a
// texture's fac), without moving geometry. distance is how far the height reaches, strength
// blends the effect in, invert makes bumps into dents. The slope is measured between
// neighbouring pixels, so very fine detail can look blocky up close.
void matx_Bump(int invert, float strength, float dist, float height, vec3 normal, out vec3 result)
{
	vec3 N = normalize(normal);
	bool front = TDFrontFacing(iVert.worldSpacePos.xyz, N);
	if (!front)
		N = -N;
	dist *= (invert == MATX_BUMP_INVERT_ON) ? -1.0 : 1.0;
	vec3 dPdx = dFdx(iVert.worldSpacePos.xyz);
	vec3 dPdy = dFdy(iVert.worldSpacePos.xyz);
	vec3 Rx = cross(dPdy, N);
	vec3 Ry = cross(N, dPdx);
	float det = dot(dPdx, Rx);
	vec3 surfgrad = dFdx(height) * Rx + dFdy(height) * Ry;
	vec3 bumped = abs(det) * N - dist * sign(det) * surfgrad;
	bumped = dot(bumped, bumped) > 0.0 ? normalize(bumped) : N;
	vec3 blended = mix(N, bumped, max(strength, 0.0));
	result = dot(blended, blended) > 0.0 ? normalize(blended) : N;
}
