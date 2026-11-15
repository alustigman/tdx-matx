// @type Bump
// @category Vector
// @menu invert off on
// @menu quality low high
// @in float strength = 1.0 [0 1]
// @in float distance = 1.0 [0 1]
// @in float filter_width = 0.1 [0 1]
// @in float height = 1.0
// @in vec3 normal = world_normal
// @out vec3 result vector
// @differentiate height by filter_width if quality high
// @enable filter_width if quality high
// Blender's Bump: perturbs the normal as if the surface were displaced by height (connect a
// texture's fac), without moving geometry. distance is how far the height reaches, strength
// blends the effect in, invert makes bumps into dents.
// quality low measures the height's slope between the pixels of each 2x2 block, so fine detail
// looks blocky up close. quality high evaluates the graph feeding height again as at the pixel
// filter_width of a pixel to the right and above (height_dx, height_dy): smooth and exact for any
// procedural texture, at the cost of running that part of the graph three times.
void matx_Bump(int invert, int quality, float strength, float dist, float filter_width,
               float height, float height_dx, float height_dy, vec3 normal, out vec3 result)
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
	// the height's change over one pixel (low), or over filter_width of one (high), along x and y
	vec2 dH = vec2(dFdx(height), dFdy(height));
	float width = 1.0;
	if (quality == MATX_BUMP_QUALITY_HIGH) {
		dH = vec2(height_dx, height_dy) - height;
		width = filter_width;
	}
	vec3 surfgrad = dH.x * Rx + dH.y * Ry;
	vec3 bumped = width * abs(det) * N - dist * sign(det) * surfgrad;
	bumped = dot(bumped, bumped) > 0.0 ? normalize(bumped) : N;
	vec3 blended = mix(N, bumped, max(strength, 0.0));
	result = dot(blended, blended) > 0.0 ? normalize(blended) : N;
}
