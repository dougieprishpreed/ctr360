float4 main(float4 c : COLOR0) : COLOR0 { clip(c.r - 0.5); return c; }
