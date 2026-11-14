// @requires view
// TouchDesigner's PBR lighting summed over every Light COMP and Environment Light COMP of the
// render. `normal` is a world-space normal (any length); roughness 0 is not allowed by TD.
vec3 matx_pbr_lighting(vec3 diffuseColor, vec3 specularColor, vec3 normal, float roughness,
                       float ambientOcclusion, float shadowStrength, vec3 shadowColor)
{
	vec3 diffuseSum = vec3(0.0);
	vec3 specularSum = vec3(0.0);
	vec3 viewVec = matx_view_vector();
	normal = matx_shading_normal(normal);
	roughness = max(roughness, 0.0001);

	for (int i = 0; i < TD_NUM_LIGHTS; i++)
	{
		TDPBRResult res;
		res = TDLightingPBR(i, diffuseColor, specularColor, iVert.worldSpacePos.xyz,
		                    normal, shadowStrength, shadowColor, viewVec, roughness);
		diffuseSum += res.diffuse;
		specularSum += res.specular;
	}

	// Environment lights
	for (int i = 0; i < TD_NUM_ENV_LIGHTS; i++)
	{
		TDPBRResult res;
		res = TDEnvLightingPBR(i, diffuseColor, specularColor, normal, viewVec,
		                       roughness, ambientOcclusion);
		diffuseSum += res.diffuse;
		specularSum += res.specular;
	}
	return diffuseSum + specularSum;
}
