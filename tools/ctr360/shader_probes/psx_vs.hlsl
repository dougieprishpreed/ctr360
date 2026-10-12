row_major float4x4 Projection : register(c0);
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
