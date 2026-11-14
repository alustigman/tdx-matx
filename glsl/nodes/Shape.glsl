// @type Shape
// @category Texture
// @menu shape circle rectangle rounded_rectangle polygon
// @in vec3 vector = uv
// @in vec3 center = 0.5 0.5 0.0 [0 1]
// @in float width = 0.5
// @in float height = 0.5
// @in float radius = 0.1 [0 0.5]
// @in float sides = 6.0 [3 12]
// @in float softness = 0.005 [0 0.2]
// @out float fac
// @out float distance
// A 2D shape in the vector's xy plane, centred on center: fac is 1 inside and 0 outside (softness
// is the width of the edge), distance is the signed distance to the outline (negative inside).
// Circle is an ellipse of width by height; radius rounds the corners of the rounded rectangle;
// polygon has `sides` sides and is `width` across.
void matx_Shape(int shape, vec3 vector, vec3 center, float width, float height, float radius, float sides,
                float softness, out float fac, out float dist)
{
	const float PI = 3.14159265358979;
	vec2 p = vector.xy - center.xy;
	vec2 halfSize = max(0.5 * vec2(width, height), vec2(0.00001));
	switch (shape)
	{
		case MATX_SHAPE_SHAPE_RECTANGLE:
		{
			vec2 q = abs(p) - halfSize;
			dist = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
			break;
		}
		case MATX_SHAPE_SHAPE_ROUNDED_RECTANGLE:
		{
			float r = clamp(radius, 0.0, min(halfSize.x, halfSize.y));
			vec2 q = abs(p) - halfSize + r;
			dist = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
			break;
		}
		case MATX_SHAPE_SHAPE_POLYGON:
		{
			float n = max(floor(sides + 0.5), 3.0);
			float a = atan(p.x, p.y) + PI;
			float slice = 2.0 * PI / n;
			dist = cos(floor(0.5 + a / slice) * slice - a) * length(p) - halfSize.x;
			break;
		}
		default:   // circle: an ellipse, its distance scaled back to the smaller radius
			dist = (length(p / halfSize) - 1.0) * min(halfSize.x, halfSize.y);
			break;
	}
	float edge = max(softness, 0.00001);
	fac = 1.0 - smoothstep(-edge, edge, dist);
}
