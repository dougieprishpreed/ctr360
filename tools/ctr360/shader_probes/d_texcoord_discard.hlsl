sampler2D s0 : register(s0);
struct VS_OUT { float4 pos : POSITION; float4 tc : TEXCOORD0; };
float4 main(VS_OUT i) : COLOR0 { float2 rg = tex2D(s0, i.tc.xy).rg; if (rg.x + rg.y <= 0.0) { discard; } return float4(rg, 0, 1); }
