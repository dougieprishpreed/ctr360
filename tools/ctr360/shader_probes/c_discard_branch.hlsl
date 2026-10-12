int flag : register(i0);
float4 main(float4 c : COLOR0) : COLOR0 { if (flag == 1) { if (c.r < 0.5) { discard; } } return c; }
