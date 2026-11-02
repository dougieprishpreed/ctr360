"""Run the actual VRAM write upload against a fake GPU that keeps its own VRAM.

The track preview movies write a 170 by 71 frame into VRAM each update. Every
write used to read the whole VRAM back first (a CPU copy out of write-combined
memory, about 50 ms) and upload all of it again, so the track list ran at 6 FPS.
A write now uploads only its rectangle, through rows a copy draws into an upload
image and a quad from there into VRAM. Checks: a frame lands exactly with no
readback and the GPU keeps what it drew around it; two writes apart while the
GPU holds pixels the CPU lacks go up one at a time, so nothing stale lands
between them; a CPU read uploads pending writes before it reads back; without
rectangle uploads one readback keeps the written rectangle; copies within VRAM
read back first. Uploading a bounding box of stale pixels, and a fallback that
loses the rectangle, are rejected.
"""
import argparse, subprocess
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--vulkan', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
p.add_argument('--cc', default='cc'); a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
s = (root / 'platform/xsdk/native_xsdk_video.c').read_text()
def function(source, start):
    begin = source.index(start); op = source.index('{', begin); depth = 1; end = op + 1
    while depth: depth += (source[end] == '{') - (source[end] == '}'); end += 1
    return source[begin:end] + '\n'
code = ''.join(function(s, name) for name in ('static void XvReadBack(', 'static void XvSyncCPU(', 'static void XvDirty(',
    'static void XvDirtyAll(', 'static void XvUploadAll(', 'static void XvUploadRect(', 'void NativeRenderer_UpdateVRAM(void)\n{'))
code += s[s.index('void NativeRenderer_CopyVRAM('):s.index('\nvoid NativeRenderer_ReadVRAM(')]
c = r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int64_t s64;
#define VRAM_WIDTH 1024
#define VRAM_HEIGHT 512
#define XV_CALL(x) assert((x)==VK_SUCCESS)
typedef struct {VkImage image;VkImageLayout layout;} XvTarget;
typedef struct {VkBuffer buffer;VkDeviceMemory memory;unsigned char *map;} XvBuffer;
static struct {VkDevice device;VkCommandBuffer command;XvTarget vram,upload;XvBuffer staging,uploadRows;
 int vramCPUChanged,vramGPUChanged,dirty[4],uploadReady;u16 pixels[1024*512],move[1024*512];} xv;
static struct {unsigned uploads,reads;} xvCost;
void NativeRenderer_UpdateVRAM(void);
/* The fake GPU: its VRAM and upload image, and what it should hold. */
static u16 gpu[1024*512],uploadImage[1024*512],expected[1024*512];
static unsigned readbacks,wholeUploads,rectUploads;
static void XvBegin(void){}
static void XvEndPass(void){}
static void XvSubmit(void){}
static void XvLayout(XvTarget *t,VkImageLayout l){t->layout=l;}
static void XvApplyFills(void){}
static void XvPaletteReset(void){}
static void XvReadTarget(XvTarget *t){
 assert(t==&xv.vram);readbacks++;
 for(int i=0;i<1024*512;i++){xv.staging.map[4*i]=(u8)gpu[i];xv.staging.map[4*i+1]=(u8)(gpu[i]>>8);}
}
VkResult vkFlushMappedMemoryRanges(VkDevice d,uint32_t n,const VkMappedMemoryRange *r){(void)d;(void)n;(void)r;return VK_SUCCESS;}
void vkCmdCopyBufferToImage(VkCommandBuffer c,VkBuffer b,VkImage image,VkImageLayout l,uint32_t n,const VkBufferImageCopy *r){
 (void)c;assert(n==1 && l==VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && !r->imageOffset.x && !r->imageOffset.y);
 if(image==xv.vram.image){
  assert(b==xv.staging.buffer && r->imageExtent.width==1024 && r->imageExtent.height==512);
  for(int i=0;i<1024*512;i++)gpu[i]=(u16)(xv.staging.map[4*i]|xv.staging.map[4*i+1]<<8);
  wholeUploads++;return;
 }
 /* vulkan4xenon's drawn_upload: a linear texture's 64-texel pitch, the 8-pixel grid. */
 unsigned pitch=r->bufferRowLength,w=r->imageExtent.width,h=r->imageExtent.height;
 assert(image==xv.upload.image && b==xv.uploadRows.buffer && pitch%64==0 && w%8==0 && h%8==0 && w<=pitch && w<=1024 && h<=512);
 for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
  const u8 *in=xv.uploadRows.map+4*(y*pitch+x);uploadImage[y*1024+x]=(u16)(in[0]|in[1]<<8);
 }
 rectUploads++;
}
static void XvQuad(XvTarget *to,XvTarget *from,int mode,int x,int y,int w,int h,float sx,float sy,float sw,float sh){
 assert(to==&xv.vram && from==&xv.upload && mode==0 && sx==0 && sy==0 && sw==w/1024.0f && sh==h/512.0f);
 for(int r=0;r<h;r++)for(int c=0;c<w;c++){
  const u8 *bytes=xv.uploadRows.map+4*(r*((w+63)&~63)+c);assert(bytes[2]==0 && bytes[3]==255);
  gpu[(y+r)*1024+x+c]=uploadImage[r*1024+c];
 }
}
'''+code+r'''
/* The GPU draws (a pack, a fill): pixels the CPU lacks. */
static void Draw(int x,int y,int w,int h,int seed){
 for(int r=0;r<h;r++)for(int c=0;c<w;c++)gpu[(y+r)*1024+x+c]=expected[(y+r)*1024+x+c]=(u16)(seed*977+r*31+c*7);
 xv.vramGPUChanged=1;
}
static u16 frame[1024*512];
static void Write(int x,int y,int w,int h,int seed){
 for(int i=0;i<w*h;i++)frame[i]=(u16)(seed*131+i*3);
 for(int r=0;r<h;r++)for(int c=0;c<w;c++)expected[(y+r)*1024+x+c]=frame[r*w+c];
 NativeRenderer_CopyVRAM(frame,0,0,w,h,x,y);
}
static void Same(void){assert(!memcmp(gpu,expected,sizeof(gpu)));}
int main(void){
 xv.vram.image=(VkImage)1;xv.upload.image=(VkImage)2;xv.staging.buffer=(VkBuffer)3;xv.uploadRows.buffer=(VkBuffer)4;
 xv.staging.map=calloc(1024*512,4);xv.uploadRows.map=calloc(1024*544,4);assert(xv.staging.map && xv.uploadRows.map);
 xv.uploadReady=1;
 /* Boot: the whole image goes up. */
 for(int i=0;i<1024*512;i++)xv.pixels[i]=expected[i]=(u16)(i*37+9);
 XvDirtyAll();NativeRenderer_UpdateVRAM();Same();assert(wholeUploads==1 && !readbacks);
 /* A movie frame at an odd place beside what the GPU drew: no readback, one rectangle. */
 Draw(0,0,512,216,1);Write(343,77,170,71,2);NativeRenderer_UpdateVRAM();
 Same();assert(!readbacks && rectUploads==1 && wholeUploads==1);
 /* Every update, a frame: still no readback. */
 for(int k=0;k<30;k++){Draw(0,0,512,216,10+k);Write(343,77,170,71,40+k);NativeRenderer_UpdateVRAM();}
 Same();assert(!readbacks && rectUploads==31);
 /* Two writes apart while the GPU holds pixels the CPU lacks between them. */
 Draw(600,300,100,100,3);Write(610,310,8,8,4);Write(680,380,8,8,5);NativeRenderer_UpdateVRAM();
 Same();assert(!readbacks && rectUploads==33);
 /* Slices side by side in one rectangle (retail MDEC strips): one upload. */
 Write(100,100,16,32,6);Write(100,100,16,32,7);NativeRenderer_UpdateVRAM();Same();assert(rectUploads==34);
 /* A CPU read: pending writes go up, then everything comes back. */
 Draw(200,300,64,64,8);Write(100,400,20,10,9);XvSyncCPU();
 Same();assert(!memcmp(xv.pixels,expected,sizeof(expected)) && readbacks==1 && !xv.vramCPUChanged && !xv.vramGPUChanged);
 /* A copy within VRAM reads back first. */
 Draw(700,10,40,40,10);
 for(int r=0;r<40;r++)for(int c=0;c<40;c++)expected[(100+r)*1024+800+c]=expected[(10+r)*1024+700+c];
 NativeRenderer_CopyVRAM(NULL,700,10,40,40,800,100);NativeRenderer_UpdateVRAM();Same();assert(readbacks==2);
 /* Without rectangle uploads: one readback, the whole image, the rectangle kept. */
 xv.uploadReady=0;Draw(0,0,512,216,11);Write(5,5,33,17,12);NativeRenderer_UpdateVRAM();
 Same();assert(readbacks==3 && wholeUploads==2);
 puts("PASS: actual VRAM writes upload only their rectangle: a 170x71 movie frame beside GPU drawing, 31 frames without a readback, writes apart uploaded one at a time, side-by-side slices once; CPU reads and VRAM copies upload pending writes before one readback; the fallback keeps the rectangle");
 return 0;
}
'''
def run(text, name):
    source = a.out / (name + '.c'); source.write_text(text); exe = a.out / name
    subprocess.run([a.cc, '-std=gnu17', '-w', '-I' + str(a.vulkan / 'third_party/vulkan-headers/include'), str(source), '-o', str(exe)], check=True)
    return subprocess.run([str(exe.resolve())], capture_output=True, text=True)
r = run(c, 'vram-upload'); assert r.returncode == 0, r.stdout + r.stderr; print(r.stdout.strip())
box = c.replace('if(xv.vramGPUChanged && !(x<=d[0]', 'if(0 && xv.vramGPUChanged && !(x<=d[0]')
assert box != c and run(box, 'vram-upload-box').returncode != 0
lost = c.replace('for(int row=0;row<h;row++)memcpy(xv.pixels+(y+row)*1024+x,xv.move+row*w,w*2);', '')
assert lost != c and run(lost, 'vram-upload-lost').returncode != 0
print('PASS: a bounding box of stale pixels between writes, and a fallback readback that loses the rectangle, rejected')
