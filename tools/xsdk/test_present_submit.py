"""Record the actual presentation path: one combined submit, fenced reuse."""
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
static struct {VkDevice device;VkSwapchainKHR swapchain;VkQueue queue;VkFence fence;XvTarget main,vram,swap[3];int mainResolved;} xv;
static struct {unsigned submits,uploads,reads,draws,passes,shaderDraws[7],quads[4];unsigned submitMS,waitMS,frameWaitMS,acquireMS,presentMS;unsigned blendDraws[5],uiDraws,feedbackRequests,midpointFeedbackSkips,skippedSTPPasses;} xvCost;
static int xvEdgeAA=1;
static unsigned phase,submits,quads,modeSeen;
#define XV_CALL(x) assert((x)==VK_SUCCESS)
static unsigned GetTickCount(void){return 1;}
static void Platform_Log(const char *format,...){}
static void NativeRenderer_UpdateVRAM(void){}
static void XvSubmit(void){assert(phase==4);phase=5;submits++;xvCost.submits++;xvCost.waitMS+=17;}
static void XvQuad(XvTarget *to,XvTarget *from,int mode,int x,int y,int w,int h,float sx,float sy,float sw,float sh){assert(phase==3 && to==&xv.swap[1]);assert(from==(xv.mainResolved?&xv.main:&xv.vram));modeSeen=mode;quads++;phase=4;}
static void XvLayout(XvTarget *target,VkImageLayout layout){assert(phase==4 && target==&xv.swap[1] && layout==VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);}
VkResult vkAcquireNextImageKHR(VkDevice d,VkSwapchainKHR s,uint64_t t,VkSemaphore sem,VkFence f,uint32_t *i){assert(phase==0);*i=1;phase=1;return VK_SUCCESS;}
VkResult vkWaitForFences(VkDevice d,uint32_t n,const VkFence *f,VkBool32 all,uint64_t t){assert(phase==1);phase=2;return VK_SUCCESS;}
VkResult vkResetFences(VkDevice d,uint32_t n,const VkFence *f){assert(phase==2);phase=3;return VK_SUCCESS;}
VkResult vkQueuePresentKHR(VkQueue q,const VkPresentInfoKHR *p){assert(phase==5 && *p->pImageIndices==1);phase=6;return VK_SUCCESS;}
'''+body+r'''
int main(void){
 for(unsigned resolved=0;resolved<2;resolved++)for(unsigned aa=0;aa<2;aa++){
  phase=submits=quads=0;xv.mainResolved=resolved;xvEdgeAA=aa;unsigned before=xvCost.frameWaitMS;
  NativeRenderer_PresentVRAMRect(0,0,512,216);
  assert(phase==6 && submits==1 && quads==1 && xvCost.frameWaitMS-before==17);
  assert(modeSeen==(resolved?(aa?3:0):2));
 }
 phase=0;NativeRenderer_PresentVRAMRect(0,0,0,216);assert(phase==0);
 puts("PASS: combined render/present submission, acquire/reset before submit, final wait before flip, raw/AA/VRAM paths");
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
