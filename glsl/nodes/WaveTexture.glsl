// @type WaveTexture
// @category Texture
// @menu wave_type bands rings
// @menu bands_direction x y z diagonal
// @menu rings_direction x y z spherical
// @menu profile sine saw triangle
// @in vec3 vector = uv
// @in float scale = 5.0
// @in float distortion = 0.0
// @in float detail = 2.0
// @in float detail_scale = 1.0
// @in float detail_roughness = 0.5
// @in float phase_offset = 0.0
// @out vec3 color
// @out float fac
// @requires fbm
// Blender's Wave Texture: parallel bands or concentric rings. bands_direction and
// rings_direction apply to their own wave type (rings around an axis, or spherical).
// distortion warps the waves with fractal noise (detail, detail_scale, detail_roughness);
// phase_offset slides them, so animate it to make them travel.
void matx_WaveTexture(int wave_type, int bands_direction, int rings_direction, int profile, vec3 vector,
                      float scale, float distortion, float detail, float detail_scale,
                      float detail_roughness, float phase_offset, out vec3 color, out float fac)
{
	const float PI = 3.14159265358979;
	vec3 p = vector * scale;
	p = (p + 0.000001) * 0.999999;   // avoids precision issues on unit coordinates
	float n;
	if (wave_type == MATX_WAVETEXTURE_WAVE_TYPE_BANDS)
	{
		switch (bands_direction)
		{
			case MATX_WAVETEXTURE_BANDS_DIRECTION_X: n = p.x * 20.0; break;
			case MATX_WAVETEXTURE_BANDS_DIRECTION_Y: n = p.y * 20.0; break;
			case MATX_WAVETEXTURE_BANDS_DIRECTION_Z: n = p.z * 20.0; break;
			default:                                 n = (p.x + p.y + p.z) * 10.0; break;
		}
	}
	else
	{
		vec3 rp = p;
		switch (rings_direction)
		{
			case MATX_WAVETEXTURE_RINGS_DIRECTION_X: rp *= vec3(0.0, 1.0, 1.0); break;
			case MATX_WAVETEXTURE_RINGS_DIRECTION_Y: rp *= vec3(1.0, 0.0, 1.0); break;
			case MATX_WAVETEXTURE_RINGS_DIRECTION_Z: rp *= vec3(1.0, 1.0, 0.0); break;
			default: break;   // spherical
		}
		n = length(rp) * 20.0;
	}
	n += phase_offset;
	if (distortion != 0.0)
		n += distortion * (matx_fbm(p * detail_scale, detail, detail_roughness, 2.0) * 2.0 - 1.0);
	switch (profile)
	{
		case MATX_WAVETEXTURE_PROFILE_SAW:
			n /= 2.0 * PI;
			fac = n - floor(n);
			break;
		case MATX_WAVETEXTURE_PROFILE_TRIANGLE:
			n /= 2.0 * PI;
			fac = abs(n - floor(n + 0.5)) * 2.0;
			break;
		default:
			fac = 0.5 + 0.5 * sin(n - PI / 2.0);
			break;
	}
	color = vec3(fac);
}
