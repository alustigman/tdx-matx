// Fractal Brownian motion of TDPerlinNoise in 3D, normalized to 0-1 (Blender's noise_fbm).
// detail is the number of octaves above the first (fractions blend the last one in, up to 15),
// roughness the amplitude ratio between octaves, lacunarity their frequency ratio.
float matx_fbm(vec3 p, float detail, float roughness, float lacunarity)
{
	detail = clamp(detail, 0.0, 15.0);
	roughness = max(roughness, 0.0);
	int octaves = int(detail);
	float fscale = 1.0;
	float amp = 1.0;
	float maxamp = 0.0;
	float sum = 0.0;
	for (int i = 0; i <= octaves; i++)
	{
		sum += TDPerlinNoise(fscale * p) * amp;
		maxamp += amp;
		amp *= roughness;
		fscale *= lacunarity;
	}
	float rmd = detail - float(octaves);
	float value = 0.5 * sum / maxamp + 0.5;
	if (rmd != 0.0)
	{
		float sum2 = sum + TDPerlinNoise(fscale * p) * amp;
		value = mix(value, 0.5 * sum2 / (maxamp + amp) + 0.5, rmd);
	}
	return value;
}
