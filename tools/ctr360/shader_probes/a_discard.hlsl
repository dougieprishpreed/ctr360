float4 main(float4 c : COLOR0) : COLOR0 { if (c.r < 0.5) { discard; } return c; }
