// @type Fresnel
// @category Input
// @in float ior = 1.5 [1 3]
// @in vec3 normal = world_normal
// @out float fac
// @requires view
// How much a dielectric of this index of refraction reflects at this viewing angle: low facing
// the camera, 1 at grazing angles. Use it as a Mix factor for rim effects.
void matx_Fresnel(float ior, vec3 normal, out float fac)
{
	normal = normalize(normal);
	bool front = TDFrontFacing(iVert.worldSpacePos.xyz, normal);
	float eta = max(ior, 0.00001);
	fac = matx_fresnel_dielectric(dot(matx_view_vector(), normal), front ? eta : 1.0 / eta);
}
