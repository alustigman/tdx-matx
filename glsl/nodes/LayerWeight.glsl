// @type LayerWeight
// @category Input
// @in float blend = 0.5
// @in vec3 normal = world_normal
// @out float fresnel
// @out float facing
// @requires view
// Blender's Layer Weight: two view-dependent factors for layering shaders. fresnel follows a
// dielectric's reflectance, facing goes from 0 facing the camera to 1 at the silhouette; blend
// biases both towards the first (0) or the second (1) shader.
void matx_LayerWeight(float blend, vec3 normal, out float fresnel, out float facing)
{
	normal = normalize(normal);
	float cosi = dot(matx_view_vector(), normal);
	float eta = max(1.0 - blend, 0.00001);
	fresnel = matx_fresnel_dielectric(cosi, TDFrontFacing(iVert.worldSpacePos.xyz, normal) ? 1.0 / eta : eta);
	facing = abs(cosi);
	if (blend != 0.5)
	{
		float b = clamp(blend, 0.0, 1.0 - 0.00001);
		b = b < 0.5 ? 2.0 * b : 0.5 / (1.0 - b);
		facing = pow(facing, b);
	}
	facing = 1.0 - facing;
}
