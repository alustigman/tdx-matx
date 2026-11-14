// Integer hashes returning floats in [0, 1): PCG4D (Jarzynski & Olano, "Hash Functions for GPU
// Rendering", 2020). Four independent values per call.

uvec4 matx_pcg4d(uvec4 v)
{
	v = v * 1664525u + 1013904223u;
	v.x += v.y * v.w; v.y += v.z * v.x; v.z += v.x * v.y; v.w += v.y * v.z;
	v ^= v >> 16u;
	v.x += v.y * v.w; v.y += v.z * v.x; v.z += v.x * v.y; v.w += v.y * v.z;
	return v;
}

// Hash of a lattice point: the components of p are whole numbers (negative ones included).
vec4 matx_hash_cell(vec4 p)
{
	return vec4(matx_pcg4d(uvec4(ivec4(p))) >> 8u) * (1.0 / 16777216.0);
}

// Hash of any value: two floats that differ at all give unrelated results.
vec4 matx_hash_float(vec4 p)
{
	return vec4(matx_pcg4d(floatBitsToUint(p + 0.0)) >> 8u) * (1.0 / 16777216.0);   // + 0.0: -0 is 0
}
