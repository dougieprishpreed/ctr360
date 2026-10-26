#version 450
layout(location=0) in vec4 position;
layout(location=1) in vec4 texcoord;
layout(location=2) in vec4 color;
layout(location=3) in vec4 extra;
layout(location=4) in vec4 bounds;
layout(set=0,binding=0,std140) uniform State { vec4 rect; vec4 scale; vec4 flags; vec4 source; } s;
layout(location=0) out vec4 rgba;
layout(location=1) out vec4 tc;
layout(location=2) out vec4 page;
layout(location=3) out vec4 uvRange;
void main() {
    // GTE-projected vertices carry the fraction of their exact position in
    // the spare extra bytes (1/256 pixel); dithering keeps the pixel grid.
    vec2 psx=position.xy+extra.zw*(1.0/256.0);
    vec2 xy=vec2((psx.x-s.scale.y)*s.scale.x+s.scale.y,psx.y);
    gl_Position=vec4((xy/s.rect.zw)*2.0-1.0,0.0,1.0);
    // Pixel shading no longer needs brightness or vertex alpha. Carry the
    // two dither coordinates in those lanes instead of a fourth interpolator.
    tc=vec4(texcoord.xy+extra.xy*0.5,position.x,texcoord.w*s.scale.z);
    rgba=vec4(color.rgb*texcoord.z,position.y);
    page=vec4(fract(position.z/16.0)*1024.0,floor(position.z/16.0)*256.0,
              fract(position.w/64.0)*1024.0,floor(position.w/64.0));
    // Identical on a triangle's three vertices: its texel minimum and
    // exclusive maximum, for filtered taps.
    uvRange=bounds;
}
