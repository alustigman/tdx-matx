// @type Time
// @category Input
// @in float time = 0.0
// @uniform time = absTime.seconds
// @out float seconds
// Running time in seconds, for animated shaders. The Time parameter holds the expression
// absTime.seconds and is always a uniform on the GLSL MAT, so the shader is not recompiled as
// it changes; write another expression (a speed, a Timer CHOP) to drive it differently.
void matx_Time(float time, out float seconds)
{
	seconds = time;
}
