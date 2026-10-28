"""Run all actual boot checks against upstream whole-level copy validation.

The recorder supplies known pixels to test copy extent, buffer capacity and
row addressing. It cannot establish real GPU color correctness.
"""
import argparse,re,subprocess,json,math
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
sweep=function(s,'static unsigned XvSweepWord(')+function(s,'static void XvSweepExpected(')+function(s,'static void XvColorSweep(')+function(s,'static void XvMeshCheck(')
checks=function(s,'static void XvColorCheck(void)\n{')+function(s,'static void XvPrepareForGame(void)\n{')
# The checks run only on request, on the full 720p raster (before the 4:3 picture is set);
# the game's starting state is set either way.
boot=s[s.index('if(xvSelfTest)XvColorCheck();'):s.index('[vulkan] 720p renderer initialized')]
assert re.fullmatch(r'if\(xvSelfTest\)XvColorCheck\(\);\n    /\*[^*]*\*/\n    if\(!g_nativeHDWidescreen && video\.is_widescreen\)\{\n'
                    r'        xvSqueeze=0\.75f;\n        xvPicture=[^\n]*\n    \}\n    XvPrepareForGame\(\);\n    Platform_Log\("',boot),'boot checks not optional or starting state skipped'
allocate=re.search(r'XvBufferCreate\(&xv.staging,([^,]+),',s)[1]
validator=function(upstream,'static uint32_t level_size(')+function(upstream,'static bool in_level(')+function(upstream,'static bool whole_level(')
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
#include <math.h>
typedef uint16_t u16;typedef int16_t s16;typedef uint8_t u8;
typedef struct {int16_t x,y,page,clut;uint8_t u,v,bright,dither,r,g,b,a;int8_t tcx,tcy,pad0,pad1;} GrVertex;
typedef struct {int x,y,w,h;} RECT16;
typedef unsigned TexFormat;
enum {TF_4_BIT,TF_8_BIT,TF_16_BIT};
enum {BM_NONE=0,BM_AVERAGE,BM_ADD,BM_SUBTRACT,BM_ADD_QUATER_SOURCE};
typedef int BlendMode;
enum {XV_WIDTH=1280,XV_HEIGHT=720,XSDK_TEXTURE_3D=3};
typedef struct {VkImage image;VkImageLayout layout;unsigned width,height;int clearStencil;} XvTarget;
typedef struct {VkBuffer buffer;VkDeviceMemory memory;unsigned char *map;size_t size;} XvBuffer;
typedef struct {unsigned first,count;} Slices;
typedef struct {unsigned width,height,format;bool is_texture;struct {unsigned dimension,levels,depth;} texture;} Image;
/* The targets are uncompressed RGBA8. */
typedef struct {bool compressed;} V4xFormat;
static const V4xFormat *v4x_format(unsigned format){static const V4xFormat rgba8={false};(void)format;return &rgba8;}
static struct {
 VkDevice device;VkCommandBuffer command;XvBuffer staging;XvTarget main,off,vram;
 RECT16 offRect;int offscreen,drawPrim,vramCPUChanged,vramGPUChanged,mainValid,mainResolved,clipEnabled,ui;
 unsigned format,texture,vertexCursor,vertexCount;BlendMode blend;
 struct {float rect[4],scale[4],flags[4],source[4];} state;u16 pixels[1024*512];
} xv;
static struct {unsigned unused;} xvCost;
static int g_dbg_texturelessMode;
static unsigned copies,mainCopies,offCopies,logs,clears,meshUploads;
/* Exact CPU raster of the mesh fixture: screen positions times six are
 * integers (2.5x, 720/216 y), pixel centers 6x+3. Every interior pixel
 * must be covered once under a top-left rule and inside its UV square. */
static long long XvEdge(long long ax,long long ay,long long bx,long long by,long long px,long long py){return (bx-ax)*(py-ay)-(by-ay)*(px-ax);}
static void XvRasterMesh(const GrVertex *v,int n){
 static unsigned char cover[720][1280];memset(cover,0,sizeof(cover));
 unsigned base=v[0].u<64?0:64,limit=copies==45?64:63;
 for(int t=0;t<n;t+=3){
  long long x[3],y[3];for(int i=0;i<3;i++){x[i]=15LL*v[t+i].x;y[i]=20LL*v[t+i].y;assert(v[t+i].u>=base && v[t+i].u<=base+limit && v[t+i].v>=base && v[t+i].v<=base+limit);}
  long long area=XvEdge(x[0],y[0],x[1],y[1],x[2],y[2]);assert(area!=0);
  if(area<0){long long tx=x[1],ty=y[1];x[1]=x[2];y[1]=y[2];x[2]=tx;y[2]=ty;}
  long long minX=x[0],maxX=x[0],minY=y[0],maxY=y[0];
  for(int i=1;i<3;i++){if(x[i]<minX)minX=x[i];if(x[i]>maxX)maxX=x[i];if(y[i]<minY)minY=y[i];if(y[i]>maxY)maxY=y[i];}
  int x0=(int)(minX/6)-1,x1=(int)(maxX/6)+1,y0=(int)(minY/6)-1,y1=(int)(maxY/6)+1;
  if(x0<0)x0=0;if(y0<0)y0=0;if(x1>1279)x1=1279;if(y1>719)y1=719;
  for(int py=y0;py<=y1;py++)for(int px=x0;px<=x1;px++){
   long long cx=6LL*px+3,cy=6LL*py+3;int inside=1;
   for(int e=0;e<3&&inside;e++){long long ax=x[e],ay=y[e],bx=x[(e+1)%3],by=y[(e+1)%3],w=XvEdge(ax,ay,bx,by,cx,cy);
    int topLeft=(ay==by&&bx<ax)||(by<ay);inside=w>0||(w==0&&topLeft);}
   if(inside)cover[py][px]++;}
 }
 for(int py=69;py<651;py++)for(int px=102;px<1178;px++)assert(cover[py][px]==1);
 meshUploads++;
}
#define XV_CALL(x) do{if((x)!=VK_SUCCESS)exit(42);}while(0)
static void XvLayout(XvTarget *t,VkImageLayout layout){t->layout=layout;}
static void XvSubmit(void){}
static void NativeRenderer_UpdateVRAM(void){xv.vramCPUChanged=0;}
static void NativeRenderer_SetTexture(unsigned id,TexFormat f){xv.texture=id;xv.format=f;}
static unsigned NativeRenderer_GetWhiteTexture(void){return 2;}
static unsigned NativeRenderer_GetVRAMTexture(void){return 1;}
static void NativeRenderer_UpdateVertexBuffer(const GrVertex *v,int n){assert(n==(copies>=40?19008:copies>=34?1536:6));if(copies>=40)XvRasterMesh(v,n);}
static void XvDrawTriangles(int first,int n,int filtering){assert(first==0 && n==(copies>=40?6336:copies>=34?512:2));}
static void XvPass(XvTarget *t){}
static unsigned xvPendingFillCount=3;
void vkCmdClearAttachments(VkCommandBuffer c,uint32_t n,const VkClearAttachment *a,uint32_t nr,const VkClearRect *r){}
void vkCmdClearColorImage(VkCommandBuffer cb,VkImage image,VkImageLayout layout,const VkClearColorValue *color,uint32_t n,const VkImageSubresourceRange *range){
 assert(copies==46 && layout==VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && n==1);
 assert(image==(VkImage)(uintptr_t)(clears?&xv.off:&xv.main));
 assert(range->aspectMask==VK_IMAGE_ASPECT_COLOR_BIT && range->baseMipLevel==0 && range->levelCount==1 && range->baseArrayLayer==0 && range->layerCount==1);
 for(unsigned i=0;i<4;i++)assert(color->float32[i]==0);clears++;
}
VkResult vkInvalidateMappedMemoryRanges(VkDevice d,uint32_t n,const VkMappedMemoryRange *r){assert(n==1 && r->size==VK_WHOLE_SIZE);return VK_SUCCESS;}
static void Platform_Log(const char *format,...){
 va_list ap;va_start(ap,format);unsigned check=va_arg(ap,unsigned);(void)va_arg(ap,unsigned);(void)va_arg(ap,unsigned);
 unsigned bad=va_arg(ap,unsigned),total=va_arg(ap,unsigned),r=va_arg(ap,unsigned),g=va_arg(ap,unsigned),b=va_arg(ap,unsigned);
 unsigned er=va_arg(ap,unsigned),eg=va_arg(ap,unsigned),eb=va_arg(ap,unsigned);
 assert(check==logs++ && !bad && total==(check>=40?626232:check>=34?65536:check>=30?506880:900));
 assert(abs((int)r-(int)er)<=1 && abs((int)g-(int)eg)<=1 && abs((int)b-(int)eb)<=1);va_end(ap);
}
'''+validator+r'''
void vkCmdCopyImageToBuffer(VkCommandBuffer cb,VkImage image,VkImageLayout layout,VkBuffer buffer,uint32_t n,const VkBufferImageCopy *region){
 XvTarget *target=(XvTarget *)(uintptr_t)image;assert(n==1 && layout==VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
 Image img={.width=target->width,.height=target->height,.is_texture=true,.texture={2,1,1}};Slices slices;
 if(!whole_level(&img,&region->imageSubresource,region->imageOffset,region->imageExtent,&slices) || region->bufferOffset%4)exit(42);
 size_t bytes=(size_t)target->width*target->height*4;
 if(bytes>xv.staging.size || region->bufferRowLength || region->bufferImageHeight)exit(42);
 memset(xv.staging.map,0,bytes);
 if(copies>=40){
  assert(target==&xv.main);
  for(size_t i=0;i<bytes;i+=4){xv.staging.map[i]=copies==40?64:255;xv.staging.map[i+1]=xv.staging.map[i+2]=copies==40?64:0;}
  MESH_DEFECT copies++;mainCopies++;return;
 }
 if(copies>=34){
  const char *paths[]={SWEEP_PATHS};FILE *file=fopen(paths[copies-34],"rb");assert(file && target==&xv.off);
  for(unsigned y=0;y<256;y++)assert(fread(xv.staging.map+4*y*target->width,1,256*4,file)==256*4);
  fclose(file);copies++;offCopies++;return;
 }
 const unsigned colors[4][3]={{255,0,0},{0,255,0},{0,0,255},{255,255,255}};
 const unsigned blends[5][3]={{96,64,32},{80,80,80},{160,160,160},{0,32,96},{88,112,136}};
 for(unsigned y=0;y<(copies>=30?target->height:32);y++)for(unsigned x=0;x<(copies>=30?target->width:32);x++){
  unsigned rgb[3];
  if(copies<9){for(unsigned ch=0;ch<3;ch++)rgb[ch]=copies<6?colors[x&3][ch]:(colors[x&3][ch]+colors[(x+1)&3][ch]+1)/2;}
  else if(copies<13){rgb[0]=64;rgb[1]=128;rgb[2]=192;}
  else if(copies<19 || copies>=24){rgb[0]=247;rgb[1]=93;rgb[2]=31;}
  else memcpy(rgb,blends[copies-19],sizeof(rgb));
  for(unsigned ch=0;ch<3;ch++)xv.staging.map[4*(y*target->width+x)+ch]=rgb[ch];
 }
 copies++;if(target==&xv.main)mainCopies++;else {assert(target==&xv.off);offCopies++;}
}
'''+reader+clearer+sweep+checks+r'''
int main(void){
 xv.main.width=1280;xv.main.height=720;xv.off.width=1024;xv.off.height=512;
 xv.main.image=(VkImage)(uintptr_t)&xv.main;xv.off.image=(VkImage)(uintptr_t)&xv.off;
 xv.staging.size=ALLOCATION_BYTES;xv.staging.map=malloc(xv.staging.size);assert(xv.staging.map);
 XvColorCheck();XvPrepareForGame();assert(logs==46 && copies==46 && mainCopies==16 && offCopies==30 && meshUploads==6);
 assert(clears==2 && xv.main.clearStencil && xv.off.clearStencil && xvPendingFillCount==0);
 assert(xv.mainValid==0 && xv.mainResolved==0);free(xv.staging.map);
 puts("PASS: all 46 actual boot checks including color/index sweeps and mesh coverage/UV range/filter fringe; independent fixture pixels, exact watertight mesh raster, whole-level validator, staging capacity and pitch");
}
'''
c=c.replace('ALLOCATION_BYTES',allocate)
c_meshless=c
c=c.replace('MESH_DEFECT ','')
# Independent Python pixel model, quantized as a GPU RGBA8 target would be.
paths=[]
for case in range(6):
 fmt=case%3;filtered=case>=3;pixels=bytearray()
 for row in range(256):
  for x in range(256):
   span=16 if fmt==0 else 255;u=(x+.5)*span/256+1/4096;v=(row if fmt==2 else 0)+1/4096
   if filtered:u=min(u,span-1);v=math.floor(v)
   tx,ty=math.floor(u),math.floor(v);fx=u-tx if filtered else 0;fy=v-ty if filtered else 0
   def word(dx,dy):return (((ty+dy)%256)<<8)|((tx+dx)%256) if fmt==2 else (row<<8)+(((tx+dx)%16)*17 if fmt==0 else (tx+dx)%256)
   if word(0,0)==0:rgb=[0,0,0]
   else:
    taps=[(word(dx,dy),(fx if dx else 1-fx)*(fy if dy else 1-fy)) for dy in range(2) for dx in range(2)]
    coverage=max(.0001,sum(weight for value,weight in taps if value))
    rgb=[sum(((value>>shift)&31)/31*weight for value,weight in taps if value)/coverage*255 for shift in (0,5,10)]
   pixels.extend([max(0,min(255,math.floor(channel+.5))) for channel in rgb]+[0])
 path=a.out/('sweep-%d.rgba'%case);path.write_bytes(pixels);paths.append(json.dumps(str(path)))
c=c.replace('SWEEP_PATHS',','.join(paths))
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=a.out/name
 subprocess.run(['cc','-std=c17','-I'+str(a.vulkan/'third_party/vulkan-headers/include'),str(source),'-lm','-o',str(exe)],check=True)
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
def sweep_paths(text):return text.replace('SWEEP_PATHS',','.join(paths))
gap=sweep_paths(c_meshless.replace('MESH_DEFECT ','if(copies==40)xv.staging.map[4*(300*1280+500)]=0;'))
assert run(gap,'mesh-gap-negative').returncode!=0
drift=sweep_paths(c_meshless.replace('MESH_DEFECT ','if(copies==43){xv.staging.map[4*(400*1280+700)]=0;xv.staging.map[4*(400*1280+700)+2]=255;}'))
assert run(drift,'uv-drift-negative').returncode!=0
torn=c.replace('const unsigned order[2][6]={{0,1,2,2,1,3},{0,1,3,0,3,2}};','const unsigned order[2][6]={{0,1,2,0,1,2},{0,1,3,0,3,2}};')
assert torn!=c and run(torn,'mesh-fixture-negative').returncode!=0
print('PASS: mesh gap, out-of-range UV pixel and torn mesh fixture rejected')
