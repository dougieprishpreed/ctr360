#version 450
layout(set=0,binding=0,std140) uniform State { vec4 rect; vec4 scale; vec4 flags; vec4 source; } s;
layout(set=0,binding=1) uniform sampler2D vram;
layout(location=0) in vec4 rgba;
layout(location=1) in vec4 tc;
layout(location=2) in vec4 page;
layout(location=0) out vec4 result;
vec2 bytes(vec2 pos) {
    // Callers supply integral word addresses. The VRAM sampler wraps the
    // 1024x512 image, including CLUTs/pages that cross its physical edges.
    return floor(textureLod(vram,(pos+0.5)/vec2(1024,512),0.0).rg*255.0+0.5);
}
float word(vec2 pos) {
    vec2 rg=bytes(pos);
    return rg.x+rg.y*256.0;
}
vec4 unpackColor(float w) {
    vec4 shifted=floor(w/vec4(1,32,1024,32768));
    return vec4(shifted.xyz-shifted.yzw*32.0,shifted.w)/vec4(31,31,31,1);
}
float textureWord(vec2 uv,vec4 pg) {
    // UV is already integral and wrapped to this 256x256 page.
    float w;
    #if XV_FORMAT == 0
    {
        float packedX=floor(uv.x*0.25);
        vec2 rg=bytes(pg.xy+vec2(packedX,uv.y));
        float component=uv.x-packedX*4.0;
        // Select the byte, then its nibble, as in the working XDK renderer.
        // Arithmetic stays in 0..255; no variable full-word shift multiplier.
        float b=mix(rg.x,rg.y,step(2.0,component));
        float high=floor(b*0.0625);
        float index=mix(b-high*16.0,high,mod(component,2.0));
        w=word(pg.zw+vec2(index,0));
    }
#elif XV_FORMAT == 1
    {
        float packedX=floor(uv.x*0.5);
        vec2 rg=bytes(pg.xy+vec2(packedX,uv.y));
        w=word(pg.zw+vec2(mix(rg.x,rg.y,uv.x-packedX*2.0),0));
    }
#else
    w=word(pg.xy+uv);
#endif
    return w;
}
vec4 samplePSX(vec2 uv,vec4 pg) {
    float w=textureWord(uv,pg);
    vec4 c=unpackColor(w);
    float visible=w>0.0?1.0:0.0;
    return vec4(c.rgb,visible);
}
void main() {
    vec4 c;
#if XV_FORMAT != 3
    vec4 pg=floor(page+0.5);
    // The XDK path biases data sampling away from integer boundaries. Keep
    // interpolation roundoff below a constant UV from selecting its previous
    // texel/transparent mask. Use one consistent, exactly representable bias
    // for coverage and filtering, rather than a fifth nearest fetch.
    vec2 uv=tc.xy+vec2(1.0/4096.0);
    vec2 p=mod(floor(uv),256.0);
    float nearest=textureWord(p,pg);
    float stp=step(32768.0,nearest);
    // Pass is exactly 0 (all), 1 (opaque subset), or 2 (STP subset).
    if(nearest<0.5 || s.flags.x==2.0-stp) discard;
#endif
    #if XV_FORMAT == 3
    c=vec4(1);
#elif XV_FILTER
    {
        vec2 f=fract(uv);
        vec2 next=mix(p+1.0,vec2(0),step(vec2(255),p));
        // Share address rounding/wrapping across all four taps. Neighbor
        // coordinates still wrap at the PSX page edge before packed fetches.
        c=mix(mix(vec4(unpackColor(nearest).rgb,1),samplePSX(vec2(next.x,p.y),pg),f.x),
              mix(samplePSX(vec2(p.x,next.y),pg),samplePSX(next,pg),f.x),f.y);
        c.rgb/=max(c.a,0.0001);

    }
#else
    c=vec4(unpackColor(nearest).rgb,1);
#endif
    #if XV_DITHER
    vec2 dc=vec2(tc.z,rgba.a);
    vec2 d=mod(floor(dc),4.0);
    vec4 row=mix(vec4(-4,0,-3,1),vec4(2,-2,3,-1),step(1.0,d.x));
    row=mix(row,vec4(-3,1,-4,0),step(2.0,d.x));
    row=mix(row,vec4(3,-1,2,-2),step(3.0,d.x));
    float noise=mix(mix(row.x,row.y,step(1.0,d.y)),mix(row.z,row.w,step(3.0,d.y)),step(2.0,d.y));
    c.rgb=clamp(c.rgb*rgba.rgb+noise*tc.w/255.0,0.0,1.0);
    #else
    c.rgb=clamp(c.rgb*rgba.rgb,0.0,1.0);
    #endif
    // PSX coverage follows the nearest texel, tested above. A tiny filtered
    // weight at a transparent edge must not punch an extra hole in geometry.
    #if XV_FORMAT == 3
    result=vec4(c.rgb,s.flags.y);
#else
    result=vec4(c.rgb,min(1.0,s.flags.y+s.flags.z*stp));
#endif
}
