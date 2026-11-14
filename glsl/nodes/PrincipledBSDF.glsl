// @type PrincipledBSDF
// @category Shader
// @in vec3 base_color = 0.8
// @in float metallic = 0.0
// @in float roughness = 0.5
// @in float specular_level = 0.5
// @in vec3 emission = 0.0
// @in float alpha = 1.0
// @in float ambient_occlusion = 1.0
// @in float shadow_strength = 1.0
// @in vec3 shadow_color = 0.0
// @in float emission_strength = 1.0
// @in vec3 normal = world_normal
// @out closure bsdf
// @attr color
// @requires lighting
// TouchDesigner's PBR material as a shading node, following the PBR MAT's exported shader:
// vertex colour multiplies the base colour, alpha is premultiplied. `normal` takes a Normal Map
// or Bump node; unconnected it is the surface normal.
void matx_PrincipledBSDF(vec3 base_color, float metallic, float roughness, float specular_level,
                         vec3 emission, float alpha, float ambient_occlusion,
                         float shadow_strength, vec3 shadow_color, float emission_strength,
                         vec3 normal, out MatxClosure bsdf)
{
	vec4 vertColor = TDPixelColor(iVert.color);

	// 0.08 is the value for dielectric specular that
	// Substance Designer uses for its top end.
	float specLevel = 0.08 * specular_level;

	vec4 finalBaseColor = vec4(base_color * alpha, alpha) * vertColor;

	vec3 pbrDiffuseColor = finalBaseColor.rgb * (1.0 - metallic);
	vec3 pbrSpecularColor = mix(vec3(specLevel), finalBaseColor.rgb, metallic);

	bsdf.radiance = matx_pbr_lighting(pbrDiffuseColor, pbrSpecularColor, normal, roughness,
	                                  ambient_occlusion, shadow_strength, shadow_color)
	                + emission * emission_strength;
	bsdf.alpha = finalBaseColor.a;
}
