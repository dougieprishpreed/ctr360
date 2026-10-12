float4 sourceRect : register(c0);
struct PRESENT_OUT
{
	float4 pos : POSITION;
	float2 uv : TEXCOORD0;
};
PRESENT_OUT main(float2 a_position : POSITION)
{
	PRESENT_OUT o;
	float2 screenUV = a_position * 0.5 + 0.5;
	float2 sourcePixel = sourceRect.xy + float2(screenUV.x, 1.0 - screenUV.y) * sourceRect.zw;
	o.uv = sourcePixel / float2(1024.0, 512.0);
	o.pos = float4(a_position.x, a_position.y, 0.0, 1.0);
	return o;
}
