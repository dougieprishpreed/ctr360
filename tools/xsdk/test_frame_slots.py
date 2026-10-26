"""Execute the actual frame-slot submission against an in-order fake GPU.

A presented frame stays in flight while the next one is recorded. The CPU must
never write vertex/uniform storage that an in-flight submission references, nor
begin/reset a command buffer still on the GPU; drains must leave it idle.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--vulkan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
s=(root/'platform/xsdk/native_xsdk_video.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
sizes=re.search(r'enum \{ XV_WIDTH=.*?\};',s,re.S)[0]
code=''.join(function(s,name) for name in ('static void XvBegin(','static void XvEndPass(','static void XvQueue(',
 'static unsigned XvWait(','static void XvSubmit(','static void XvSubmitFrame(','static void XvReserveUniform(',
 'static void XvBindUniform(','void NativeRenderer_UpdateVertexBuffer(','void NativeRenderer_BeginScene('))
# The upload stores whole vertices; record its destination like any CPU write.
upload='XvVertex *out=(XvVertex *)(xv.vertices.map+xv.vertexCursor);xv.vertexCursor+=bytes;'
assert code.count(upload)==1
code=code.replace(upload,upload+'Tracked(out,out,bytes);')
c=r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_VERTEX_BUFFER_SIZE (1u<<16)
typedef struct {int16_t x,y,page,clut;uint8_t u,v,bright,dither,r,g,b,a;int8_t tcx,tcy,p0,p1;} GrVertex;
typedef uint8_t u8;
typedef struct {GrVertex v;u8 uvMin[2],uvMax[2];} XvVertex;
typedef struct {float rect[4],scale[4],flags[4],source[4];} XvUniform;
typedef struct {int clearStencil;} XvTarget;
typedef struct {VkDeviceMemory memory;unsigned char *map;} XvBuffer;
'''+sizes+r'''
static struct {
 VkDevice device;VkQueue queue;VkCommandBuffer command,commands[2];VkFence fence,fences[2];unsigned slot;int pending[2];
 XvBuffer vertices,uniforms;unsigned vertexCursor,vertexBase,vertexCount,uniformCursor,uniformAlignment;
 const GrVertex *sourceVertices;XvTarget *target,main;int recording,inPass,mainValid,mainResolved,offscreen;
 VkDescriptorSet sets[4];VkPipelineLayout pipelineLayout;
} xv;
static struct {unsigned submits,submitMS,waitMS,frameWaitMS;} xvCost;
static int xvRevealHoles;
static unsigned revealClears;
static int xvDrawLogState,xvDrawLogTruncated;static size_t xvDrawLogSize,loggedBytes;
static void XvLog(const void *d,size_t n){assert(xvDrawLogState==2);loggedBytes+=n;}
/* reveal_holes: one whole-target magenta clear, inside the frame's main pass. */
void vkCmdClearAttachments(VkCommandBuffer cb,uint32_t n,const VkClearAttachment *c,uint32_t r,const VkClearRect *rect){
 assert(xvRevealHoles && xv.inPass && xv.target==&xv.main && n==1 && r==1 && c->clearValue.color.float32[0]==1 &&
  c->clearValue.color.float32[1]==0 && c->clearValue.color.float32[2]==1 && rect->rect.extent.width==1280 && rect->rect.extent.height==720);
 revealClears++;}
static unsigned GetTickCount(void){return 0;}
#define XV_CALL(x) do{if((x)!=VK_SUCCESS)abort();}while(0)
/* Fake GPU: per-slot writes since the slot's last submission travel with it. */
typedef struct {size_t lo,hi;} Range;
static Range uncommitted[2][512];static unsigned uncommittedCount[2];
static struct {int slot,live;Range ranges[512];unsigned count;} flight[8];static unsigned flights;
static int signaled[2],begun[2];
static unsigned char *base;
static int SlotOf(const void *handle){for(int i=0;i<2;i++)if(handle==(const void *)xv.commands[i] || handle==(const void *)xv.fences[i])return i;abort();}
static unsigned Live(void){unsigned n=0;for(unsigned i=0;i<flights;i++)n+=flight[i].live;return n;}
static void *Tracked(void *to,const void *from,size_t n){
 size_t lo=(unsigned char *)to-base,hi=lo+n;
 for(unsigned i=0;i<flights;i++)if(flight[i].live)for(unsigned r=0;r<flight[i].count;r++)
  assert(hi<=flight[i].ranges[r].lo || lo>=flight[i].ranges[r].hi);
 assert(uncommittedCount[xv.slot]<512);uncommitted[xv.slot][uncommittedCount[xv.slot]++]=(Range){lo,hi};
 return memmove(to,from,n);
}
#define memcpy Tracked
VkResult vkBeginCommandBuffer(VkCommandBuffer cb,const VkCommandBufferBeginInfo *i){int s=SlotOf(cb);assert(s==(int)xv.slot && !xv.pending[s] && !begun[s]);begun[s]=1;return VK_SUCCESS;}
VkResult vkEndCommandBuffer(VkCommandBuffer cb){assert(begun[SlotOf(cb)]);return VK_SUCCESS;}
VkResult vkFlushMappedMemoryRanges(VkDevice d,uint32_t n,const VkMappedMemoryRange *r){return VK_SUCCESS;}
void vkCmdEndRenderPass(VkCommandBuffer cb){}
void vkCmdBindDescriptorSets(VkCommandBuffer cb,VkPipelineBindPoint p,VkPipelineLayout l,uint32_t f,uint32_t n,const VkDescriptorSet *s,uint32_t o,const uint32_t *d){}
VkResult vkQueueSubmit(VkQueue q,uint32_t n,const VkSubmitInfo *info,VkFence fence){
 int s=SlotOf(fence);assert(n==1 && SlotOf(info->pCommandBuffers[0])==s && !signaled[s] && flights<8);
 for(unsigned i=0;i<flights;i++)assert(!(flight[i].live && flight[i].slot==s));
 flight[flights].slot=s;flight[flights].live=1;flight[flights].count=uncommittedCount[s];
 memcpy(flight[flights].ranges,uncommitted[s],sizeof(Range)*uncommittedCount[s]);
 uncommittedCount[s]=0;flights++;
 /* Retire completed submissions to keep the table short. */
 unsigned kept=0;for(unsigned i=0;i<flights;i++)if(flight[i].live)flight[kept++]=flight[i];flights=kept;
 return VK_SUCCESS;
}
VkResult vkWaitForFences(VkDevice d,uint32_t n,const VkFence *f,VkBool32 all,uint64_t t){
 int s=SlotOf(*f),found=-1;for(unsigned i=0;i<flights;i++)if(flight[i].live && flight[i].slot==s)found=(int)i;
 assert(found>=0 || signaled[s]);
 for(int i=0;i<=found;i++)if(flight[i].live){flight[i].live=0;signaled[flight[i].slot]=1;} /* in order */
 return VK_SUCCESS;
}
VkResult vkResetFences(VkDevice d,uint32_t n,const VkFence *f){int s=SlotOf(*f);assert(signaled[s]);signaled[s]=0;return VK_SUCCESS;}
VkResult vkResetCommandBuffer(VkCommandBuffer cb,VkCommandBufferResetFlags f){int s=SlotOf(cb);
 for(unsigned i=0;i<flights;i++)assert(!(flight[i].live && flight[i].slot==s));begun[s]=0;return VK_SUCCESS;}
static void NativeRenderer_UpdateVRAM(void){}
static void XvStampStart(void){}
static void XvStampEnd(void){}
static void XvStampRead(unsigned slot){(void)slot;}
static void XvBegin(void);
static void XvPass(XvTarget *target){XvBegin();xv.inPass=1;xv.target=target;}
#undef memcpy
#define memcpy Tracked
'''+code+r'''
#undef memcpy
static GrVertex source[1u<<16];
int main(void){
 size_t bytes=XV_VERTEX_BYTES+XV_UNIFORM_BYTES;base=calloc(1,bytes);assert(base);
 xv.vertices.map=base;xv.uniforms.map=base+XV_VERTEX_BYTES;xv.vertices.memory=(VkDeviceMemory)(uintptr_t)1;xv.uniformAlignment=256;
 xv.commands[0]=(VkCommandBuffer)(uintptr_t)0x10;xv.commands[1]=(VkCommandBuffer)(uintptr_t)0x20;
 xv.fences[0]=(VkFence)(uintptr_t)0x30;xv.fences[1]=(VkFence)(uintptr_t)0x40;
 xv.slot=0;xv.command=xv.commands[0];xv.fence=xv.fences[0];
 unsigned seed=12345,frames=0,drains=0,overflows=0;XvUniform state={0};
 for(unsigned frame=0;frame<400;frame++){
  unsigned clearsBefore=revealClears;xvRevealHoles=frame%3==1;
  if(frame==5)xvDrawLogState=1;         /* a capture request arms recording for the next frame start */
  if(frame==6)assert(xvDrawLogState==2 && loggedBytes>0);
  if(frame==7)xvDrawLogState=0;
  NativeRenderer_BeginScene();assert(revealClears==clearsBefore+(unsigned)xvRevealHoles);
  unsigned draws=20+frame%60;
  for(unsigned draw=0;draw<draws;draw++){
   seed=seed*1664525u+1013904223u;
   if(seed%5==0){unsigned before=xv.vertexCursor;NativeRenderer_UpdateVertexBuffer(source,(int)(1000+(seed>>8)%(frame%50==7?65536:12000)));overflows+=xv.vertexCursor<before;}
   if(frame%11==3 && draw==draws/2){XvSubmit();assert(Live()==0);drains++;XvPass(&xv.main);} /* readback/upload */
   XvPass(&xv.main);XvReserveUniform();XvBindUniform(&state,0);   /* as XvDrawTriangles */
  }
  XvPass(&xv.main);XvSubmitFrame();frames++;                      /* present quad, then submit */
  assert(Live()<=1 && !xv.pending[xv.slot]);   /* one frame in flight, the recording slot free */
 }
 XvSubmit();assert(Live()==0);
 printf("PASS: %u pipelined frames, %u drains, %u vertex rewinds; no CPU write into in-flight storage, no busy command buffer reuse; %u reveal_holes frame clears\n",frames,drains,overflows,revealClears);
}
'''
def run(text,name):
 file=a.out/(name+'.c');file.write_text(text);exe=a.out/name
 subprocess.run(['cc','-std=c17','-I'+str(a.vulkan/'third_party/vulkan-headers/include'),str(file),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],text=True,capture_output=True)
r=run(c,'frame-slots');assert r.returncode==0,r.stderr;print(r.stdout.strip())
negatives={
 'no-backpressure':('xvCost.frameWaitMS+=XvWait(xv.slot);',''),
 'shared-vertex-rewind':('xv.vertexCursor=xv.slot*XV_VERTEX_SLOT_BYTES;xv.vertexCount=0;','xv.vertexCursor=0;xv.vertexCount=0;'),
 'partial-drain':('    XvWait(xv.slot^1);\n',''),
 'shared-uniforms':('xv.uniformCursor=xv.slot*XV_UNIFORM_SLOT_BYTES;','xv.uniformCursor=0;'),
}
for name,(old,new) in negatives.items():
 bad=c.replace(old,new,-1 if name=='shared-uniforms' else 1);assert bad!=c,name
 assert run(bad,'frame-slots-'+name).returncode!=0,name
print('PASS: missing backpressure, shared vertex rewind, partial drain and shared uniform storage rejected')
