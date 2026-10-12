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
float2 samplePSX(float2 tc, float4 page_clut)
{
	float2 uv = (tc * float2(0.5, 1.0) + page_clut.xy) * c_VRAMTexel;
	float2 comp = VRAM(uv);
	float2 clut_pos = page_clut.zw;
	float index = tc.x - floor(tc.x / 2.0) * 2.0;
	clut_pos.x += _idx2(comp, (int)index) * 255.0 * c_VRAMTexel.x;
	return VRAM(clut_pos);
}
float4 main(VS_OUT i) : COLOR0
{
	float sampledStp = 0.0;
	float4 color;

	if (bilinearFilter > 0.0) {
		float2 P = i.texcoord.xy;
		float2 fracPart = frac(P);
		float2 pixel = floor(P);
		float2 C11 = samplePSX(pixel, i.page_clut);
		float2 C21 = samplePSX(pixel + float2(1.0, 0.0), i.page_clut);
		float2 C12 = samplePSX(pixel + float2(0.0, 1.0), i.page_clut);
		float2 C22 = samplePSX(pixel + float2(1.0, 1.0), i.page_clut);
		float v11 = texelVisible(C11);
		float v21 = texelVisible(C21);
		float v12 = texelVisible(C12);
		float v22 = texelVisible(C22);
		float s11 = v11 * stpWeight(C11);
		float s21 = v21 * stpWeight(C21);
		float s12 = v12 * stpWeight(C12);
		float s22 = v22 * stpWeight(C22);
		float n11 = v11 - s11;
		float n21 = v21 - s21;
		float n12 = v12 - s12;
		float n22 = v22 - s22;
		float ax1 = lerp(v11, v21, fracPart.x);
		float ax2 = lerp(v12, v22, fracPart.x);
		float axm = lerp(ax1, ax2, fracPart.y);
		float sx1 = lerp(s11, s21, fracPart.x);
		float sx2 = lerp(s12, s22, fracPart.x);
		float stp = lerp(sx1, sx2, fracPart.y);
		float nx1 = lerp(n11, n21, fracPart.x);
		float nx2 = lerp(n12, n22, fracPart.x);
		float nonStp = lerp(nx1, nx2, fracPart.y);
		sampledStp = stp;
		clip(semiTransClip(axm, stp, nonStp));
		float4 x1 = lerp(lut(C11), lut(C21), fracPart.x);
		float4 x2 = lerp(lut(C12), lut(C22), fracPart.x);
		float4 t = lerp(x1, x2, fracPart.y);
		t.w = 1.0 - t.w;
		color = t;
	} else {
		float2 rg = samplePSX(i.texcoord.xy, i.page_clut);
		float visible = texelVisible(rg);
		sampledStp = visible * stpWeight(rg);
		clip(semiTransClip(visible, sampledStp, visible - sampledStp));
		float4 t = lut(rg);
		t.w = 1.0 - t.w;
		color = t;
	}

	color = dither(color * i.color, i.ditherCoord, i.texcoord.w);
	color.a = (psxDrawMaskSet != 0.0 || (psxTextureOutputStp != 0.0 && sampledStp >= 0.5)) ? 1.0 : 0.0;
	return color;
}
