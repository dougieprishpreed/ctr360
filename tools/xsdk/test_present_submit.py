"""Record the actual presentation path: one combined, unwaited frame submit.

A requested diagnostic capture reads the rendered main target before the
swapchain image is acquired; the actual writer produces a bottom-up 24-bit
BMP and a little-endian VRAM dump.
"""
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
static struct {VkDevice device;VkSwapchainKHR swapchain;VkQueue queue;VkFence fence,acquireFence;XvTarget main,vram,swap[3];int mainResolved;} xv;
static struct {unsigned submits,uploads,reads,draws,passes,shaderDraws[7],quads[4];unsigned submitMS,waitMS,frameWaitMS,acquireMS,presentMS;unsigned blendDraws[5],uiDraws,feedbackRequests,midpointFeedbackSkips,skippedSTPPasses;unsigned gpuFrames,gpuTotalUS,gpuMaxUS,gpuOver16;unsigned trisRequested,trisDrawn,trisDropped,trisSkipped;} xvCost;
static int xvEdgeAA=1,xvCaptureRequested;
static unsigned phase,submits,quads,modeSeen,captures;
static void XvWriteCapture(void){assert(phase==0 && xv.mainResolved);captures++;}
#define XV_CALL(x) assert((x)==VK_SUCCESS)
static unsigned GetTickCount(void){return 1;}
static void Platform_Log(const char *format,...){}
static void NativeRenderer_UpdateVRAM(void){}
static void XvSubmit(void){assert(0);}
static void XvSubmitFrame(void){assert(phase==4);phase=5;submits++;xvCost.submits++;}
static void XvQuad(XvTarget *to,XvTarget *from,int mode,int x,int y,int w,int h,float sx,float sy,float sw,float sh){assert(phase==3 && to==&xv.swap[1]);assert(from==(xv.mainResolved?&xv.main:&xv.vram));modeSeen=mode;quads++;phase=4;}
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
 /* A capture waits for a rendered main target, then runs once, before acquisition. */
 phase=submits=quads=0;xv.mainResolved=0;xvCaptureRequested=1;NativeRenderer_PresentVRAMRect(0,0,512,216);
 assert(phase==6 && captures==0 && xvCaptureRequested==1);
 phase=submits=quads=0;xv.mainResolved=1;NativeRenderer_PresentVRAMRect(0,0,512,216);
 assert(phase==6 && captures==1 && xvCaptureRequested==0);
 phase=submits=quads=0;NativeRenderer_PresentVRAMRect(0,0,512,216);assert(phase==6 && captures==1);
 puts("PASS: combined render/present frame submission, separate acquire fence reset before submit, present queued behind it, raw/AA/VRAM paths; capture before acquisition only for a rendered frame");
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
# The actual capture writer, against a known 1280x720 pattern and VRAM words.
writer=s[s.index('static void XvWriteCapture('):s.index('void NativeRenderer_PresentVRAMRect(')]
out=str(a.out).replace('\\','/')
w=r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint16_t u16;
enum {XV_WIDTH=1280,XV_HEIGHT=720};
typedef struct {int id;} XvTarget;
static unsigned char staging[XV_WIDTH*XV_HEIGHT*4];
static struct {XvTarget main;struct {unsigned char *map;} staging;u16 pixels[1024*512];} xv;
static int xvRevealHoles=1,xvEdgeAA=1,g_cfg_bilinearFiltering=1,g_nativePreciseVertices=1;
static unsigned xvCaptureCount=7,reads,syncs;
static void XvReadTarget(XvTarget *t){assert(t==&xv.main);reads++;}
static void XvSyncCPU(void){assert(reads==1);syncs++;}
static void Platform_Log(const char *f,...){}
static FILE *test_fopen(const char *path,const char *mode){
 char host[512];assert(!strncmp(path,"game:/",6));snprintf(host,sizeof host,"%s/%s",OUT,path+6);return fopen(host,mode);}
#define fopen test_fopen
'''+writer+r'''
#undef fopen
int main(void){
 xv.staging.map=staging;
 for(int y=0;y<XV_HEIGHT;y++)for(int x=0;x<XV_WIDTH;x++){unsigned char *p=staging+(y*XV_WIDTH+x)*4;p[0]=x;p[1]=y;p[2]=x^y;p[3]=255;}
 for(int i=0;i<1024*512;i++)xv.pixels[i]=(u16)(i*2654435761u>>7);
 XvWriteCapture();assert(reads==1 && syncs==1 && xvCaptureCount==8);
 char path[512];snprintf(path,sizeof path,"%s/capture_007.bmp",OUT);FILE *f=fopen(path,"rb");assert(f);
 static unsigned char bmp[54+XV_WIDTH*XV_HEIGHT*3];size_t n=fread(bmp,1,sizeof bmp+1,f);fclose(f);assert(n==sizeof bmp);
 #define U32(o) ((unsigned)bmp[o]|bmp[o+1]<<8|bmp[o+2]<<16|(unsigned)bmp[o+3]<<24)
 assert(bmp[0]=='B'&&bmp[1]=='M'&&U32(2)==sizeof bmp&&U32(10)==54&&U32(14)==40&&U32(18)==XV_WIDTH&&U32(22)==XV_HEIGHT);
 assert(bmp[26]==1&&bmp[28]==24&&U32(30)==0);
 for(int y=0;y<XV_HEIGHT;y+=37)for(int x=0;x<XV_WIDTH;x+=29){
  const unsigned char *q=bmp+54+((XV_HEIGHT-1-y)*XV_WIDTH+x)*3;assert(q[0]==(unsigned char)(x^y)&&q[1]==(unsigned char)y&&q[2]==(unsigned char)x);}
 snprintf(path,sizeof path,"%s/capture_007_vram.bin",OUT);f=fopen(path,"rb");assert(f);
 static unsigned char vram[1024*512*2];n=fread(vram,1,sizeof vram+1,f);fclose(f);assert(n==sizeof vram);
 for(int i=0;i<1024*512;i+=997)assert((vram[2*i]|vram[2*i+1]<<8)==xv.pixels[i]);
 puts("PASS: actual capture writer: 1280x720 bottom-up 24-bit BMP (BGR), little-endian 1024x512 VRAM words, numbered files");
}
'''
w=w.replace('OUT','"'+out+'"')
r=run(w,'capture-writer');assert r.returncode==0,r.stderr+r.stdout;print(r.stdout.strip())
