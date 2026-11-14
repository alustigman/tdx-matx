// View helpers shared by the nodes that depend on the camera.

// Unit vector from the shaded point to the camera, in world space.
vec3 matx_view_vector()
{
	return normalize(uTDMats[iVert.cameraIndex].camInverse[3].xyz - iVert.worldSpacePos.xyz);
}

// The shading normal: unit length, and flipped on back faces so it faces the camera side.
vec3 matx_shading_normal(vec3 normal)
{
	normal = normalize(normal);
	return TDFrontFacing(iVert.worldSpacePos.xyz, normal) ? normal : -normal;
}

// Fresnel reflectance of a dielectric for the cosine of the incidence angle (Blender's
// fresnel_dielectric_cos).
float matx_fresnel_dielectric(float cosi, float eta)
{
	float c = abs(cosi);
	float g = eta * eta - 1.0 + c * c;
	if (g <= 0.0)
		return 1.0;   // total internal reflection
	g = sqrt(g);
	float a = (g - c) / (g + c);
	float b = (c * (g + c) - 1.0) / (c * (g - c) + 1.0);
	return 0.5 * a * a * (1.0 + b * b);
}
