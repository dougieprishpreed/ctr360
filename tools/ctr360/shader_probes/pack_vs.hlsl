float posFlipY : register(c0);
struct QUAD_OUT
{
	float4 pos : POSITION;
	float2 uv : TEXCOORD0;
};
QUAD_OUT main(float2 a_position : POSITION)
{
	QUAD_OUT o;
	o.uv = a_position * 0.5 + 0.5;
	o.pos = float4(a_position.x, a_position.y * posFlipY, 0.0, 1.0);
	return o;
}
