// @type PrincipledBSDF
// @in vec3 base_color = 0.8
// @in float metallic = 0.0
// @in float roughness = 0.5
// @in float specular_level = 0.5
// @in vec3 emission = 0.0
// @in float alpha = 1.0
// @in float ambient_occlusion = 1.0
// @in float shadow_strength = 1.0
// @in vec3 shadow_color = 0.0
// @out closure bsdf
// @attr color world_pos world_normal camera_index
void matx_PrincipledBSDF(vec3 base_color, float metallic, float roughness, float specular_level,
                         vec3 emission, float alpha, float ambient_occlusion,
                         float shadow_strength, vec3 shadow_color, out MatxClosure bsdf)
{
	vec3 diffuseSum = vec3(0.0);
	vec3 specularSum = vec3(0.0);

	vec3 worldSpaceNorm = normalize(iVert.worldSpaceNorm.xyz);
	vec3 normal = worldSpaceNorm;
	vec3 viewVec = normalize(uTDMats[iVert.cameraIndex].camInverse[3].xyz - iVert.worldSpacePos.xyz);

	vec4 vertColor = TDPixelColor(iVert.color);

	// 0.08 is the value for dielectric specular that
	// Substance Designer uses for its top end.
	float specLevel = 0.08 * specular_level;

	vec4 finalBaseColor = vec4(base_color * alpha, alpha) * vertColor;

	// A roughness of exactly 0 is not allowed
	roughness = max(roughness, 0.0001);

	vec3 pbrDiffuseColor = finalBaseColor.rgb * (1.0 - metallic);
	vec3 pbrSpecularColor = mix(vec3(specLevel), finalBaseColor.rgb, metallic);

	// Flip the normals on backfaces
	if (!TDFrontFacing(iVert.worldSpacePos.xyz, worldSpaceNorm.xyz))
	{
		normal = -normal;
	}

	for (int i = 0; i < TD_NUM_LIGHTS; i++)
	{
		TDPBRResult res;
		res = TDLightingPBR(i, pbrDiffuseColor, pbrSpecularColor, iVert.worldSpacePos.xyz,
		                    normal, shadow_strength, shadow_color, viewVec, roughness);
		diffuseSum += res.diffuse;
		specularSum += res.specular;
	}

	// Environment lights
	for (int i = 0; i < TD_NUM_ENV_LIGHTS; i++)
	{
		TDPBRResult res;
		res = TDEnvLightingPBR(i, pbrDiffuseColor, pbrSpecularColor, normal, viewVec,
		                       roughness, ambient_occlusion);
		diffuseSum += res.diffuse;
		specularSum += res.specular;
	}

	bsdf.radiance = diffuseSum + specularSum + emission;
	bsdf.alpha = finalBaseColor.a;
}
