sampler2D s_src : register(s0);
float flipY : register(c0);
struct QUAD_OUT
{
	float4 pos : POSITION;
	float2 uv : TEXCOORD0;
};
float4 main(QUAD_OUT i) : COLOR0
{
	float2 uv = i.uv;
	if (flipY != 0.0) { uv.y = 1.0 - uv.y; }
	float4 c = floor(tex2D(s_src, uv) * 255.0 + 0.5);
	float r3 = floor(c.r / 8.0);
	float g3 = floor(c.g / 8.0);
	float b3 = floor(c.b / 8.0);
	float a1 = floor(c.a / 128.0);
	float px16 = r3 + g3 * 32.0 + b3 * 1024.0 + a1 * 32768.0;
	float lo = px16 - floor(px16 / 256.0) * 256.0;
	float hi = floor(px16 / 256.0);
	return float4(lo / 255.0, hi / 255.0, 0.0, 0.0);
}
