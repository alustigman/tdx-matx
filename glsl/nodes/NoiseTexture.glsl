// @type NoiseTexture
// @category Texture
// @menu dimensions 3d 1d 2d 4d
// @menu type fbm multifractal hybrid_multifractal ridged_multifractal hetero_terrain
// @menu normalize on off
// @in vec3 vector = uv
// @in float w = 0.0
// @in float scale = 5.0
// @in float detail = 2.0 [0 15]
// @in float roughness = 0.5
// @in float lacunarity = 2.0 [0 4]
// @in float offset = 0.0 [-1 1]
// @in float gain = 1.0 [0 4]
// @in float distortion = 0.0 [0 4]
// @out float fac
// @out vec3 color
// @enable w if dimensions 1d 4d
// @enable normalize if type fbm
// @enable offset if type hybrid_multifractal ridged_multifractal hetero_terrain
// @enable gain if type hybrid_multifractal ridged_multifractal
// Blender's Noise Texture on TouchDesigner's Perlin noise. dimensions picks what is sampled: 1D
// is w alone, 2D vector.xy, 3D vector, 4D vector and w (animate w to evolve the pattern in
// place). detail adds octaves (up to 15), roughness and lacunarity are their amplitude and
// frequency ratios, distortion warps the coordinates. normalize remaps fBM to 0-1 (off: signed,
// around 0); the other types are not normalized, and offset and gain only apply to them.
float matx_noise_signed(int dimensions, vec4 p)
{
	switch (dimensions)
	{
		case MATX_NOISETEXTURE_DIMENSIONS_1D: return TDPerlinNoise(vec2(p.w, 0.0));
		case MATX_NOISETEXTURE_DIMENSIONS_2D: return TDPerlinNoise(p.xy);
		case MATX_NOISETEXTURE_DIMENSIONS_4D: return TDPerlinNoise(p);
		default:                              return TDPerlinNoise(p.xyz);
	}
}

float matx_noise_fractal(int dimensions, int type, int normalize_mode, vec4 p, float detail,
                         float roughness, float lacunarity, float offset, float gain)
{
	detail = clamp(detail, 0.0, 15.0);
	roughness = max(roughness, 0.0);
	int octaves = int(detail);
	float rmd = detail - float(octaves);
	switch (type)
	{
		case MATX_NOISETEXTURE_TYPE_MULTIFRACTAL:
		{
			float value = 1.0;
			float pwr = 1.0;
			for (int i = 0; i <= octaves; i++)
			{
				value *= pwr * matx_noise_signed(dimensions, p) + 1.0;
				pwr *= roughness;
				p *= lacunarity;
			}
			if (rmd != 0.0)
				value *= rmd * pwr * matx_noise_signed(dimensions, p) + 1.0;
			return value;
		}
		case MATX_NOISETEXTURE_TYPE_HYBRID_MULTIFRACTAL:
		{
			float pwr = 1.0;
			float value = 0.0;
			float weight = 1.0;
			for (int i = 0; weight > 0.001 && i <= octaves; i++)
			{
				weight = min(weight, 1.0);
				float signal = (matx_noise_signed(dimensions, p) + offset) * pwr;
				pwr *= roughness;
				value += weight * signal;
				weight *= gain * signal;
				p *= lacunarity;
			}
			if (rmd != 0.0 && weight > 0.001)
			{
				weight = min(weight, 1.0);
				value += rmd * weight * (matx_noise_signed(dimensions, p) + offset) * pwr;
			}
			return value;
		}
		case MATX_NOISETEXTURE_TYPE_RIDGED_MULTIFRACTAL:
		{
			float pwr = roughness;
			float signal = offset - abs(matx_noise_signed(dimensions, p));
			signal *= signal;
			float value = signal;
			for (int i = 1; i <= octaves; i++)
			{
				p *= lacunarity;
				float weight = clamp(signal * gain, 0.0, 1.0);
				signal = offset - abs(matx_noise_signed(dimensions, p));
				signal *= signal;
				signal *= weight;
				value += signal * pwr;
				pwr *= roughness;
			}
			return value;
		}
		case MATX_NOISETEXTURE_TYPE_HETERO_TERRAIN:
		{
			float pwr = roughness;
			float value = offset + matx_noise_signed(dimensions, p);
			p *= lacunarity;
			for (int i = 1; i <= octaves; i++)
			{
				value += (matx_noise_signed(dimensions, p) + offset) * pwr * value;
				pwr *= roughness;
				p *= lacunarity;
			}
			if (rmd != 0.0)
				value += rmd * (matx_noise_signed(dimensions, p) + offset) * pwr * value;
			return value;
		}
		default:   // fBM
		{
			float fscale = 1.0;
			float amp = 1.0;
			float maxamp = 0.0;
			float sum = 0.0;
			for (int i = 0; i <= octaves; i++)
			{
				sum += matx_noise_signed(dimensions, fscale * p) * amp;
				maxamp += amp;
				amp *= roughness;
				fscale *= lacunarity;
			}
			bool norm = normalize_mode == MATX_NOISETEXTURE_NORMALIZE_ON;
			float value = norm ? 0.5 * sum / maxamp + 0.5 : sum;
			if (rmd != 0.0)
			{
				float sum2 = sum + matx_noise_signed(dimensions, fscale * p) * amp;
				value = mix(value, norm ? 0.5 * sum2 / (maxamp + amp) + 0.5 : sum2, rmd);
			}
			return value;
		}
	}
}

void matx_NoiseTexture(int dimensions, int type, int normalize_mode, vec3 vector, float w, float scale,
                       float detail, float roughness, float lacunarity, float offset, float gain,
                       float distortion, out float fac, out vec3 color)
{
	vec4 p = vec4(vector, w) * scale;
	if (distortion != 0.0)
	{
		// each component is pushed by its own noise (fixed offsets decorrelate them)
		p += distortion * vec4(matx_noise_signed(dimensions, p + vec4(113.7, 151.3, 127.1, 139.9)),
		                       matx_noise_signed(dimensions, p + vec4(171.9, 107.3, 163.3, 119.1)),
		                       matx_noise_signed(dimensions, p + vec4(131.3, 181.1, 109.7, 157.3)),
		                       matx_noise_signed(dimensions, p + vec4(149.9, 123.7, 173.1, 101.9)));
	}
	fac = matx_noise_fractal(dimensions, type, normalize_mode, p, detail, roughness, lacunarity, offset, gain);
	color = vec3(fac,
	             matx_noise_fractal(dimensions, type, normalize_mode, p + vec4(137.1, 193.7, 111.3, 167.9),
	                                detail, roughness, lacunarity, offset, gain),
	             matx_noise_fractal(dimensions, type, normalize_mode, p + vec4(179.3, 103.1, 191.9, 143.3),
	                                detail, roughness, lacunarity, offset, gain));
}
