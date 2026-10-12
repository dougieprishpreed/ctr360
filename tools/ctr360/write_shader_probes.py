"""Write all ctr360 HLSL shader probes, v2: float uniforms and float-only math
(the XDK's fxc rejects int register bindings and dynamic integer expressions)."""
import os

os.makedirs('shader_probes', exist_ok=True)

common = r'''sampler2D s_texture : register(s0);
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
'''

mainbody = r'''float4 main(VS_OUT i) : COLOR0
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
'''

sample4 = r'''float2 samplePSX(float2 tc, float4 page_clut)
{
	float2 uv = (tc * float2(0.25, 1.0) + page_clut.xy) * c_VRAMTexel;
	float2 comp = VRAM(uv);
	float index = floor(frac(tc.x / 4.0 + 0.0001) * 4.0);
	float v = _idx2(comp, (int)floor(index / 2.0)) * (255.0 / 16.0);
	float f = floor(v + 0.001);
	float2 c = float2((v - f) * 16.0, f);
	float2 clut_pos = page_clut.zw;
	float fracIndex = index - floor(index / 2.0) * 2.0;
	clut_pos.x += lerp(c[1], c[0], fracIndex) * c_VRAMTexel.x;
	return VRAM(clut_pos);
}
'''
sample8 = r'''float2 samplePSX(float2 tc, float4 page_clut)
{
	float2 uv = (tc * float2(0.5, 1.0) + page_clut.xy) * c_VRAMTexel;
	float2 comp = VRAM(uv);
	float2 clut_pos = page_clut.zw;
	float index = tc.x - floor(tc.x / 2.0) * 2.0;
	clut_pos.x += _idx2(comp, (int)index) * 255.0 * c_VRAMTexel.x;
	return VRAM(clut_pos);
}
'''
sample16 = r'''float2 samplePSX(float2 tc, float4 page_clut)
{
	float2 uv = (tc + page_clut.xy) * c_VRAMTexel;
	return VRAM(uv);
}
'''

shaders = {
    'psx4': common + sample4 + mainbody,
    'psx8': common + sample8 + mainbody,
    'psx16': common + sample16 + mainbody,
}
for name, src in shaders.items():
    open('shader_probes/%s.hlsl' % name, 'w', encoding='utf-8').write(src)

src32 = common + r'''float2 texelSize : register(c16);
float4 main(VS_OUT i) : COLOR0
{
	float2 tc = i.texcoord.xy * texelSize + texelSize * 0.5;
	float4 color = tex2D(s_texture, tc);
	color = dither(color * i.color, i.ditherCoord, i.texcoord.w);
	color.a = (psxDrawMaskSet != 0.0) ? 1.0 : 0.0;
	return color;
}
'''
open('shader_probes/psx32.hlsl', 'w', encoding='utf-8').write(src32)

vs = r'''row_major float4x4 Projection : register(c0);
struct VS_OUT
{
	float4 pos : POSITION;
	float4 texcoord : TEXCOORD0;
	float4 color : COLOR0;
	float4 page_clut : TEXCOORD1;
	float2 ditherCoord : TEXCOORD2;
	float z : TEXCOORD3;
};
VS_OUT main(float4 a_position : POSITION, float4 a_texcoord : TEXCOORD0, float4 a_color : COLOR0, float4 a_extra : TEXCOORD1)
{
	VS_OUT o;
	float4 clip = mul(float4(a_position.xy, 0.0, 1.0), Projection);
	o.ditherCoord = a_position.xy;
	o.texcoord = a_texcoord;
	o.texcoord.xy += a_extra.xy * 0.5;
	o.color = a_color;
	o.color.xyz *= a_texcoord.z;
	o.page_clut.x = frac(a_position.z / 16.0) * 1024.0;
	o.page_clut.y = floor(a_position.z / 16.0) * 256.0;
	o.page_clut.z = frac(a_position.w / 64.0);
	o.page_clut.w = floor(a_position.w / 64.0) / 512.0;
	o.page_clut.xy += 0.00025;
	o.page_clut.zw += 0.00025;
	o.pos = float4(clip.x, -clip.y, 0.0, 1.0);
	o.z = (clip.z - 40.0) * 0.005;
	return o;
}
'''
open('shader_probes/psx_vs.hlsl', 'w', encoding='utf-8').write(vs)

pack_vs = r'''float posFlipY : register(c0);
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
'''
open('shader_probes/pack_vs.hlsl', 'w', encoding='utf-8').write(pack_vs)

pack_ps = r'''sampler2D s_src : register(s0);
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
'''
open('shader_probes/pack_ps.hlsl', 'w', encoding='utf-8').write(pack_ps)

present_vs = r'''float4 sourceRect : register(c0);
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
'''
open('shader_probes/present_vs.hlsl', 'w', encoding='utf-8').write(present_vs)

present_ps = r'''sampler2D s_texture : register(s0);
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
'''
open('shader_probes/present_ps.hlsl', 'w', encoding='utf-8').write(present_ps)
print("written")
