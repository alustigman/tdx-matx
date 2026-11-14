// @type ToonBSDF
// @category Shader
// @in vec3 color = 0.8
// @in float steps = 3.0 [1 8]
// @in float smoothness = 0.1
// @in vec3 normal = world_normal
// @out closure bsdf
// @requires lighting
// Cel shading: the scene's diffuse lighting cut into `steps` flat bands of the colour.
// smoothness softens the edges between bands (0 is a hard edge). The brightest band is what a
// Diffuse BSDF shows facing a light of dimmer 1, so brighter lights only add to the top band.
void matx_ToonBSDF(vec3 color, float steps, float smoothness, vec3 normal, out MatxClosure bsdf)
{
	const float PI = 3.14159265358979;
	vec3 lit = matx_pbr_lighting(vec3(1.0), vec3(0.0), normal, 1.0, 1.0, 1.0, vec3(0.0));
	float raw = dot(lit, vec3(0.2126, 0.7152, 0.0722));
	steps = max(floor(steps + 0.5), 1.0);
	// a white Lambert surface facing a light of dimmer 1 reflects 1 / PI
	float x = raw * PI * steps;
	float s = clamp(smoothness, 0.0, 1.0) * 0.5;
	float band = floor(x) + (s > 0.0 ? smoothstep(0.5 - s, 0.5 + s, fract(x)) : step(0.5, fract(x)));
	// keep the light's tint, replace its brightness by the band's
	vec3 tint = raw > 0.0 ? lit / raw : vec3(1.0);
	bsdf.radiance = color * tint * (band / steps) / PI;
	bsdf.alpha = 1.0;
}
