// @type Mapping
// @category Vector
// @menu mapping_type point texture vector normal
// @in vec3 vector = uv
// @in vec3 location = 0.0 [-1 1]
// @in vec3 rotation = 0.0 [-180 180]
// @in vec3 scale = 1.0 [0 4]
// @out vec3 result
// @enable location unless mapping_type vector normal
// Blender's Mapping: moves, rotates and scales a vector, usually texture coordinates on their
// way into a texture. rotation is in degrees around x, y and z (applied in that order). Point
// transforms the vector itself; Texture transforms the texture instead (the inverse: a location
// of 0.5 moves the pattern, a scale of 2 makes it twice as large); Vector ignores location;
// Normal is for normals (inverse scale, renormalized).
void matx_Mapping(int mapping_type, vec3 vector, vec3 location, vec3 rotation, vec3 scale, out vec3 result)
{
	vec3 r = radians(rotation);
	mat3 rot = TDRotateZ(r.z) * TDRotateY(r.y) * TDRotateX(r.x);
	vec3 safeScale = vec3(scale.x != 0.0 ? scale.x : 1.0, scale.y != 0.0 ? scale.y : 1.0,
	                      scale.z != 0.0 ? scale.z : 1.0);
	switch (mapping_type)
	{
		case MATX_MAPPING_MAPPING_TYPE_TEXTURE: result = (transpose(rot) * (vector - location)) / safeScale; break;
		case MATX_MAPPING_MAPPING_TYPE_VECTOR:  result = rot * (vector * scale); break;
		case MATX_MAPPING_MAPPING_TYPE_NORMAL:
		{
			vec3 n = rot * (vector / safeScale);
			result = dot(n, n) > 0.0 ? normalize(n) : vec3(0.0);
			break;
		}
		default: result = rot * (vector * scale) + location; break;
	}
}
