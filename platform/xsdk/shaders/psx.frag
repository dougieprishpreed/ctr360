#version 450
layout(set=0,binding=0,std140) uniform State { vec4 rect; vec4 scale; vec4 flags; vec4 source; } s;
layout(set=0,binding=1) uniform sampler2D vram;
layout(location=0) in vec4 tc;
layout(location=1) in vec4 rgba;
layout(location=2) in vec2 dc;
layout(location=3) in vec4 page;
layout(location=0) out vec4 result;
vec2 bytes(vec2 pos) {
    return floor(texture(vram,(mod(floor(pos),vec2(1024,512))+0.5)/vec2(1024,512)).rg*255.0+0.5);
}
float word(vec2 pos) {
    vec2 rg=bytes(pos);
    return rg.x+rg.y*256.0;
}
vec4 unpackColor(float w) {
    return vec4(mod(w,32.0),mod(floor(w/32.0),32.0),mod(floor(w/1024.0),32.0),floor(w/32768.0))/vec4(31,31,31,1);
}
float textureWord(vec2 uv) {
    uv=mod(floor(uv),256.0);
    float w;
    #if XV_FORMAT == 0
    {
        vec2 rg=bytes(floor(page.xy+0.5)+vec2(floor(uv.x*0.25),uv.y));
        float component=mod(uv.x,4.0);
        // Select the byte, then its nibble, as in the working XDK renderer.
        // Arithmetic stays in 0..255; no variable full-word shift multiplier.
        float b=mix(rg.x,rg.y,step(2.0,component));
        float high=floor(b*0.0625);
        float index=mix(b-high*16.0,high,mod(component,2.0));
        w=word(floor(page.zw+0.5)+vec2(index,0));
    }
#elif XV_FORMAT == 1
    {
        vec2 rg=bytes(floor(page.xy+0.5)+vec2(floor(uv.x*0.5),uv.y));
        w=word(floor(page.zw+0.5)+vec2(mix(rg.x,rg.y,mod(uv.x,2.0)),0));
    }
#else
    w=word(floor(page.xy+0.5)+uv);
#endif
    return w;
}
vec4 samplePSX(vec2 uv) {
    float w=textureWord(uv);
    vec4 c=unpackColor(w);
    float visible=w>0.0?1.0:0.0;
    return vec4(c.rgb*visible,visible);
}
void main() {
    vec4 c;
#if XV_FORMAT != 3
    float nearest=textureWord(tc.xy);
    float stp=step(32768.0,nearest);
    if(nearest<0.5 || (s.flags.x>0.5 && s.flags.x<1.5 && stp>0.5) || (s.flags.x>1.5 && stp<0.5)) discard;
#endif
    #if XV_FORMAT == 3
    c=vec4(1);
#elif XV_FILTER
    {
        vec2 uv=tc.xy; vec2 f=fract(uv);vec2 p=floor(uv);
        // textureWord floors UV: the nearest sample is exactly the top-left
        // filtering tap. Its visibility/STP decision above still applies.
        c=mix(mix(vec4(unpackColor(nearest).rgb,1),samplePSX(p+vec2(1,0)),f.x),
              mix(samplePSX(p+vec2(0,1)),samplePSX(p+vec2(1,1)),f.x),f.y);
        c.rgb/=max(c.a,0.0001);

    }
#else
    c=vec4(unpackColor(nearest).rgb,1);
#endif
    vec2 d=mod(floor(dc),4.0);
    vec4 row=mix(vec4(-4,0,-3,1),vec4(2,-2,3,-1),step(1.0,d.x));
    row=mix(row,vec4(-3,1,-4,0),step(2.0,d.x));
    row=mix(row,vec4(3,-1,2,-2),step(3.0,d.x));
    float noise=mix(mix(row.x,row.y,step(1.0,d.y)),mix(row.z,row.w,step(3.0,d.y)),step(2.0,d.y));
    c.rgb=clamp(c.rgb*rgba.rgb+noise*tc.w/255.0,0.0,1.0);
    #if XV_FORMAT == 3
    if(c.a>=0.0001) { result=vec4(c.rgb,s.flags.y>0.5?1.0:0.0); }
#else
    if(c.a>=0.0001) { result=vec4(c.rgb,(s.flags.y>0.5 || (s.flags.z>0.5 && stp>0.5))?1.0:0.0); }
#endif
    else { discard; }
}
