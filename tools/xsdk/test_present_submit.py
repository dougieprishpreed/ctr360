"""Record the actual presentation path: one combined, unwaited frame submit."""
import argparse,subprocess
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--vulkan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
s=(root/'platform/xsdk/native_xsdk_video.c').read_text()
body=s[s.index('void NativeRenderer_PresentVRAMRect('):s.index('void NativeRenderer_PresentVRAMDisplay(')]
c=r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
enum {XV_WIDTH=1280,XV_HEIGHT=720};
typedef struct {int id;} XvTarget;
static struct {VkDevice device;VkSwapchainKHR swapchain;VkQueue queue;VkFence fence,acquireFence;VkCommandBuffer command;XvTarget main,vram,swap[3];int mainResolved;} xv;
static VkRect2D xvPicture={{0,0},{XV_WIDTH,XV_HEIGHT}};
typedef struct {uint32_t drawn_back,clear_resolves,resolves_put_off,late_resolves;} V4xEdramCounts;
static V4xEdramCounts v4x_edram_counts(void){V4xEdramCounts c={0};return c;}
static int quadX,quadW,bars;
static int xvCaptureRequested;static unsigned shots;
static struct {unsigned submits,uploads,reads,draws,passes,shaderDraws[7],quads[4];unsigned submitMS,waitMS,frameWaitMS,acquireMS,presentMS;unsigned blendDraws[5],uiDraws,feedbackRequests,midpointFeedbackSkips,skippedSTPPasses;unsigned gpuFrames,gpuTotalUS,gpuMaxUS,gpuOver16;} xvCost;
static int xvEdgeAA=1;
static unsigned phase,submits,quads,modeSeen;
void vkCmdClearAttachments(VkCommandBuffer c,uint32_t n,const VkClearAttachment *at,uint32_t rn,const VkClearRect *r){
 assert(phase==4 && n==1 && at->clearValue.color.float32[0]==0 && rn==2);
 assert(r[0].rect.offset.x==0 && r[0].rect.extent.width==(unsigned)quadX && r[1].rect.offset.x==quadX+quadW && r[1].rect.extent.width==(unsigned)(XV_WIDTH-quadX-quadW));
 bars++;
}
#define XV_CALL(x) assert((x)==VK_SUCCESS)
static unsigned GetTickCount(void){return 1;}
static void Platform_Log(const char *format,...){}
static void NativeRenderer_UpdateVRAM(void){}
static void XvSubmit(void){assert(0);}
/* The screenshot reads main before acquisition, while it holds the finished frame. */
static void XvWriteScreenshot(void){assert(phase==0 && xv.mainResolved);shots++;}
static void XvSubmitFrame(void){assert(phase==4);phase=5;submits++;xvCost.submits++;}
static void XvQuad(XvTarget *to,XvTarget *from,int mode,int x,int y,int w,int h,float sx,float sy,float sw,float sh){assert(phase==3 && to==&xv.swap[1]);assert(from==(xv.mainResolved?&xv.main:&xv.vram));modeSeen=mode;quads++;phase=4;quadX=x;quadW=w;}
static void XvLayout(XvTarget *target,VkImageLayout layout){assert(phase==4 && target==&xv.swap[1] && layout==VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);}
VkResult vkAcquireNextImageKHR(VkDevice d,VkSwapchainKHR s,uint64_t t,VkSemaphore sem,VkFence f,uint32_t *i){assert(phase==0 && f==xv.acquireFence);*i=1;phase=1;return VK_SUCCESS;}
VkResult vkWaitForFences(VkDevice d,uint32_t n,const VkFence *f,VkBool32 all,uint64_t t){assert(phase==1 && *f==xv.acquireFence);phase=2;return VK_SUCCESS;}
VkResult vkResetFences(VkDevice d,uint32_t n,const VkFence *f){assert(phase==2 && *f==xv.acquireFence);phase=3;return VK_SUCCESS;}
VkResult vkQueuePresentKHR(VkQueue q,const VkPresentInfoKHR *p){assert(phase==5 && *p->pImageIndices==1);phase=6;return VK_SUCCESS;}
'''+body+r'''
int main(void){
 xv.fence=(VkFence)(uintptr_t)1;xv.acquireFence=(VkFence)(uintptr_t)2;
 for(unsigned resolved=0;resolved<2;resolved++)for(unsigned aa=0;aa<2;aa++){
  phase=submits=quads=0;xv.mainResolved=resolved;xvEdgeAA=aa;
  NativeRenderer_PresentVRAMRect(0,0,512,216);
  assert(phase==6 && submits==1 && quads==1);
  assert(modeSeen==(resolved?(aa?3:0):2));
 }
 phase=0;NativeRenderer_PresentVRAMRect(0,0,0,216);assert(phase==0);
 /* Widescreen: a VRAM present fills the screen. 4:3 on a widescreen output: the picture
  * and black bars; a main present copies main, whose bars are already black. */
 assert(bars==0 && quadX==0 && quadW==XV_WIDTH);
 xvPicture=(VkRect2D){{160,0},{960,XV_HEIGHT}};
 phase=0;xv.mainResolved=0;NativeRenderer_PresentVRAMRect(0,0,512,216);assert(phase==6 && quadX==160 && quadW==960 && bars==1);
 phase=0;xv.mainResolved=1;NativeRenderer_PresentVRAMRect(0,0,512,216);assert(phase==6 && quadX==0 && quadW==XV_WIDTH && bars==1);
 /* A requested screenshot waits for a finished main picture, then is taken once. */
 assert(shots==0);xvCaptureRequested=1;
 phase=0;xv.mainResolved=0;NativeRenderer_PresentVRAMRect(0,0,512,216);assert(shots==0 && xvCaptureRequested);
 phase=0;xv.mainResolved=1;NativeRenderer_PresentVRAMRect(0,0,512,216);assert(shots==1 && !xvCaptureRequested && phase==6);
 phase=0;NativeRenderer_PresentVRAMRect(0,0,512,216);assert(shots==1);
 puts("PASS: combined render/present frame submission, separate acquire fence reset before submit, present queued behind it, raw/AA/VRAM paths; 4:3 VRAM presents keep black bars");
}
'''
def run(text,name):
 file=a.out/(name+'.c');file.write_text(text);exe=a.out/name
 subprocess.run(['cc','-std=c17','-I'+str(a.vulkan/'third_party/vulkan-headers/include'),str(file),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],text=True,capture_output=True)
r=run(c,'present-submit');assert r.returncode==0,r.stderr;print(r.stdout.strip())
old=c.replace('if(w<=0 || h<=0)return;NativeRenderer_UpdateVRAM();','if(w<=0 || h<=0)return;NativeRenderer_UpdateVRAM();XvSubmit();',1)
assert old!=c and run(old,'present-submit-negative').returncode
print('PASS: previous split submission rejected')
drained=c.replace('    XvSubmitFrame();\n','    XvSubmit();\n',1)
assert drained!=c and run(drained,'present-drain-negative').returncode
shared=c.replace('VK_NULL_HANDLE,xv.acquireFence,&index','VK_NULL_HANDLE,xv.fence,&index',1)
assert shared!=c and run(shared,'present-shared-fence-negative').returncode
print('PASS: waiting present and acquisition on the frame fence rejected')
