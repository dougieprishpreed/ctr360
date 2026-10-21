#version 450
layout(set=0,binding=0,std140) uniform State { vec4 rect; vec4 scale; vec4 flags; vec4 source; } s;
layout(location=0) in vec4 position;
layout(location=0) out vec2 uv;
void main() {
    vec2 xy=position.xy;
    // Four strip vertices; y increases toward the bottom in Vulkan.
    gl_Position=vec4(xy*2.0-1.0,0,1);
    uv=s.source.xy+xy*s.source.zw;
}
