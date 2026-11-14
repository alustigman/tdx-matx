// @type Triplanar
// @category Texture
// @sampler sampler2D image
// @in vec3 vector = object_pos
// @in vec3 normal = object_normal
// @in float scale = 1.0 [0 4]
// @in float blend = 4.0 [1 16]
// @out vec3 color
// @out float alpha
// Samples the TOP set on the node without texture coordinates: the image is projected along
// x, y and z and the three projections are blended by the direction the surface faces. vector
// and normal default to the geometry's own P and N, so the texture sticks to the object; blend
// sharpens the transition between projections.
void matx_Triplanar(sampler2D image, vec3 vector, vec3 normal, float scale, float blend,
                    out vec3 color, out float alpha)
{
	vec3 p = vector * scale;
	vec3 w = pow(abs(normalize(normal)), vec3(max(blend, 1.0)));
	w /= max(w.x + w.y + w.z, 0.00001);
	vec4 c = texture(image, p.zy) * w.x + texture(image, p.xz) * w.y + texture(image, p.xy) * w.z;
	color = c.rgb;
	alpha = c.a;
}
