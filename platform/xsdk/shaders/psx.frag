#version 450
layout(set=0,binding=0,std140) uniform State { vec4 rect; vec4 scale; vec4 flags; vec4 source; } s;
layout(set=0,binding=1) uniform sampler2D vram;
layout(location=0) in vec4 tc;
layout(location=1) in vec4 rgba;
layout(location=2) in vec4 page;
layout(location=3) in vec2 dc;
layout(location=0) out vec4 result;
float word(vec2 pos) {
    vec2 rg=floor(texture(vram,(mod(floor(pos),vec2(1024,512))+0.5)/vec2(1024,512)).rg*255.0+0.5);
    return rg.x+rg.y*256.0;
}
vec4 unpackColor(float w) {
    return vec4(mod(w,32.0),mod(floor(w/32.0),32.0),mod(floor(w/1024.0),32.0),floor(w/32768.0))/vec4(31,31,31,1);
}
float textureWord(vec2 uv) {
    uv=mod(floor(uv),256.0);
    float w;
    if(s.scale.w<0.5) {
        w=word(page.xy+vec2(floor(uv.x/4.0),uv.y));
        float component=mod(uv.x,4.0);
        float divisor=mix(1.0,16.0,step(1.0,component));
        divisor=mix(divisor,256.0,step(2.0,component));
        divisor=mix(divisor,4096.0,step(3.0,component));
        w=word(page.zw+vec2(mod(floor(w/divisor),16.0),0));
    } else if(s.scale.w<1.5) {
        w=word(page.xy+vec2(floor(uv.x/2.0),uv.y));
        w=word(page.zw+vec2(mod(floor(w/mix(1.0,256.0,step(1.0,mod(uv.x,2.0)))),256.0),0));
    } else w=word(page.xy+uv);
    return w;
}
vec4 samplePSX(vec2 uv) {
    float w=textureWord(uv);
    vec4 c=unpackColor(w);
    float visible=w>0.0?1.0:0.0;
    if(s.flags.x>0.5 && s.flags.x<1.5) visible*=1.0-c.a;
    if(s.flags.x>1.5) visible*=c.a;
    return vec4(c.rgb*visible,visible);
}
void main() {
    vec4 c;
    if(s.scale.w>2.5) c=vec4(1);
    else if(s.flags.w>0.5) {
        vec2 uv=tc.xy-0.5; vec2 f=fract(uv);vec2 p=floor(uv);
        c=mix(mix(samplePSX(p),samplePSX(p+vec2(1,0)),f.x),
              mix(samplePSX(p+vec2(0,1)),samplePSX(p+vec2(1,1)),f.x),f.y);

    } else c=samplePSX(tc.xy);
    vec2 d=mod(floor(dc),4.0);
    vec4 row=mix(vec4(-4,0,-3,1),vec4(2,-2,3,-1),step(1.0,d.x));
    row=mix(row,vec4(-3,1,-4,0),step(2.0,d.x));
    row=mix(row,vec4(3,-1,2,-2),step(3.0,d.x));
    float noise=mix(mix(row.x,row.y,step(1.0,d.y)),mix(row.z,row.w,step(3.0,d.y)),step(2.0,d.y));
    c.rgb=clamp(c.rgb*rgba.rgb+noise*tc.w/255.0,0.0,1.0);
    if(c.a>=0.0001) { result=vec4(c.rgb,(s.flags.y>0.5 || (s.flags.z>0.5 && textureWord(tc.xy)>=32768.0))?1.0:0.0); }
    else { discard; }
}
