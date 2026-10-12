row_major float4x4 m : register(c4);
float4 main(float4 c : COLOR0) : COLOR0 { int2 dc = int2(fmod(floor(c.xy), 4.0)); float d = m[dc.x][dc.y]; return float4(d, 0, 0, 1); }
