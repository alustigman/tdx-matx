// @type VoronoiTexture
// @category Texture
// @menu dimensions 3d 1d 2d 4d
// @menu feature f1 f2 smooth_f1 distance_to_edge n_sphere_radius
// @menu metric euclidean manhattan chebychev minkowski
// @in vec3 vector = uv
// @in float w = 0.0
// @in float scale = 5.0
// @in float smoothness = 1.0
// @in float exponent = 0.5 [0 4]
// @in float randomness = 1.0
// @out float distance
// @out vec3 color
// @out vec3 position
// @out float w_out
// @out float radius
// @requires hash
// @enable w if dimensions 1d 4d
// @enable smoothness if feature smooth_f1
// @enable metric unless feature distance_to_edge n_sphere_radius
// @enable exponent if metric minkowski
// @enable exponent unless feature distance_to_edge n_sphere_radius
// Blender's Voronoi Texture: cells around randomly placed points. dimensions picks what is
// sampled (1D is w alone, 2D vector.xy, 3D vector, 4D vector and w). feature picks the output:
// F1 the distance to the closest point, F2 to the second closest, Smooth F1 a blended F1
// (smoothness), Distance To Edge the distance to the cell border, N-Sphere Radius the radius of
// the largest sphere around the closest point (written to radius and distance). metric is the
// distance used by F1, F2 and Smooth F1 (exponent is Minkowski's); randomness 0 is a regular
// grid. color and position (and w_out in 1D and 4D) describe the cell found.
#define MATX_VORONOI_CELLS(R) for (int l = -R.w; l <= R.w; l++) for (int k = -R.z; k <= R.z; k++) for (int j = -R.y; j <= R.y; j++) for (int i = -R.x; i <= R.x; i++)

float matx_voronoi_metric(int metric, vec4 a, vec4 b, float exponent)
{
	vec4 d = abs(a - b);
	switch (metric)
	{
		case MATX_VORONOITEXTURE_METRIC_MANHATTAN: return d.x + d.y + d.z + d.w;
		case MATX_VORONOITEXTURE_METRIC_CHEBYCHEV: return max(max(d.x, d.y), max(d.z, d.w));
		case MATX_VORONOITEXTURE_METRIC_MINKOWSKI:
			return pow(pow(d.x, exponent) + pow(d.y, exponent) + pow(d.z, exponent) + pow(d.w, exponent),
			           1.0 / exponent);
		default: return length(d);
	}
}

// The point of the cell at `cell + offset`, relative to `cell`.
vec4 matx_voronoi_point(vec4 cell, vec4 offset, float randomness, vec4 mask)
{
	return offset + matx_hash_cell(cell + offset) * randomness * mask;
}

void matx_VoronoiTexture(int dimensions, int feature, int metric, vec3 vector, float w, float scale,
                         float smoothness, float exponent, float randomness, out float out_distance,
                         out vec3 color, out vec3 position, out float w_out, out float radius)
{
	// the lattice directions in use
	vec4 mask = vec4(1.0, 1.0, 1.0, 0.0);
	if (dimensions == MATX_VORONOITEXTURE_DIMENSIONS_1D)
		mask = vec4(0.0, 0.0, 0.0, 1.0);
	else if (dimensions == MATX_VORONOITEXTURE_DIMENSIONS_2D)
		mask = vec4(1.0, 1.0, 0.0, 0.0);
	else if (dimensions == MATX_VORONOITEXTURE_DIMENSIONS_4D)
		mask = vec4(1.0);
	ivec4 r = ivec4(mask);
	vec4 p = vec4(vector, w) * scale * mask;
	vec4 cell = floor(p);
	vec4 local = p - cell;
	randomness = clamp(randomness, 0.0, 1.0);
	exponent = max(exponent, 0.0001);
	smoothness = clamp(smoothness / 2.0, 0.0, 0.5);

	out_distance = 0.0;
	color = vec3(0.0);
	radius = 0.0;
	vec4 found = vec4(0.0);   // the output position, in scaled coordinates

	if (feature == MATX_VORONOITEXTURE_FEATURE_DISTANCE_TO_EDGE)
	{
		vec4 toClosest = vec4(0.0);
		float minDist = 1e30;
		MATX_VORONOI_CELLS(r)
		{
			vec4 v = matx_voronoi_point(cell, vec4(i, j, k, l), randomness, mask) - local;
			float d = dot(v, v);
			if (d < minDist)
			{
				minDist = d;
				toClosest = v;
			}
		}
		minDist = 1e30;
		MATX_VORONOI_CELLS(r)
		{
			vec4 v = matx_voronoi_point(cell, vec4(i, j, k, l), randomness, mask) - local;
			vec4 perpendicular = v - toClosest;
			if (dot(perpendicular, perpendicular) > 0.0001)
				minDist = min(minDist, dot((toClosest + v) / 2.0, normalize(perpendicular)));
		}
		out_distance = minDist;
	}
	else if (feature == MATX_VORONOITEXTURE_FEATURE_N_SPHERE_RADIUS)
	{
		vec4 closest = vec4(0.0);
		vec4 closestOffset = vec4(0.0);
		float minDist = 1e30;
		MATX_VORONOI_CELLS(r)
		{
			vec4 pp = matx_voronoi_point(cell, vec4(i, j, k, l), randomness, mask);
			float d = distance(pp, local);
			if (d < minDist)
			{
				minDist = d;
				closest = pp;
				closestOffset = vec4(i, j, k, l);
			}
		}
		minDist = 1e30;
		MATX_VORONOI_CELLS(r)
		{
			if (i == 0 && j == 0 && k == 0 && l == 0)
				continue;
			vec4 pp = matx_voronoi_point(cell, vec4(i, j, k, l) + closestOffset, randomness, mask);
			minDist = min(minDist, distance(closest, pp));
		}
		radius = minDist / 2.0;
		out_distance = radius;
	}
	else if (feature == MATX_VORONOITEXTURE_FEATURE_F2)
	{
		float distF1 = 1e30;
		float distF2 = 1e30;
		vec4 offsetF1 = vec4(0.0), positionF1 = vec4(0.0);
		vec4 offsetF2 = vec4(0.0), positionF2 = vec4(0.0);
		MATX_VORONOI_CELLS(r)
		{
			vec4 offset = vec4(i, j, k, l);
			vec4 pp = matx_voronoi_point(cell, offset, randomness, mask);
			float d = matx_voronoi_metric(metric, pp, local, exponent);
			if (d < distF1)
			{
				distF2 = distF1;
				distF1 = d;
				offsetF2 = offsetF1;
				offsetF1 = offset;
				positionF2 = positionF1;
				positionF1 = pp;
			}
			else if (d < distF2)
			{
				distF2 = d;
				offsetF2 = offset;
				positionF2 = pp;
			}
		}
		out_distance = distF2;
		color = matx_hash_cell(cell + offsetF2).xyz;
		found = positionF2 + cell;
	}
	else if (feature == MATX_VORONOITEXTURE_FEATURE_SMOOTH_F1 && smoothness > 0.0)
	{
		float smoothDistance = 8.0;
		vec3 smoothColor = vec3(0.0);
		vec4 smoothPosition = vec4(0.0);
		ivec4 r2 = 2 * r;   // the blend reaches two cells away
		MATX_VORONOI_CELLS(r2)
		{
			vec4 offset = vec4(i, j, k, l);
			vec4 pp = matx_voronoi_point(cell, offset, randomness, mask);
			float d = matx_voronoi_metric(metric, pp, local, exponent);
			float h = smoothstep(0.0, 1.0, 0.5 + 0.5 * (smoothDistance - d) / smoothness);
			float correction = smoothness * h * (1.0 - h);
			smoothDistance = mix(smoothDistance, d, h) - correction;
			correction /= 1.0 + 3.0 * smoothness;
			smoothColor = mix(smoothColor, matx_hash_cell(cell + offset).xyz, h) - correction;
			smoothPosition = mix(smoothPosition, pp, h) - correction;
		}
		out_distance = smoothDistance;
		color = smoothColor;
		found = smoothPosition + cell;
	}
	else   // F1
	{
		float minDist = 1e30;
		vec4 targetOffset = vec4(0.0);
		vec4 targetPosition = vec4(0.0);
		MATX_VORONOI_CELLS(r)
		{
			vec4 offset = vec4(i, j, k, l);
			vec4 pp = matx_voronoi_point(cell, offset, randomness, mask);
			float d = matx_voronoi_metric(metric, pp, local, exponent);
			if (d < minDist)
			{
				minDist = d;
				targetOffset = offset;
				targetPosition = pp;
			}
		}
		out_distance = minDist;
		color = matx_hash_cell(cell + targetOffset).xyz;
		found = targetPosition + cell;
	}
	found = scale != 0.0 ? found * mask / scale : vec4(0.0);
	position = found.xyz;
	w_out = found.w;
}
