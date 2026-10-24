"""Run all actual boot checks against upstream whole-level copy validation.

The recorder supplies known pixels to test copy extent, buffer capacity and
row addressing. It cannot establish real GPU color correctness.
"""
import argparse,re,subprocess
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--vulkan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
s=(root/'platform/xsdk/native_xsdk_video.c').read_text()
upstream=(a.vulkan/'src/command_buffer.c').read_text()
def function(source,start):
 begin=source.index(start);opening=source.index('{',begin);depth=1;end=opening+1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
reader=function(s,'static void XvReadTarget(')
clearer=function(s,'static void XvClearDiagnosticTarget(')
checks=function(s,'static void XvColorCheck(void)\n{')
allocate=re.search(r'XvBufferCreate\(&xv.staging,([^,]+),',s)[1]
validator=function(upstream,'static uint32_t level_size(')+function(upstream,'static bool whole_level(')
c=r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef uint16_t u16;
typedef struct {int16_t x,y,page,clut;uint8_t u,v,bright,dither,r,g,b,a;int8_t tcx,tcy,pad0,pad1;} GrVertex;
typedef struct {int x,y,w,h;} RECT16;
typedef unsigned TexFormat;
enum {TF_4_BIT,BM_NONE=0,BM_AVERAGE,BM_ADD,BM_SUBTRACT,BM_ADD_QUATER_SOURCE};
typedef int BlendMode;
enum {XV_WIDTH=1280,XV_HEIGHT=720,XSDK_TEXTURE_3D=3};
typedef struct {VkImage image;VkImageLayout layout;unsigned width,height;int clearStencil;} XvTarget;
typedef struct {VkBuffer buffer;VkDeviceMemory memory;unsigned char *map;size_t size;} XvBuffer;
typedef struct {unsigned first,count;} Slices;
typedef struct {unsigned width,height;bool is_texture;struct {unsigned dimension,levels,depth;} texture;} Image;
static struct {
 VkDevice device;VkCommandBuffer command;XvBuffer staging;XvTarget main,off,vram;
 RECT16 offRect;int offscreen,drawPrim,vramCPUChanged,vramGPUChanged,mainValid,mainResolved;
 unsigned format,texture,vertexCursor,vertexCount;BlendMode blend;
 struct {float rect[4],scale[4],flags[4],source[4];} state;u16 pixels[1024*512];
} xv;
static struct {unsigned unused;} xvCost;
static int g_dbg_texturelessMode;
static unsigned copies,mainCopies,offCopies,logs,clears;
#define XV_CALL(x) do{if((x)!=VK_SUCCESS)exit(42);}while(0)
static void XvLayout(XvTarget *t,VkImageLayout layout){t->layout=layout;}
static void XvSubmit(void){}
static void NativeRenderer_UpdateVRAM(void){xv.vramCPUChanged=0;}
static void NativeRenderer_SetTexture(unsigned id,TexFormat f){xv.texture=id;xv.format=f;}
static unsigned NativeRenderer_GetWhiteTexture(void){return 2;}
static unsigned NativeRenderer_GetVRAMTexture(void){return 1;}
static void NativeRenderer_UpdateVertexBuffer(const GrVertex *v,int n){assert(n==6);}
static void XvDrawTriangles(int first,int n,int filtering){assert(first==0 && n==2);}
static void XvPass(XvTarget *t){}
void vkCmdClearAttachments(VkCommandBuffer c,uint32_t n,const VkClearAttachment *a,uint32_t nr,const VkClearRect *r){}
void vkCmdClearColorImage(VkCommandBuffer cb,VkImage image,VkImageLayout layout,const VkClearColorValue *color,uint32_t n,const VkImageSubresourceRange *range){
 assert(copies==30 && layout==VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && n==1);
 assert(image==(VkImage)(uintptr_t)(clears?&xv.off:&xv.main));
 assert(range->aspectMask==VK_IMAGE_ASPECT_COLOR_BIT && range->baseMipLevel==0 && range->levelCount==1 && range->baseArrayLayer==0 && range->layerCount==1);
 for(unsigned i=0;i<4;i++)assert(color->float32[i]==0);clears++;
}
VkResult vkInvalidateMappedMemoryRanges(VkDevice d,uint32_t n,const VkMappedMemoryRange *r){assert(n==1 && r->size==VK_WHOLE_SIZE);return VK_SUCCESS;}
static void Platform_Log(const char *format,...){
 va_list ap;va_start(ap,format);unsigned check=va_arg(ap,unsigned);(void)va_arg(ap,unsigned);(void)va_arg(ap,unsigned);
 unsigned bad=va_arg(ap,unsigned),r=va_arg(ap,unsigned),g=va_arg(ap,unsigned),b=va_arg(ap,unsigned);
 unsigned er=va_arg(ap,unsigned),eg=va_arg(ap,unsigned),eb=va_arg(ap,unsigned);
 assert(check==logs++ && !bad && r==er && g==eg && b==eb);va_end(ap);
}
'''+validator+r'''
void vkCmdCopyImageToBuffer(VkCommandBuffer cb,VkImage image,VkImageLayout layout,VkBuffer buffer,uint32_t n,const VkBufferImageCopy *region){
 XvTarget *target=(XvTarget *)(uintptr_t)image;assert(n==1 && layout==VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
 Image img={.width=target->width,.height=target->height,.is_texture=true,.texture={2,1,1}};Slices slices;
 if(!whole_level(&img,&region->imageSubresource,region->imageOffset,region->imageExtent,&slices) || region->bufferOffset%4)exit(42);
 size_t bytes=(size_t)target->width*target->height*4;
 if(bytes>xv.staging.size || region->bufferRowLength || region->bufferImageHeight)exit(42);
 memset(xv.staging.map,0,bytes);
 const unsigned colors[4][3]={{255,0,0},{0,255,0},{0,0,255},{255,255,255}};
 const unsigned blends[5][3]={{96,64,32},{80,80,80},{160,160,160},{0,32,96},{88,112,136}};
 for(unsigned y=0;y<32;y++)for(unsigned x=0;x<32;x++){
  unsigned rgb[3];
  if(copies<9){for(unsigned ch=0;ch<3;ch++)rgb[ch]=copies<6?colors[x&3][ch]:(colors[x&3][ch]+colors[(x+1)&3][ch]+1)/2;}
  else if(copies<13){rgb[0]=64;rgb[1]=128;rgb[2]=192;}
  else if(copies<19 || copies>=24){rgb[0]=247;rgb[1]=93;rgb[2]=31;}
  else memcpy(rgb,blends[copies-19],sizeof(rgb));
  for(unsigned ch=0;ch<3;ch++)xv.staging.map[4*(y*target->width+x)+ch]=rgb[ch];
 }
 copies++;if(target==&xv.main)mainCopies++;else {assert(target==&xv.off);offCopies++;}
}
'''+reader+clearer+checks+r'''
int main(void){
 xv.main.width=1280;xv.main.height=720;xv.off.width=1024;xv.off.height=512;
 xv.main.image=(VkImage)(uintptr_t)&xv.main;xv.off.image=(VkImage)(uintptr_t)&xv.off;
 xv.staging.size=ALLOCATION_BYTES;xv.staging.map=malloc(xv.staging.size);assert(xv.staging.map);
 XvColorCheck();assert(logs==30 && copies==30 && mainCopies==6 && offCopies==24);
 assert(clears==2 && xv.main.clearStencil && xv.off.clearStencil);
 assert(xv.mainValid==0 && xv.mainResolved==0);free(xv.staging.map);
 puts("PASS: all 30 actual boot checks; upstream whole-level validator, main/VRAM staging capacity and per-target readback pitch");
}
'''
c=c.replace('ALLOCATION_BYTES',allocate)
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=a.out/name
 subprocess.run(['cc','-std=c17','-I'+str(a.vulkan/'third_party/vulkan-headers/include'),str(source),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'boot-readback');assert r.returncode==0,r.stderr;print(r.stdout.strip())
old_extent=c.replace('.imageExtent={target->width,target->height,1}', '.imageExtent={1024,512,1}')
assert old_extent!=c and run(old_extent,'partial-level-negative').returncode==42
old_capacity=c.replace('xv.staging.size='+allocate,'xv.staging.size=1024*512*4')
assert old_capacity!=c and run(old_capacity,'capacity-negative').returncode==42
old_pitch=c.replace('y*checked->width','y*1024').replace('4*checked->width','4*1024')
assert old_pitch!=c and run(old_pitch,'pitch-negative').returncode!=0
print('PASS: prior partial-main copy, undersized staging and fixed-1024 read pitch rejected')
dirty=c.replace('XvClearDiagnosticTarget(&xv.main);XvClearDiagnosticTarget(&xv.off);','')
assert dirty!=c and run(dirty,'diagnostic-residue-negative').returncode!=0
print('PASS: both diagnostic targets cleared before game; leaving test pixels rejected')
