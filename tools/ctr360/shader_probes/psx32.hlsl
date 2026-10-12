sampler2D s_texture : register(s0);
sampler2D s_rgLut : register(s1);
static const float2 c_VRAMTexel = float2(1.0 / 1024.0, 1.0 / 512.0);
static const float2 c_LUTTexel = float2(1.0 / 256.0, 1.0 / 256.0);
float bilinearFilter : register(c0);
float psxSemiTransPass : register(c1);
float psxDrawMaskSet : register(c2);
float psxTextureOutputStp : register(c3);
row_major float4x4 c_dither : register(c4);
struct VS_OUT
{
	float4 pos : POSITION;
	float4 texcoord : TEXCOORD0;
	float4 color : COLOR0;
	float4 page_clut : TEXCOORD1;
	float2 ditherCoord : TEXCOORD2;
	float z : TEXCOORD3;
};
float2 VRAM(float2 uv) { return tex2D(s_texture, uv).rg; }
float _idx2(float2 array, int idx) { return (idx == 0) ? array.x : array.y; }
float texelVisible(float2 rg) { return (rg.x + rg.y > 0.0) ? 1.0 : 0.0; }
float stpWeight(float2 rg) { return (rg.y >= 0.5) ? 1.0 : 0.0; }
float semiTransClip(float visible, float stpVisible, float nonStpVisible)
{
	if (visible < 0.5) { return -1.0; }
	if (psxSemiTransPass == 1.0 && nonStpVisible < 0.5) { return -1.0; }
	if (psxSemiTransPass == 2.0 && stpVisible < 0.5) { return -1.0; }
	return 1.0;
}
float4 lut(float2 rg) { return tex2D(s_rgLut, rg - c_LUTTexel * 0.0001); }
float4 dither(float4 color, float2 ditherCoord, float ditherAmount)
{
	float2 dc = floor(fmod(floor(ditherCoord), 4.0));
	float d = c_dither[(int)dc.x][(int)dc.y];
	color.xyz += d * ditherAmount;
	return color;
}
float2 texelSize : register(c16);
float4 main(VS_OUT i) : COLOR0
{
	float2 tc = i.texcoord.xy * texelSize + texelSize * 0.5;
	float4 color = tex2D(s_texture, tc);
	color = dither(color * i.color, i.ditherCoord, i.texcoord.w);
	color.a = (psxDrawMaskSet != 0.0) ? 1.0 : 0.0;
	return color;
}
