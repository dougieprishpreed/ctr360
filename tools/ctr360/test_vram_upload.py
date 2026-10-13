"""Execute Xbox dirty ownership/upload logic with a linear tile/lock fixture.

The test proves which pixels the code uploads and retry ownership. It cannot
validate Xenos tiling, synchronization or console GPU cache behavior.
"""
from pathlib import Path
import re
import subprocess
root=Path(__file__).resolve().parents[2]
source=(root/'platform/xbox360/native_xbox360_video.c').read_text()
out=root/'build-360/results/vram-upload-contract'
out.mkdir(parents=True,exist_ok=True)

def function(name):
    m=re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{',source,re.M);assert m,name
    start=source.index('{',m.start());end=start+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[m.start():end]+'\n'

c=r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;
typedef uint32_t u32;typedef int32_t s32;typedef int64_t s64;typedef int b32;
typedef int HRESULT;typedef int TextureID;
typedef struct {s16 x,y,w,h;} RECT16;
typedef struct {int left,top,right,bottom;} RECT;
typedef struct {int x,y;} POINT;
typedef struct {void*pBits;int Pitch;} D3DLOCKED_RECT;
#define internal static
#define VRAM_WIDTH 64
#define VRAM_HEIGHT 16
#define NATIVE_VRAM_DIRTY_RECT_CAP 128
#define NATIVE_VRAM_TILE_SIZE 4
#define NATIVE_VRAM_TILE_COLS (VRAM_WIDTH/NATIVE_VRAM_TILE_SIZE)
#define FAILED(hr) ((hr)<0)
#define SUCCEEDED(hr) ((hr)>=0)
#define E_FAIL (-1)
#define D3DLOCK_READONLY 1
#define NATIVE_RENDERER_ERROR(...) ((void)0)
#define Platform_Log(...) ((void)0)
#define Platform_LogError(...) ((void)0)
static u32 gpu[VRAM_WIDTH*VRAM_HEIGHT],s_vramLinearScratch[VRAM_WIDTH*VRAM_HEIGHT];
static int lockFail,unlockFail,uploads,lockCalls,failLockAt;
static TextureID s_lastBoundTexture;
static struct {u16 cpuPixels[VRAM_WIDTH*VRAM_HEIGHT];void*texture;
 RECT16 cpuDirtyRects[NATIVE_VRAM_DIRTY_RECT_CAP];s32 cpuDirtyRectCount;
 b32 cpuDirtyOverflow;u32 cpuDirtyPixels[VRAM_WIDTH*VRAM_HEIGHT/32];u32 gpuNewerTiles[2];} s_vram;
static HRESULT IDirect3DTexture9_LockRect(void*t,int level,D3DLOCKED_RECT*out,void*r,int flags){
 lockCalls++;if(lockFail||lockCalls==failLockAt)return -1;out->pBits=gpu;return 0;
}
static HRESULT IDirect3DTexture9_UnlockRect(void*t,int level){return unlockFail?-1:0;}
static void XGTileSurface(void*t,int width,int height,const POINT*point,const u32*src,int pitch,const RECT*r,int bpp){
 assert(point->x==r->left&&point->y==r->top && width==VRAM_WIDTH && height==VRAM_HEIGHT && bpp==4);
 uploads++;
 for(int y=r->top;y<r->bottom;y++)for(int x=r->left;x<r->right;x++)((u32*)t)[y*width+x]=src[y*width+x];
}
static void XGUntileSurface(u32*dst,int pitch,const void*point,const void*src,int width,int height,const RECT*r,int bpp){
 assert(pitch==width*4&&bpp==4);memcpy(dst,src,width*height*4);
}
'''
for name in ('NativeRenderer_ClipVRAMRect','NativeRenderer_DirtyRectContains',
             'NativeRenderer_MarkCpuDirtyPixels','NativeRenderer_AppendCpuDirtyRect',
             'NativeRenderer_MarkVRAMDirty','NativeRenderer_MarkGpuVRAMNewer','NativeRenderer_UploadCpuRect','NativeRenderer_UpdateVRAM',
             'NativeRenderer_SyncGpuVRAMToCPU','NativeRenderer_ResolveVRAMRead','NativeRenderer_CopyVRAM','NativeRenderer_ReadVRAM','NativeRenderer_ClearVRAM'):
    c+=function(name)
c+=r'''
static u32 pixel(u16 v){return 0xff000000u|((u32)(v&255)<<16)|((u32)(v>>8)<<8);}
static void reset(void){memset(&s_vram,0,sizeof s_vram);s_vram.texture=(void*)1;for(int i=0;i<VRAM_WIDTH*VRAM_HEIGHT;i++)gpu[i]=0xff123456;uploads=lockFail=unlockFail=lockCalls=failLockAt=0;}
int main(void){
 reset();s_vram.cpuPixels[1]=0x4321;s_vram.cpuPixels[11]=0xabcd;
 NativeRenderer_MarkVRAMDirty(1,0,1,1);NativeRenderer_MarkVRAMDirty(11,0,1,1);
 NativeRenderer_UpdateVRAM();assert(uploads==2 && gpu[1]==pixel(0x4321)&&gpu[11]==pixel(0xabcd));
 for(int i=2;i<11;i++)assert(gpu[i]==0xff123456);
 assert(!s_vram.cpuDirtyRectCount && !s_vram.cpuDirtyOverflow);
 /* Overlap/containment is safe because every covered pixel was written. */
 reset();for(int x=3;x<8;x++)s_vram.cpuPixels[x]=x;
 NativeRenderer_MarkVRAMDirty(3,0,2,1);NativeRenderer_MarkVRAMDirty(3,0,5,1);
 assert(s_vram.cpuDirtyRectCount==1);NativeRenderer_UpdateVRAM();assert(uploads==1 && gpu[2]==0xff123456&&gpu[8]==0xff123456);
 /* Overflow must retain all true writes and every intervening GPU pixel. */
 reset();for(int i=0;i<150;i++){int x=(i%32)*2,y=i/32;s_vram.cpuPixels[y*64+x]=(u16)(i+1);NativeRenderer_MarkVRAMDirty(x,y,1,1);}
 assert(s_vram.cpuDirtyOverflow && s_vram.cpuDirtyRectCount==128);
 lockFail=1;NativeRenderer_UpdateVRAM();assert(s_vram.cpuDirtyOverflow && uploads==0);
 lockFail=0;unlockFail=1;NativeRenderer_UpdateVRAM();assert(s_vram.cpuDirtyOverflow);
 unlockFail=0;NativeRenderer_UpdateVRAM();assert(!s_vram.cpuDirtyOverflow && !s_vram.cpuDirtyRectCount);
 for(int i=0;i<150;i++){int at=(i/32)*64+(i%32)*2;assert(gpu[at]==pixel((u16)(i+1))&&gpu[at+1]==0xff123456);}
 for(int i=0;i<VRAM_WIDTH*VRAM_HEIGHT/32;i++)assert(s_vram.cpuDirtyPixels[i]==0);
 /* Missing texture preserves writes too. */
 reset();NativeRenderer_MarkVRAMDirty(1,1,1,1);s_vram.texture=NULL;NativeRenderer_UpdateVRAM();assert(s_vram.cpuDirtyRectCount==1);
 s_vram.texture=(void*)1;NativeRenderer_UpdateVRAM();assert(!s_vram.cpuDirtyRectCount);
 /* Failed upload must prevent a subsequent readback overwriting CPU dirt. */
 reset();s_vram.cpuPixels[1]=0x4567;NativeRenderer_MarkVRAMDirty(1,0,1,1);NativeRenderer_MarkGpuVRAMNewer(0,0,4,4);
 failLockAt=1;assert(!NativeRenderer_SyncGpuVRAMToCPU(0,0,4,4));
 assert(lockCalls==1&&s_vram.cpuPixels[1]==0x4567&&s_vram.cpuDirtyRectCount==1&&s_vram.gpuNewerTiles[0]==1);
 failLockAt=0;assert(NativeRenderer_SyncGpuVRAMToCPU(0,0,4,4));
 assert(s_vram.cpuPixels[1]==0x4567&&gpu[1]==pixel(0x4567)&&s_vram.cpuPixels[2]==0x3412&&!s_vram.gpuNewerTiles[0]);
 /* Failed read lock/unlock must preserve shadow and GPU ownership for retry. */
 reset();s_vram.cpuPixels[0]=0xbeef;NativeRenderer_MarkGpuVRAMNewer(0,0,4,4);lockFail=1;
 assert(!NativeRenderer_SyncGpuVRAMToCPU(0,0,4,4)&&s_vram.cpuPixels[0]==0xbeef&&s_vram.gpuNewerTiles[0]==1);
 lockFail=0;unlockFail=1;assert(!NativeRenderer_SyncGpuVRAMToCPU(0,0,4,4)&&s_vram.cpuPixels[0]==0xbeef&&s_vram.gpuNewerTiles[0]==1);
 unlockFail=0;assert(NativeRenderer_SyncGpuVRAMToCPU(0,0,4,4)&&s_vram.cpuPixels[0]==0x3412&&!s_vram.gpuNewerTiles[0]);
 reset();NativeRenderer_MarkGpuVRAMNewer(0,0,4,4);s_vram.cpuPixels[4]=0xcafe;lockFail=1;
 NativeRenderer_CopyVRAM(NULL,0,0,4,1,4,0);assert(s_vram.cpuPixels[4]==0xcafe&&!s_vram.cpuDirtyRectCount);
 u16 read[16];for(int i=0;i<16;i++)read[i]=0xaaaa;
 NativeRenderer_ReadVRAM(read,0,0,4,4);for(int i=0;i<16;i++)assert(read[i]==0xaaaa);
 lockFail=0;NativeRenderer_ReadVRAM(read,0,0,4,4);for(int i=0;i<16;i++)assert(read[i]==0x3412);
 NativeRenderer_ReadVRAM(NULL,0,0,4,4);
 NativeRenderer_ReadVRAM(read,-1,0,4,4);NativeRenderer_ReadVRAM(read,0,-1,4,4);
 NativeRenderer_ReadVRAM(read,63,0,4,4);NativeRenderer_ReadVRAM(read,0,15,4,4);
 NativeRenderer_ReadVRAM(read,0,0,0x7fffffff,4);for(int i=0;i<16;i++)assert(read[i]==0x3412);
 /* Actual MoveImage overlap preserves the original image in both axes. */
 reset();u16 before[VRAM_WIDTH*VRAM_HEIGHT];
 for(int i=0;i<VRAM_WIDTH*VRAM_HEIGHT;i++)s_vram.cpuPixels[i]=(u16)i;
 memcpy(before,s_vram.cpuPixels,sizeof before);
 NativeRenderer_CopyVRAM(NULL,1,1,12,8,3,3);
 for(int y=0;y<8;y++)for(int x=0;x<12;x++)assert(s_vram.cpuPixels[(y+3)*64+x+3]==before[(y+1)*64+x+1]);
 NativeRenderer_ClearVRAM(-2,-3,4,5,255,0,0);assert(s_vram.cpuPixels[0]==31&&s_vram.cpuPixels[65]==31);
 NativeRenderer_ClearVRAM(0x7fffffff,0,0x7fffffff,1,255,0,0);
 NativeRenderer_CopyVRAM(NULL,-2147483647,0,32,32,0,0);
 u16 host[12];for(int i=0;i<12;i++)host[i]=500+i;
 NativeRenderer_CopyVRAM(host,0,0,4,3,-1,-1);
 assert(s_vram.cpuPixels[0]==host[5]&&s_vram.cpuPixels[2]==host[7]&&s_vram.cpuPixels[64]==host[9]);
 puts("PASS actual Xbox upload/readback logic: separated/overlapping writes preserve GPU holes, 150-rect overflow retains exact pixels, failed lock/unlock/missing texture retries preserve dirt/shadow/ownership, copy defers failed source sync; clipped clear/copy and overlapping MoveImage");
}
'''
(out/'fixture.c').write_text(c)
subprocess.run(['clang','-O2',str(out/'fixture.c'),'-o',str(out/'fixture.exe')],check=True)
subprocess.run([str(out/'fixture.exe')],check=True)
