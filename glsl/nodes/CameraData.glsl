// @type CameraData
// @category Input
// @out vec3 view_vector
// @out float view_z_depth
// @out float view_distance
// The shaded point seen from the camera. view_vector is its direction in camera space (the
// camera looks down -Z), view_z_depth its distance along the camera's axis, view_distance its
// straight-line distance.
void matx_CameraData(out vec3 view_vector, out float view_z_depth, out float view_distance)
{
	vec3 camPos = (uTDMats[iVert.cameraIndex].cam * vec4(iVert.worldSpacePos.xyz, 1.0)).xyz;
	view_distance = length(camPos);
	view_vector = view_distance > 0.0 ? camPos / view_distance : vec3(0.0, 0.0, -1.0);
	view_z_depth = -camPos.z;
}
