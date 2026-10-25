#version 450
layout(set=0,binding=0,std140) uniform State { vec4 rect; vec4 scale; vec4 flags; vec4 source; } s;
layout(set=0,binding=1) uniform sampler2D image;
layout(location=0) in vec2 uv;
layout(location=0) out vec4 result;
void main() {
    #if XV_MODE == 2
    vec4 c=textureLod(image,uv,0.0);
    #else
    vec4 c=texture(image,uv);
    #endif
    #if XV_MODE == 3
    {
        vec2 p=vec2(1.0/1280.0,1.0/720.0);
        vec3 nw=texture(image,uv+vec2(-p.x,-p.y)).rgb;
        vec3 ne=texture(image,uv+vec2(p.x,-p.y)).rgb;
        vec3 sw=texture(image,uv+vec2(-p.x,p.y)).rgb;
        vec3 se=texture(image,uv+vec2(p.x,p.y)).rgb;
        vec3 l=vec3(0.299,0.587,0.114);
        float m=dot(c.rgb,l),a=dot(nw,l),b=dot(ne,l),d=dot(sw,l),e=dot(se,l);
        float lo=min(m,min(min(a,b),min(d,e))),hi=max(m,max(max(a,b),max(d,e)));
        vec2 dir=vec2(-((a+b)-(d+e)),(a+d)-(b+e));
        float reduce=max((a+b+d+e)*0.03125,0.0078125);
        dir=clamp(dir/(min(abs(dir.x),abs(dir.y))+reduce),-8.0,8.0)*p;
        vec3 A=0.5*(texture(image,uv-dir/6.0).rgb+texture(image,uv+dir/6.0).rgb);
        vec3 B=A*0.5+0.25*(texture(image,uv-dir*0.5).rgb+texture(image,uv+dir*0.5).rgb);
        float bl=dot(B,l);vec3 smoothColor=(bl<lo || bl>hi)?A:B;
        result=vec4((hi-lo < max(0.03125,hi*0.125))?c.rgb:smoothColor,1);
    }
#elif XV_MODE == 2
    {
        vec2 rg=floor(c.rg*255.0+0.5);float w=rg.x+rg.y*256.0;
        result=vec4(mod(w,32.0),mod(floor(w/32.0),32.0),mod(floor(w/1024.0),32.0),floor(w/32768.0)*31.0)/31.0;
    }
#elif XV_MODE == 1
    {
        vec4 bytes=floor(clamp(c,0,1)*255.0+0.5);
        float w=floor(bytes.r/8.0)+floor(bytes.g/8.0)*32.0+floor(bytes.b/8.0)*1024.0+floor(bytes.a/128.0)*32768.0;
        result=vec4(mod(w,256.0),floor(w/256.0),0,255)/255.0;
    }
#else
    result=vec4(c.rgb,1);
#endif
}
