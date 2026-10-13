"""Execute audited effect writers with GTE/OT fixtures and guarded real packets.

Checks native field values and actual allocation/iteration paths, not rendered
pixels or PPC execution. Every source function comes from the current engine.
"""
from pathlib import Path
import subprocess
import re
root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/audit-effect-bounds'
out.mkdir(parents=True, exist_ok=True)

def function(path, name):
    s = (root/path).read_text()
    m = re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{', s, re.M)
    assert m, name
    start=s.index('{', m.start()); end=start+1; depth=1
    while depth:
        depth+=(s[end]=='{')-(s[end]=='}');end+=1
    return s[m.start():end]+'\n'

prelude=r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define CTR_NATIVE 1
#define CTR_STATIC_ASSERT(x)
#define CTR_OFFSET_OF_ARRAY(t,m,i) (offsetof(t,m)+sizeof(((t*)0)->m[0])*(i))
typedef uint8_t u8;typedef int8_t s8;typedef uint16_t u16;typedef int16_t s16;
typedef uint32_t u32;typedef int32_t s32;typedef int64_t s64;typedef s16 VERTTYPE;
typedef struct {s16 x,y,z;} SVec3;
typedef struct {s16 m[3][3],pad;s32 t[3];} MATRIX;
typedef struct {u32 tag;u8 r0,g0,b0,code;s16 x0,y0;u8 u0,v0;u16 clut;
 s16 x1,y1;u8 u1,v1;u16 tpage;s16 x2,y2;u8 u2,v2;u16 pad2;} POLY_FT3;
typedef struct {u32 tag;u8 r0,g0,b0,code;s16 x0,y0;u8 u0,v0;u16 clut;
 s16 x1,y1;u8 u1,v1;u16 tpage;s16 x2,y2;u8 u2,v2;u16 pad2;s16 x3,y3;u8 u3,v3;u16 pad3;} POLY_FT4;
typedef struct {u32 tag;u8 r0,g0,b0,code;s16 x0,y0;u8 r1,g1,b1,pad;s16 x1,y1;} LINE_G2;
typedef struct {u32 tag;u8 r0,g0,b0,code;s16 x0,y0;} TILE_1;
struct CtrGpuDrawModePacket {u32 tag,drawMode,terminator;};
struct PushBuffer {SVec3 pos,rot;MATRIX matrix_ViewProj;struct {s16 x,y,w,h;} rect;u32 *ptrOT;int distanceToScreen_PREV;};
struct PrimMem {void *cursor,*guardEnd;};
struct RainBuffer {s32 numParticles_curr;u16 numParticles_max,vanishRate;u8 opaque[16];SVec3 cameraPos;u16 pad;u32 colorRGBA_top,colorRGBA_bottom,fillMode,offsetOT;};
struct Particle {struct Particle *next;u8 storage[128];};
struct InstDraw {u8 pad[0x50];s8 offset;u8 rest[0x3b];s16 x,padX,y,padY,z;};
struct RainLocal {struct RainLocal*next;void*cloudInst;SVec3 scroll,vel;int frameCount;};
struct JitPool {struct {void*first;} taken;};
struct InstDrawPerPlayer {u8 bytes[0x48];};
#define InstDrawPerPlayer InstDrawPerPlayer
struct Stars {u16 numStars,spread,seed,distance;};
struct TrigPair {s16 sin,cos;};
static struct {u32 trigApprox[1024];} data;
#define ANG_MODULO_HALF_PI(x) ((x)&1023)
#define IS_ANG_FIRST_OR_THIRD_QUADRANT(x) (((x)&1024)==0)
#define IS_ANG_THIRD_OR_FOURTH_QUADRANT(x) (((x)&2048)!=0)
static u32 CTR_TrigApproxWord(const u32*p){return *p;}
static volatile u32 gteRegs[32],controls[32];static u8 *fixtureScratch;
#define CTR_SCRATCHPAD_PTR(t,n) ((t*)((u8*)fixtureScratch+(n)))
#define MFC2(n) (gteRegs[n])
#define CFC2(n) (controls[n])
#define MTC2(v,n) (gteRegs[n]=(u32)(v))
#define CTC2(v,n) (controls[n]=(u32)(v))
static u16 CTR_ReadU16LE(const void*p){const u8*b=p;return b[0]|((u16)b[1]<<8);}
static u32 CTR_ReadU32LE(const void*p){const u8*b=p;return b[0]|((u32)b[1]<<8)|((u32)b[2]<<16)|((u32)b[3]<<24);}
static void CTR_WriteU32LE(void*p,u32 v){u8*b=p;for(int i=0;i<4;i++)b[i]=(u8)(v>>(i*8));}
static u32 CTR_PackS16Pair(s16 x,s16 y){return (u16)x|((u32)(u16)y<<16);}
static void CTR_GPU_WriteControlWord(u32*p,u32 v){CTR_WriteU32LE(p,v);}
static void gte_llv0bk_b(void){gteRegs[25]=100;gteRegs[26]=70;gteRegs[27]=512;}
static void gte_rtps_b(void){gteRegs[14]=0x00460064;controls[31]=0;}
static void gte_rtpt_b(void){
 if(controls[2]==0x0a00){gteRegs[12]=10;gteRegs[13]=10<<16;gteRegs[14]=7|(7<<16);}
 else {gteRegs[12]=80|(50<<16);gteRegs[13]=90|(60<<16);gteRegs[14]=100|(70<<16);}
 controls[31]=0;
}
static u8 *allocationBegin,*allocationEnd;static int links;
static void CtrGpu_LinkPacket24(u32*ot,u32*tag,const void*packet,u32 command){
 assert((const u8*)packet>=allocationBegin && (const u8*)packet+4+(command>>24)*4<=allocationEnd);
 *tag=command;*ot=123;links++;
}
'''
helpers=''.join(function('include/gpu.h',n) for n in ('CtrGpu_PrimFits','CtrGpu_WriteColorCode','CtrGpu_WritePackedXY','CtrGpu_WritePackedUVWord','CtrGpu_WriteControlWord'))
sources=''
for path in ('game/Torch.c','game/RenderWeather/RenderWeather.c','game/RenderWeather/RedBeaker_RenderRain.c','game/RenderStars.c'):
    s=(root/path).read_text().replace('#include <common.h>','')
    # Assertions involving PSX pointer layout belong to the real AST/XDK build.
    s=re.sub(r'(?m)^CTR_STATIC_ASSERT.*?;\s*$', '', s)
    sources+=s+'\n'
tests=r'''
static u8 *arena;
static void reserve(struct PrimMem*pm,int size){
 memset(arena,0xa5,2048);allocationBegin=arena+16;allocationEnd=allocationBegin+size;
 pm->cursor=allocationBegin;pm->guardEnd=allocationEnd;links=0;
}
static void canary(struct PrimMem*pm){
 assert((u8*)pm->cursor<=allocationEnd);
 for(int i=0;i<16;i++)assert(arena[i]==0xa5);
 for(u8*p=allocationEnd;p<arena+2048;p++)if(*p!=0xa5){fprintf(stderr,"canary size=%td cursor=%td links=%d at=%td byte=%x\n",allocationEnd-allocationBegin,(u8*)pm->cursor-allocationBegin,links,p-allocationBegin,*p);abort();}
}
int main(void){
 fixtureScratch=calloc(1,4096);arena=malloc(2048);assert(fixtureScratch&&arena);
 struct PushBuffer pb={0};struct PrimMem pm;u32 ot[1024]={0};struct TorchScratch*ts=Torch_Scratch();
 pb.ptrOT=ot;pb.rect.w=512;pb.rect.h=216;pb.distanceToScreen_PREV=450;
 for(int i=0;i<3;i++) CTR_WriteU32LE((u8*)&pb.matrix_ViewProj+i*8,0x1000);
 ts->uv0.u=17;ts->uv0.v=91;ts->uv0.clut=0x1234;
 ts->uv1.u=38;ts->uv1.v=145;ts->uv1.tpage=0x02ab;
 ts->uv23.u0=9;ts->uv23.v0=102;ts->uv23.u1=178;ts->uv23.v1=211;
 assert(Torch_Uv0Word(ts)==0x12345b11 && Torch_Uv1Word(ts)==0x02ab9126 && Torch_Uv23Word(ts)==0xd3b26609);
 struct Particle particle={0};s32 axis=0x006312ab;memcpy((u8*)&particle+0x3c,&axis,4);
 assert(Torch_ReadU8(&particle,0x3d)==18);
 for(int off=0x3c;off<=0x6c;off+=8){s32 value=12<<8;memcpy((u8*)&particle+off,&value,4);}
 reserve(&pm,575);Torch_Main(&particle,&pb,&pm,1,0);assert(pm.cursor==allocationBegin && links==0);canary(&pm);
 reserve(&pm,576);Torch_Main(&particle,&pb,&pm,1,0);assert((u8*)pm.cursor==allocationBegin+576 && links==16);canary(&pm);
 struct RainBuffer rain={0},before;rain.numParticles_curr=1000;rain.numParticles_max=1000;
 rain.fillMode=0xe1000a20;rain.colorRGBA_top=0x123456;rain.colorRGBA_bottom=0x987654;
 before=rain;reserve(&pm,31);RenderWeather(&pb,&pm,&rain,1,1);assert((u8*)pm.cursor==allocationBegin+12 && links==1);canary(&pm);
 assert(memcmp(&rain,&before,sizeof rain)==0);
 reserve(&pm,32);RenderWeather(&pb,&pm,&rain,1,1);assert((u8*)pm.cursor==allocationBegin+32 && links==2);canary(&pm);
 reserve(&pm,11);RenderWeather(&pb,&pm,&rain,1,1);assert(pm.cursor==allocationBegin && links==0);canary(&pm);
 rain.numParticles_curr=-1;reserve(&pm,32);RenderWeather(&pb,&pm,&rain,1,1);assert(links==1);canary(&pm);
 pb.pos=(SVec3){123,-42,333};rain.numParticles_curr=0;
 CTR_WriteU32LE((u8*)&rain+8,0x00120034);CTR_WriteU32LE((u8*)&rain+16,0x00020003);
 reserve(&pm,32);RenderWeather(&pb,&pm,&rain,1,0);
 assert(CTR_ReadU32LE((u8*)&rain+8)==0x00140037 && rain.cameraPos.x==123 && rain.cameraPos.y==-42 && rain.cameraPos.z==333);canary(&pm);
 reserve(&pm,31);u32*cursor=pm.cursor;RedBeaker_RenderPass(&cursor,ot,0x123456,0xe1000a20,1000,0,0,0,0,0,0,0x00d80200,pm.guardEnd);
 pm.cursor=cursor;assert(links==1 && (u8*)cursor==allocationBegin+12);canary(&pm);
 reserve(&pm,32);cursor=pm.cursor;RedBeaker_RenderPass(&cursor,ot,0x123456,0xe1000a20,1000,0,0,0,0,0,0,0x00d80200,pm.guardEnd);
 pm.cursor=cursor;assert(links==2 && (u8*)cursor==allocationBegin+32);canary(&pm);
 reserve(&pm,11);cursor=pm.cursor;RedBeaker_RenderPass(&cursor,ot,0,0,1000,0,0,0,0,0,0,0x00d80200,pm.guardEnd);
 assert(cursor==pm.cursor && links==0);canary(&pm);
 struct Stars stars={2000,0,0,0};reserve(&pm,23);RenderStars(&pb,&pm,&stars,1);assert(links==1);canary(&pm);
 reserve(&pm,24);RenderStars(&pb,&pm,&stars,1);assert(links==2 && (u8*)pm.cursor==allocationBegin+24);canary(&pm);
 assert(CtrGpu_PrimFits(allocationEnd,allocationEnd,0) && !CtrGpu_PrimFits(allocationEnd,allocationEnd,1));
 puts("PASS actual Torch/rain/cloud/star writers: complete reserves, 1-byte-short/exact-fit canaries, numeric UV/axis fields, LE weather state, native camera history, paused draw invariance and negative counts");
}
'''
path=out/'fixture.c'; path.write_text(prelude+helpers+sources+tests)
# Match XDK/MSVC alias semantics for legacy scratchpad/packet overlays.
subprocess.run(['clang','-O2','-fno-strict-aliasing','-Wno-pointer-to-int-cast',str(path),'-o',str(out/'fixture.exe')],check=True)
subprocess.run([str(out/'fixture.exe')],check=True)

