"""Run the actual background-fill path against a recording fake GPU.

CTR fills the displayed draw area with its background colours every frame. Drawn into
the VRAM image at once, each fill switched the GPU to VRAM and back mid-frame, and on
Xenos every switch resolves the 720p target out of eDRAM and draws it back in. The
fills now wait for the next VRAM pass; every reader of the VRAM image applies them
first, in order, and the frame's pack drops those it covers.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--vulkan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--cc',default='cc');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
s=(root/'platform/xsdk/native_xsdk_video.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
pending=re.search(r'enum \{ XV_PENDING_FILLS=16 \};.*?static unsigned xvPendingFillCount;',s,re.S)[0]
code=''.join(function(s,name) for name in ('static void XvEndPass(','static void XvLayout(','static void XvPass(',
 'static void XvApplyFills(','static void XvQuad(','static void XvSyncCPU(','static int XvValidRect(','static int XvRectInside(',
 'void NativeRenderer_ClearVRAM(','void NativeRenderer_Clear(','static void XvPack(','int NativeRenderer_RestoreVRAMState('))
c=r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;
typedef struct {s16 x,y,w,h;} RECT16;
typedef struct {RECT16 disp;} DISPENV;
typedef struct {RECT16 clip;} DRAWENV;
static DISPENV activeDispEnv;static DRAWENV activeDrawEnv;
typedef struct {VkImage image;VkFramebuffer framebuffer;VkImageLayout layout;unsigned width,height,pass;int clearStencil;} XvTarget;
typedef struct {float rect[4],scale[4],flags[4],source[4];} XvUniform;
typedef struct {VkBuffer buffer;unsigned char *map;size_t size;} XvBuffer;
static struct {
 VkCommandBuffer command;XvTarget swap[1],main,off,vram;VkRenderPass passes[4];XvTarget *target;int recording,inPass;
 XvBuffer staging,vertices;int mainValid,mainResolved,vramCPUChanged,vramGPUChanged;u16 pixels[1024*512];
} xv;
static struct {unsigned passes,quads[4],reads;} xvCost;
enum {XV_VERTEX_BYTES=0,BM_NONE=0};
/* The fake GPU: one line per command, in order. */
static char events[4096][64];static unsigned eventCount;
static void Event(const char *f,...){va_list v;va_start(v,f);vsnprintf(events[eventCount++],64,f,v);va_end(v);assert(eventCount<4096);}
static void XvLayout(XvTarget *target,VkImageLayout layout);
static const char *Name(const void *t){return t==&xv.main?"main":t==&xv.vram?"vram":t==&xv.off?"off":"swap";}
static XvTarget *imageTarget(VkImage i){XvTarget *t[]={&xv.main,&xv.vram,&xv.off,&xv.swap[0]};for(int k=0;k<4;k++)if(t[k]->image==i)return t[k];abort();}
static XvTarget *fbTarget(VkFramebuffer f){XvTarget *t[]={&xv.main,&xv.vram,&xv.off,&xv.swap[0]};for(int k=0;k<4;k++)if(t[k]->framebuffer==f)return t[k];abort();}
void vkCmdBeginRenderPass(VkCommandBuffer c,const VkRenderPassBeginInfo *b,VkSubpassContents x){(void)c;(void)x;Event("begin %s",Name(fbTarget(b->framebuffer)));}
void vkCmdEndRenderPass(VkCommandBuffer c){(void)c;Event("end");}
void vkCmdPipelineBarrier(VkCommandBuffer c,VkPipelineStageFlags s,VkPipelineStageFlags d,VkDependencyFlags f,uint32_t n,const VkMemoryBarrier *m,uint32_t bn,const VkBufferMemoryBarrier *bm,uint32_t in,const VkImageMemoryBarrier *im){(void)c;(void)s;(void)d;(void)f;(void)n;(void)m;(void)bn;(void)bm;(void)in;(void)im;}
void vkCmdClearAttachments(VkCommandBuffer c,uint32_t n,const VkClearAttachment *at,uint32_t rn,const VkClearRect *r){(void)c;(void)n;(void)rn;
 Event("clear %s %d,%d,%u,%u %.3f",Name(xv.target),r->rect.offset.x,r->rect.offset.y,r->rect.extent.width,r->rect.extent.height,at->clearValue.color.float32[0]);}
void vkCmdCopyImageToBuffer(VkCommandBuffer c,VkImage i,VkImageLayout l,VkBuffer b,uint32_t n,const VkBufferImageCopy *r){(void)c;(void)l;(void)b;(void)n;(void)r;Event("read %s",Name(imageTarget(i)));}
void vkCmdSetViewport(VkCommandBuffer c,uint32_t f,uint32_t n,const VkViewport *v){(void)c;(void)f;(void)n;(void)v;}
void vkCmdSetScissor(VkCommandBuffer c,uint32_t f,uint32_t n,const VkRect2D *r){(void)c;(void)f;(void)n;(void)r;}
void vkCmdBindPipeline(VkCommandBuffer c,VkPipelineBindPoint b,VkPipeline p){(void)c;(void)b;(void)p;}
void vkCmdBindVertexBuffers(VkCommandBuffer c,uint32_t f,uint32_t n,const VkBuffer *b,const VkDeviceSize *o){(void)c;(void)f;(void)n;(void)b;(void)o;}
void vkCmdDraw(VkCommandBuffer c,uint32_t v,uint32_t i,uint32_t fv,uint32_t fi){(void)c;(void)v;(void)i;(void)fv;(void)fi;Event("quad %s",Name(xv.target));}
VkResult vkInvalidateMappedMemoryRanges(VkDevice d,uint32_t n,const VkMappedMemoryRange *r){(void)d;(void)n;(void)r;return VK_SUCCESS;}
static void XvBegin(void){xv.recording=1;}
static void XvSubmit(void){if(xv.inPass){vkCmdEndRenderPass(xv.command);xv.inPass=0;}Event("submit");}
static void XvReserveUniform(void){}
static void XvBindUniform(const XvUniform *u,unsigned t){(void)u;(void)t;}
static VkPipeline XvPipeline(unsigned p,int s,int b,int st){(void)p;(void)s;(void)b;(void)st;return VK_NULL_HANDLE;}
static void XvReadTarget(XvTarget *t){XvLayout(t,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);vkCmdCopyImageToBuffer(xv.command,t->image,t->layout,xv.staging.buffer,1,NULL);XvSubmit();}
static void XvPaletteWritten(int x,int y,int w,int h){(void)x;(void)y;(void)w;(void)h;}
static void XvPaletteReset(void){}
static void NativeRenderer_UpdateVRAM(void){if(xv.vramCPUChanged){XvSubmit();Event("upload");xv.vramCPUChanged=0;}}
#define XV_WIDTH 1280
#define XV_HEIGHT 720
'''+pending+code+r'''
static unsigned Count(const char *prefix,unsigned from){unsigned n=0;for(unsigned i=from;i<eventCount;i++)n+=!strncmp(events[i],prefix,strlen(prefix));return n;}
static int Find(const char *text,unsigned from){for(unsigned i=from;i<eventCount;i++)if(!strncmp(events[i],text,strlen(text)))return (int)i;return -1;}
/* One game frame as Platform_BeginScene .. Platform_EndScene draws it: the two background fills, a textured
 * draw, the pack of a whole frame (not on a midpoint) and the present. */
static unsigned Frame(int y,int midpoint){
 unsigned first=eventCount;
 activeDispEnv.disp=(RECT16){0,(s16)y,512,216};activeDrawEnv.clip=activeDispEnv.disp;
 xv.main.clearStencil=1;XvPass(&xv.main);
 NativeRenderer_Clear(0,y,512,114,87,98,178);NativeRenderer_Clear(0,y+114,512,102,230,230,230);
 XvLayout(&xv.vram,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);XvPass(&xv.main);Event("draw");
 if(!midpoint)XvPack(&xv.main,0,y,512,216);
 XvQuad(&xv.swap[0],&xv.main,3,0,0,1280,720,0,0,1,1);XvSubmit();
 return Count("begin",first);
}
int main(void){
 XvTarget *t[]={&xv.main,&xv.vram,&xv.off,&xv.swap[0]};
 for(uintptr_t k=0;k<4;k++){t[k]->image=(VkImage)(k+1);t[k]->framebuffer=(VkFramebuffer)(k+11);t[k]->layout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;}
 xv.staging.map=calloc(1024*512,4);assert(xv.staging.map);
 xv.main.width=1280;xv.main.height=720;xv.vram.width=1024;xv.vram.height=512;xv.off.width=1024;xv.off.height=512;
 unsigned whole=Frame(296,0),mid=Frame(0,1),next=Frame(296,0);
 printf("passes whole=%u midpoint=%u next=%u\n",whole,mid,next);fflush(stdout);
 assert(whole==3 && mid==2 && next==3);
 /* Fills left from another buffer ride in the pack's VRAM pass; a pack drops those it covers. */
 assert(Count("begin vram",0)==2 && xvPendingFillCount==0);
 unsigned same=eventCount;Frame(296,0);Frame(296,0);assert(Count("clear vram",same)==0 && xvPendingFillCount==0);
 /* A midpoint keeps one fill per area, the latest. */
 Frame(0,1);Frame(0,1);assert(xvPendingFillCount==2);
 /* A readback applies them first, in order, inside a VRAM pass. */
 unsigned from=eventCount;xv.vramGPUChanged=1;XvSyncCPU();
 int b=Find("begin vram",from),c1=Find("clear vram 0,0,512,114 ",from),c2=Find("clear vram 0,114,512,102 ",from),r=Find("read vram",from);
 assert(b>=0 && c1>b && c2>c1 && r>c2 && xvPendingFillCount==0);
 /* A copy from VRAM (the offscreen bridge) applies them first. */
 Frame(0,1);from=eventCount;XvQuad(&xv.off,&xv.vram,2,0,0,64,64,0,0,1,1);
 assert(Find("begin vram",from)>=0 && Find("begin vram",from)<Find("begin off",from) && Count("clear vram",from)==2);
 /* A fill elsewhere goes at once, after the waiting ones it might overlap. */
 Frame(0,1);from=eventCount;activeDispEnv.disp=activeDrawEnv.clip=(RECT16){0,0,512,216};
 NativeRenderer_ClearVRAM(0,200,512,100,255,0,0);
 b=Find("clear vram 0,0,512,114 ",from);c2=Find("clear vram 0,200,512,100 ",from);
 assert(b>=0 && c2>b && xvPendingFillCount==0);
 /* A restored VRAM state drops them. */
 Frame(0,1);static u16 state[1024*512];NativeRenderer_RestoreVRAMState(state,sizeof(state));assert(xvPendingFillCount==0);
 puts("PASS: background fills wait for the frame's VRAM pass: 3 passes a whole frame, 2 a midpoint; readbacks, VRAM copies and fills elsewhere apply them first, in order");
}
'''
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=a.out/(name+'.exe')
 subprocess.run([a.cc,'-std=c17','-w','-I'+str(a.vulkan/'third_party/vulkan-headers/include'),str(source),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'background-fill');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip().splitlines()[-1])
eager=c.replace('if(!(xv.inPass && xv.target==&xv.vram) && XvRectInside(','if(0 && XvRectInside(')
assert eager!=c;r=run(eager,'background-fill-eager');assert r.returncode!=0 and 'passes whole=8' in r.stdout,r.stdout
unapplied=c.replace('XvApplyFills();XvReadTarget(&xv.vram);','XvReadTarget(&xv.vram);')
assert unapplied!=c and run(unapplied,'background-fill-unapplied').returncode!=0
print('PASS: drawing fills at once (8 passes a whole frame) and a readback before the fills rejected')
