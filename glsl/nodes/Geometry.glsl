// @type Geometry
// @category Input
// @out vec3 position
// @out vec3 normal
// @out vec3 incoming vector
// @out vec3 object_position
// @out vec3 object_normal
// @out float backfacing
// @attr world_pos world_normal object_pos object_normal camera_index
// @requires view
// The shaded point. position, normal and incoming (the direction towards the camera) are in
// world space, after instancing and deforms; object_position and object_normal are the
// geometry's own P and N. normal faces the camera side; backfacing is 1 on back faces.
void matx_Geometry(out vec3 position, out vec3 normal, out vec3 incoming, out vec3 object_position,
                   out vec3 object_normal, out float backfacing)
{
	position = iVert.worldSpacePos.xyz;
	normal = matx_shading_normal(iVert.worldSpaceNorm);
	incoming = matx_view_vector();
	object_position = iVert.objectPos;
	object_normal = normalize(iVert.objectNorm);
	backfacing = TDFrontFacing(iVert.worldSpacePos.xyz, normalize(iVert.worldSpaceNorm)) ? 0.0 : 1.0;
}
