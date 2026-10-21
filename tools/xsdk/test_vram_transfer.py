"""Execute the actual Vulkan backend's CPU VRAM transfer and clipping code."""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
s=(root/'platform/xsdk/native_xsdk_video.c').read_text()
body=s[s.index('void NativeRenderer_CopyVRAM('):s.index('\nvoid NativeRenderer_ReadVRAM(')]
c=r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>
typedef int64_t s64;typedef uint16_t u16;
#define VRAM_WIDTH 1024
#define VRAM_HEIGHT 512
static struct {u16 pixels[1024*512];int vramCPUChanged;} xv;
static void XvSyncCPU(void) {}
"""+body+r"""
static u16 old[1024*512],expected[1024*512],external[100];
static void check(int externalSource,int x,int y,int w,int h,int dx,int dy) {
 for(int i=0;i<1024*512;i++)xv.pixels[i]=(u16)(i*37+9);
 memcpy(old,xv.pixels,sizeof(old));memcpy(expected,old,sizeof(old));
 for(int i=0;i<100;i++)external[i]=(u16)(i+0x4000);
 int sw=externalSource?w:1024,sh=externalSource?h:512;
 const u16 *source=externalSource?external:old;
 // Brute force reference applies the requested translation to valid pixels.
 if(w>0 && h>0 && w<=32 && h<=32)for(int row=0;row<h;row++)for(int col=0;col<w;col++) {
  int64_t sx=(int64_t)x+col,sy=(int64_t)y+row,tx=(int64_t)dx+col,ty=(int64_t)dy+row;
  if(sx>=0 && sx<sw && sy>=0 && sy<sh && tx>=0 && tx<1024 && ty>=0 && ty<512)
   expected[ty*1024+tx]=source[sy*sw+sx];
 }
 NativeRenderer_CopyVRAM(externalSource?external:NULL,x,y,w,h,dx,dy);
 assert(!memcmp(expected,xv.pixels,sizeof(expected)));
}
int main(void) {
 check(0,3,4,8,7,4,5);check(0,4,5,8,7,3,4);check(0,3,4,8,7,4,4);
 check(0,-2,-1,8,7,0,0);check(0,1021,510,8,7,10,10);check(0,1,1,8,7,-3,-2);
 check(1,0,0,8,7,4,5);check(1,-2,-1,8,7,4,5);check(1,0,0,8,7,1021,510);
 check(0,INT_MIN,0,8,7,0,0);check(0,INT_MAX,0,8,7,0,0);check(0,0,0,8,7,INT_MIN,0);
 return 0;
}
"""
source=a.out/'vram.c';source.write_text(c);exe=a.out/'vram-test'
subprocess.run(['cc','-std=gnu17',str(source),'-o',str(exe)],check=True);subprocess.run([str(exe.resolve())],check=True)
print('PASS: overlapping VRAM moves, external uploads, clipping both ends, extreme coordinates')
