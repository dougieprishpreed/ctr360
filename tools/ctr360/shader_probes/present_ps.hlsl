sampler2D s_texture : register(s0);
struct PRESENT_OUT
{
	float4 pos : POSITION;
	float2 uv : TEXCOORD0;
};
float4 main(PRESENT_OUT i) : COLOR0
{
	float2 bytes = floor(tex2D(s_texture, i.uv).rg * 255.0 + 0.5);
	float pixel = bytes.r + bytes.g * 256.0;
	float c5r = pixel - floor(pixel / 32.0) * 32.0;
	float c5g = floor(pixel / 32.0) - floor(pixel / 1024.0) * 32.0;
	float c5b = floor(pixel / 1024.0) - floor(pixel / 32768.0) * 32.0;
	float stp = floor(pixel / 32768.0);
	float3 color5 = float3(c5r, c5g, c5b);
	float3 color8 = (color5 * 8.0 + floor(color5 / 4.0)) / 255.0;
	return float4(color8, stp);
}
