// @type PrincipledBSDF
// @in vec3 base_color = 0.8
// @in float metallic = 0.0
// @in float roughness = 0.5
// @in vec3 emission = 0.0
// @in float alpha = 1.0
// @in float ambient_occlusion = 1.0
// @out closure bsdf
// @attr world_pos world_normal
void matx_PrincipledBSDF(vec3 base_color, float metallic, float roughness, vec3 emission,
                         float alpha, float ambient_occlusion, out MatxClosure bsdf)
{
	vec3 diffuseColor = base_color * (1.0 - metallic);
	vec3 specularColor = mix(vec3(0.04), base_color, metallic);
	vec3 N = normalize(vWorldNormal);
	vec3 V = normalize(uTDMats[TDCameraIndex()].camInverse[3].xyz - vWorldPos);

	vec3 diffuse = vec3(0.0);
	vec3 specular = vec3(0.0);

	for (int i = 0; i < TD_NUM_LIGHTS; i++) {
		TDPBRResult res = TDLightingPBR(i, diffuseColor, specularColor, vWorldPos, N,
		                                1.0, vec3(0.0), V, roughness);
		diffuse += res.diffuse;
		specular += res.specular;
	}
	for (int i = 0; i < TD_NUM_ENV_LIGHTS; i++) {
		vec3 diffuseContrib = vec3(0.0);
		vec3 specularContrib = vec3(0.0);
		TDEnvLightingPBR(diffuseContrib, specularContrib, i, diffuseColor, specularColor,
		                 N, V, roughness, ambient_occlusion);
		diffuse += diffuseContrib;
		specular += specularContrib;
	}
	bsdf.radiance = diffuse + specular + emission;
	bsdf.alpha = alpha;
}
