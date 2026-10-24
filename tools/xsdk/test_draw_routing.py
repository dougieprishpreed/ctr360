"""Execute the actual draw path with Vulkan recorders, including texture IDs.

Untextured game splits retain the current tpage format. A test of the flat
shader alone cannot catch routing those splits through a palette shader.
"""
import argparse
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vulkan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    source = (root/'platform/xsdk/native_xsdk_video.c').read_text()
    setters = source[source.index('void NativeRenderer_SetTexture('):source.index('void NativeRenderer_UpdateVertexBuffer(')]
    draw = source[source.index('static void XvDrawTriangles('):source.index('static int XvValidRect(')]
    harness = r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
enum {XV_WIDTH=1280, XV_HEIGHT=720};
typedef unsigned TextureID;
typedef enum {TF_4_BIT,TF_8_BIT,TF_16_BIT,TF_32_BIT_RGBA} TexFormat;
typedef enum {BM_NONE,BM_AVERAGE,BM_ADD,BM_SUBTRACT,BM_ADD_QUATER_SOURCE} BlendMode;
typedef struct {int x,y,w,h;} RECT16;
typedef struct {float rect[4],scale[4],flags[4],source[4];} XvUniform;
typedef struct {int pass;} XvTarget;
static struct {
 VkCommandBuffer command; XvTarget main,off,vram;
 struct {VkBuffer buffer;} vertices;
 unsigned vertexBase,vertexCount; int offscreen,ui,clipEnabled,drawPrim,mainValid;
 RECT16 offRect; VkRect2D scissor; XvUniform state;
 TextureID texture; TexFormat format; BlendMode blend;
} xv;
static struct {unsigned draws,shaderDraws[7],blendDraws[5],uiDraws;} xvCost;
static int g_dbg_texturelessMode,g_cfg_bilinearFiltering=1;
static unsigned selected,stencil,bound,draws,firstSeen,countSeen;
static XvTarget *targetSeen;
static void NativeRenderer_UpdateVRAM(void){}
static void XvLayout(XvTarget *target,VkImageLayout layout){}
static void XvPass(XvTarget *target){targetSeen=target;}
static void XvReserveUniform(void){}
static void XvBindUniform(const XvUniform *s,unsigned texture){assert(texture==0);}
static VkPipeline XvPipeline(unsigned pass,int shader,BlendMode blend,int mask){
 selected=shader;stencil=mask;assert(blend==xv.blend);return (VkPipeline)(uintptr_t)(shader+1);
}
void vkCmdSetViewport(VkCommandBuffer c,uint32_t f,uint32_t n,const VkViewport *v){}
void vkCmdSetScissor(VkCommandBuffer c,uint32_t f,uint32_t n,const VkRect2D *v){}
void vkCmdBindPipeline(VkCommandBuffer c,VkPipelineBindPoint p,VkPipeline v){bound=(unsigned)(uintptr_t)v-1;}
void vkCmdBindVertexBuffers(VkCommandBuffer c,uint32_t f,uint32_t n,const VkBuffer *b,const VkDeviceSize *o){assert(*o==xv.vertexBase);}
void vkCmdDraw(VkCommandBuffer c,uint32_t n,uint32_t i,uint32_t f,uint32_t fi){draws++;firstSeen=f;countSeen=n;assert(i==1 && fi==0);}
'''+setters+draw+r'''
static void check(TextureID texture,TexFormat format,int filtering,int expected){
 NativeRenderer_SetTexture(texture,format);
 XvDrawTriangles(3,2,filtering);
 assert(selected==expected+(xv.offscreen?7:0) && bound==selected);
 assert(firstSeen==3 && countSeen==6 && stencil==(xv.drawPrim?1:2));
 assert(targetSeen==(xv.offscreen?&xv.off:&xv.main));
}
int main(void){
 xv.vertexCount=12;xv.vertexBase=120;xv.state.rect[2]=512;xv.state.rect[3]=216;
 xv.offRect=(RECT16){0,0,32,32};
 unsigned cases=0;
 for(unsigned off=0;off<2;off++)for(unsigned ui=0;ui<2;ui++)for(unsigned mask=0;mask<2;mask++){
  xv.offscreen=off;xv.ui=ui;xv.drawPrim=mask;
  for(unsigned fmt=0;fmt<4;fmt++)for(unsigned filter=0;filter<2;filter++){
   g_dbg_texturelessMode=0;
   check(NativeRenderer_GetWhiteTexture(),fmt,filter,6);cases++;
   check(NativeRenderer_GetVRAMTexture(),fmt,filter,fmt==3?6:fmt*2+filter);cases++;
   g_dbg_texturelessMode=1;
   check(NativeRenderer_GetVRAMTexture(),fmt,filter,6);cases++;
  }
 }
 g_dbg_texturelessMode=0;xv.offscreen=0;xv.ui=0;
 NativeRenderer_SetTexture(NativeRenderer_GetVRAMTexture(),TF_4_BIT);
 NativeRenderer_DrawTriangles(3,2);assert(selected==1);
 xv.ui=1;NativeRenderer_DrawTriangles(3,2);assert(selected==0);
 xv.ui=0;xv.offscreen=1;NativeRenderer_DrawTriangles(3,2);assert(selected==7);
 unsigned before=draws;
 XvDrawTriangles(-1,2,1);XvDrawTriangles(0,0,1);XvDrawTriangles(10,2,1);XvDrawTriangles(13,1,1);
 assert(draws==before);
 printf("PASS: %u actual draw-routing cases; flat/textured/debug, inherited tpage, filter, UI/offscreen, stencil, bounds\n",cases);
}
'''
    header = '-I'+str(args.vulkan/'third_party/vulkan-headers/include')
    def run(text, name):
        c = args.out/(name+'.c')
        exe = args.out/name
        c.write_text(text)
        subprocess.run(['cc','-std=c17',header,str(c),'-o',str(exe)],check=True)
        return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
    result = run(harness, 'draw-routing')
    if result.returncode:
        raise SystemExit(result.stderr or 'actual renderer routes untextured draws incorrectly')
    print(result.stdout.strip())
    # The exact previously shipped omission must fail the behavioral test.
    predicate = 'xv.texture==NativeRenderer_GetWhiteTexture() || '
    assert predicate in draw
    negative = run(harness.replace(predicate, ''), 'draw-routing-negative')
    assert negative.returncode, 'negative control failed to detect ignored texture ID'
    print('PASS: previous ignored-white-texture regression rejected')


if __name__ == '__main__':
    main()
