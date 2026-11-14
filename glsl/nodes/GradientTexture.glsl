// @type GradientTexture
// @category Texture
// @menu gradient_type linear quadratic easing diagonal radial quadratic_sphere spherical
// @in vec3 vector = uv
// @out vec3 color
// @out float fac
// Blender's Gradient Texture: a 0-1 ramp over the vector. Linear, quadratic and easing run
// along x, diagonal along x + y, radial turns around the origin in the xy plane, and the two
// spheres fall off with the distance from the origin (centre the vector with a Mapping node).
void matx_GradientTexture(int gradient_type, vec3 vector, out vec3 color, out float fac)
{
	const float PI = 3.14159265358979;
	float x = vector.x;
	float y = vector.y;
	float f;
	switch (gradient_type)
	{
		case MATX_GRADIENTTEXTURE_GRADIENT_TYPE_QUADRATIC:
		{
			float r = max(x, 0.0);
			f = r * r;
			break;
		}
		case MATX_GRADIENTTEXTURE_GRADIENT_TYPE_EASING:
		{
			float r = clamp(x, 0.0, 1.0);
			f = 3.0 * r * r - 2.0 * r * r * r;
			break;
		}
		case MATX_GRADIENTTEXTURE_GRADIENT_TYPE_DIAGONAL:
			f = (x + y) * 0.5;
			break;
		case MATX_GRADIENTTEXTURE_GRADIENT_TYPE_RADIAL:
			f = (x == 0.0 && y == 0.0) ? 0.5 : atan(y, x) / (2.0 * PI) + 0.5;
			break;
		case MATX_GRADIENTTEXTURE_GRADIENT_TYPE_QUADRATIC_SPHERE:
		{
			// biased so that a unit-length vector gives exactly 0
			float r = max(0.999999 - length(vector), 0.0);
			f = r * r;
			break;
		}
		case MATX_GRADIENTTEXTURE_GRADIENT_TYPE_SPHERICAL:
			f = max(0.999999 - length(vector), 0.0);
			break;
		default:
			f = x;
			break;
	}
	fac = clamp(f, 0.0, 1.0);
	color = vec3(fac);
}
