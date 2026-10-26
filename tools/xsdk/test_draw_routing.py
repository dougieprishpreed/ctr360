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
    palette = source[source.index('/* CPU palette summaries'):source.index('static void XvCheck(')]
    setters = source[source.index('void NativeRenderer_SetTexture('):source.index('void NativeRenderer_UpdateVertexBuffer(')]
    draw = source[source.index('static void XvDrawTriangles('):source.index('static int XvValidRect(')]
    harness = r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
enum {XV_WIDTH=1280, XV_HEIGHT=720};
typedef unsigned TextureID;
typedef uint16_t u16;
typedef struct {int16_t clut;} GrVertex;
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
 const GrVertex *sourceVertices;u16 pixels[1024*512];
} xv;
static struct {unsigned draws,shaderDraws[7],blendDraws[5],uiDraws,skippedSTPPasses,trisRequested,trisDrawn,trisDropped,trisSkipped;} xvCost;
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
'''+palette+setters+draw+r'''
static void twoPasses(unsigned expected){
 unsigned before=draws;
 xv.state.flags[0]=1;XvDrawTriangles(0,2,1);
 xv.state.flags[0]=2;XvDrawTriangles(0,2,1);
 assert(draws-before==expected);
}
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
 GrVertex vertices[6];for(unsigned i=0;i<6;i++)vertices[i].clut=511*64+63;
 xv.vertexCount=6;xv.sourceVertices=vertices;xv.offscreen=xv.ui=0;
 for(unsigned fmt=0;fmt<2;fmt++)for(unsigned kind=0;kind<4;kind++){
  xv.format=fmt;memset(xv.pixels,0,sizeof(xv.pixels));
  for(unsigned i=0;i<(fmt?256:16);i++)xv.pixels[511*1024+((1008+i)&1023)]=kind==0?31:kind==1?32768:kind==2?(i&1?31:32768):0;
  XvPaletteReset();twoPasses(kind<2?1:2);twoPasses(kind<2?1:2);
  for(unsigned i=0;i<6;i++)vertices[i].clut^=32768;
  twoPasses(kind<2?1:2);
  for(unsigned i=0;i<6;i++)vertices[i].clut^=32768;
  // An unrelated framebuffer rectangle must not disable the cached summary.
  XvPaletteWritten(0,511,16,1);twoPasses(fmt?2:kind<2?1:2);
  XvPaletteWritten(1008,511,1,1);twoPasses(2);
  XvPaletteReset();twoPasses(kind<2?1:2);
  // Different CLUTs in one call, direct color, and the debug/white paths
  // cannot use this proof even when the first vertex's palette is uniform.
  vertices[5].clut--;twoPasses(2);vertices[5].clut++;
  xv.format=TF_16_BIT;twoPasses(2);xv.format=fmt;
  g_dbg_texturelessMode=1;twoPasses(2);g_dbg_texturelessMode=0;
  xv.texture=NativeRenderer_GetWhiteTexture();twoPasses(2);xv.texture=NativeRenderer_GetVRAMTexture();
 }
 // CPU changes/readback start a new generation; stale cached STP is rejected.
 xv.format=TF_4_BIT;xv.pixels[511*1024+1008]=31;XvPaletteReset();twoPasses(1);
 xv.pixels[511*1024+1008]=32768;XvPaletteReset();twoPasses(1);
 assert(XvTexturePassNeeded(0,2)); // Last pass (STP) now has a visible texel.
 xvPalette.generation=~0u;XvPaletteReset();assert(xvPalette.generation==1);twoPasses(1);
 printf("PASS: %u actual draw-routing cases; flat/textured/debug, inherited tpage, filter, UI/offscreen, stencil, bounds\n",cases);
 puts("PASS: actual STP draw skipping; opaque/STP/mixed/zero palettes, 4/8-bit wrap, GPU overlap, CPU invalidation, mixed CLUTs and generation rollover");
}
'''
    harness=harness.replace('#include <stdio.h>','#include <stdio.h>\n#include <string.h>')
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
    invalidation = 'if(xvPalette.gpuWritten[y*64+((x/16+i)&63)])return 0;'
    assert invalidation in harness
    negative = run(harness.replace(invalidation,'(void)0;'), 'palette-invalidation-negative')
    assert negative.returncode, 'negative control missed stale GPU-written palette'
    print('PASS: using stale CPU palettes after a GPU write rejected')


if __name__ == '__main__':
    main()
