"""Exercise the actual effect helpers with independent expected field values.

The GTE register/operation fixture is deliberately small; it tests boundaries,
not rendered pixels. Source audit separately rejects BE-only accessor mistakes.
"""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[2]
out = root/'build-360/results/effects-contract'


def function(path, name):
    source = (root/path).read_text()
    start = re.search(r'(?m)^(?:static\s+|inline\s+|__inline\s+)*(?:void|u32|s16|MATRIX\s*\*|struct\s+\w+\s*\*|u32\s*\*)\s*'+name+r'\s*\(', source)
    assert start, name
    opening = source.index('{', start.start())
    depth = 1
    end = opening+1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start.start():end]+'\n'


prelude = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define CTR_NATIVE 1
typedef uint8_t u8; typedef int8_t s8; typedef uint16_t u16; typedef int16_t s16;
typedef uint32_t u32; typedef int32_t s32; typedef int16_t VERTTYPE;
typedef struct {s16 m[3][3],pad; s32 t[3];} MATRIX;
typedef struct {s16 x,y,z;} SVec3;
struct Instance {MATRIX matrix;};
struct ParticleAxis {int startVal; s16 velocity,accel;};
struct Particle {u16 flagsAxis,flagsOscillatorAxis; struct ParticleAxis axis[12];};
struct ParticleOscillator {void *next,*prev;u16 flags;s16 previousValue;u16 period;s16 phase;u16 scale;s16 offset,min,max;};
struct ParticleOscillatorRandomRange {u16 period;s16 phase;u16 scale;s16 offset,min,max;};
struct ParticleOscillatorConfig {u16 flags;s16 previousValue;struct ParticleOscillatorRandomRange range;};
struct ParticleEmitter {struct {struct ParticleOscillatorConfig oscillator;} tail;};
struct ParticleRenderListScratch {u32 viewProjWords[5];s32 depth;};
struct ParticleSpecialLineBody {u32 color0AndCode,xy0,color1,xy1;};
struct ParticleSpecialPacket {u32 tag,drawMode,pad;struct ParticleSpecialLineBody line;};
struct DrawLevelOvr1PScratchVertex {s16 pos[3];u16 flags;u8 color_hi[4];s16 posScreen[2];u16 depth;u8 clipNear,clipHalfNear;};
struct QuadBlock {s8 order[4];};
struct PushBuffer {u32 *ptrOT;};
enum {DRAW_LEVEL_OVR1P_MAX_OT_INDEX=1020};
static struct DrawLevelOvr1PScratchVertex waterFrame[9];
static struct DrawLevelOvr1PScratchVertex *DrawLevelOvr1P_GetScratchVertices(void){return waterFrame;}
static u32 DrawLevelOvr1P_GetProjectedOtSlotWord(const struct DrawLevelOvr1PScratchVertex*p,int face){(void)p;return face*4;}
static s8 DrawLevelOvr1P_ReadRetailQuadBlockByte(const struct QuadBlock*b,u32 off){assert(off>=0x18&&off<0x1c);return b->order[off-0x18];}
struct UIMap {s16 worldEndX,worldEndY,worldStartX,worldStartY,iconSizeX,iconSizeY,iconStartX,iconStartY,mode;};
static struct {int numPlyrCurrGame;} tracker;
static struct {void *unused;struct {int numPlyrCurrGame;} *gGT;} state;
static typeof(state) *sdata=&state;
static s32 regs[32];static u32 controls[32];
#define MFC2(n) ((u32)regs[n])
#define MFC2_S(n) (regs[n])
#define MTC2(v,n) (regs[n]=(s32)(v))
#define CTC2(v,n) (controls[n]=(u32)(v))
static u16 CTR_ReadU16LE(const void*p){const u8*b=p;return b[0]|((u16)b[1]<<8);}
static u32 CTR_ReadU32LE(const void*p){const u8*b=p;return b[0]|((u32)b[1]<<8)|((u32)b[2]<<16)|((u32)b[3]<<24);}
static void CTR_WriteU16LE(void*p,u16 v){u8*b=p;b[0]=(u8)v;b[1]=(u8)(v>>8);}
static void CTR_WriteU32LE(void*p,u32 v){u8*b=p;b[0]=(u8)v;b[1]=(u8)(v>>8);b[2]=(u8)(v>>16);b[3]=(u8)(v>>24);}
static void CTR_GPU_WriteControlWord(u32*p,u32 v){CTR_WriteU32LE(p,v);}
static u32 CTR_PackS16Pair(s16 a,s16 b){return (u16)a|((u32)(u16)b<<16);}
static void SetRotMatrix(MATRIX*m){for(int i=0;i<4;i++)controls[i]=CTR_ReadU32LE((u8*)m+i*4);controls[4]=CTR_ReadU16LE((u8*)m+16);}
static void CTR_GteLoadSVec3V0(const SVec3*v){regs[0]=CTR_PackS16Pair(v->x,v->y);regs[1]=v->z;}
static void gte_compute(int translation){
 s16 r[9],v[3]={(s16)regs[0],(s16)((u32)regs[0]>>16),(s16)regs[1]};
 for(int i=0;i<9;i++)r[i]=(s16)(controls[i/2]>>((i%2)*16));
 for(int row=0;row<3;row++){int val=0;for(int col=0;col<3;col++)val+=r[row*3+col]*v[col];regs[25+row]=(val>>12)+(translation?(s32)controls[5+row]:0);}
}
static void gte_rt(void){gte_compute(1);}
static void gte_rtv0(void){gte_compute(0);}
static void gte_rtpt_b(void){regs[12]=0x009cffbe;regs[13]=0x00b1ffdb;regs[17]=777;}
static s32 Particle_RenderList_MulLo(s32 a,s32 b){return (s32)((uint64_t)(uint32_t)a*b);}
static u32 Particle_RenderList_PackXY(s32 a,s32 b){return (u16)a|((u32)b<<16);}
'''

helpers = ''
for path in ('include/namespace_Particle.h', 'game/Particle.c', 'game/UI/UI_Map.c'):
    helpers += '\n'.join(re.findall(r'enum(?:\s+\w+)?\s*\{.*?\};', (root/path).read_text(), re.S))+'\n'
for name in ('CTR_GteStoreU32', 'CTR_GteStoreMAC', 'CTR_GteSetRuntimeTransMatrix', 'CTR_GteStoreRuntimeMAC'):
    helpers += function('include/ctr_gte.h', name)
for name in ('CtrGpu_WriteColorCode', 'CtrGpu_WriteControlWord', 'CtrGpu_WritePackedXY'):
    helpers += function('include/gpu.h', name)
for path, names in (
    ('game/LHMatrix.c', ('LHMatrix_Parent',)),
    ('game/MATH/MATH_3_HitboxMatrix.c', ('MATH_HitboxMatrix',)),
    ('game/Particle.c', ('Particle_GetAxisFlags','Particle_Init_SetAxisFlags',
                         'ParticleEmitter_CopyOscillator','Particle_RenderList_WriteSpecialPrimitive')),
    ('game/UI/UI_Map.c', ('UI_Map_GetIconPos',)),
    ('game/226/226_00_DrawLevelOvr1P.c', ('DrawLevelOvr1P_GetWaterTopFrameOtDepth',
        'Ovr226_800a2690_ResolveWaterListInheritedOtEntry','Ovr226_800a31f0_ResolveWaterRenderedInheritedOtEntry'))):
    for name in names:
        helpers += function(path, name)

tests = r'''
int main(void){
 struct Particle p={0};struct ParticleEmitter em={0};struct ParticleOscillator osc={0};
 Particle_Init_SetAxisFlags(&p,0x8a2511df);assert(p.flagsAxis==0x11df&&p.flagsOscillatorAxis==0x8a25&&Particle_GetAxisFlags(&p)==0x8a2511df);
 osc.next=(void*)0x1234;osc.prev=(void*)0x5678;
 em.tail.oscillator=(struct ParticleOscillatorConfig){0x102,-273,{511,-1023,4096,-133,12,2301}};
 ParticleEmitter_CopyOscillator(&osc,&em);
 assert(osc.next==(void*)0x1234&&osc.prev==(void*)0x5678&&osc.flags==0x102&&osc.previousValue==-273);
 assert(osc.period==511&&osc.phase==-1023&&osc.scale==4096&&osc.offset==-133&&osc.min==12&&osc.max==2301);
 struct Instance src={0},dst={0};SVec3 local={27,-15,103};
 const s16 rotation[9]={0,0,4096,0,4096,0,-4096,0,0};
 for(int i=0;i<9;i++)CTR_WriteU16LE(&src.matrix.m[i/3][i%3],rotation[i]);
 src.matrix.t[0]=-10673;src.matrix.t[1]=275;src.matrix.t[2]=13467;
 LHMatrix_Parent(&dst,&src,&local);
 assert(memcmp(src.matrix.m,dst.matrix.m,18)==0);
 assert(dst.matrix.t[0]==-10570&&dst.matrix.t[1]==260&&dst.matrix.t[2]==13440);
 MATRIX inverse={0};MATH_HitboxMatrix(&inverse,&src.matrix);
 for(int row=0;row<3;row++)for(int col=0;col<3;col++)assert((s16)CTR_ReadU16LE(&inverse.m[row][col])==rotation[col*3+row]);
 assert((s32)CTR_ReadU32LE(&inverse.t[0])==13467);
 assert((s32)CTR_ReadU32LE(&inverse.t[1])==-275);
 assert((s32)CTR_ReadU32LE(&inverse.t[2])==10673);
 regs[25]=-123456;regs[26]=234567;regs[27]=-345678;s32 numeric[3],packed[3];
 CTR_GteStoreRuntimeMAC(numeric);CTR_GteStoreMAC(packed);
 assert(numeric[0]==-123456&&numeric[1]==234567&&numeric[2]==-345678);
 assert((s32)CTR_ReadU32LE(packed)==-123456);
 struct ParticleSpecialPacket packet={0};struct ParticleRenderListScratch scratch={0};
 p.axis[PARTICLE_AXIS_ICON_FRAME_OR_LINE_COLOR].startVal=0x50a1b2c3;
 Particle_RenderList_WriteSpecialPrimitive(&packet,&p,0,0,0x00543210,&scratch);
 assert(CTR_ReadU32LE(&packet.line.color0AndCode)==0x50543210&&CTR_ReadU32LE(&packet.line.color1)==0x50a1b2c3);
 assert(((s16*)&packet.line.xy0)[0]==-66&&((s16*)&packet.line.xy0)[1]==156);
 assert(((s16*)&packet.line.xy1)[0]==-37&&((s16*)&packet.line.xy1)[1]==177&&scratch.depth==777);
 assert(CTR_ReadU32LE(&packet.drawMode)==PARTICLE_GPU_DRAWMODE_BASE&&packet.pad==0);
 assert(CTR_ReadU32LE(&p.axis[PARTICLE_AXIS_ICON_FRAME_OR_LINE_COLOR].velocity)==0x50543210);
 Particle_RenderList_WriteSpecialPrimitive(&packet,&p,0,PARTICLE_SET_COLOR_FLAG_SPECIAL_LINE_SWAP_COLORS,0x00543210,&scratch);
 assert(CTR_ReadU32LE(&packet.line.color1)==0x50543210&&CTR_ReadU32LE(&packet.line.color0AndCode)==0x50a1b2c3);
 struct UIMap map={4009,9250,-10987,-10560,80,40,475,170,0};int x=-6200,y=-4800;
 state.gGT=(void*)&tracker;tracker.numPlyrCurrGame=1;UI_Map_GetIconPos(&map,&x,&y);
 assert(x==442&&y==135);
 const int iconX[4]={442,494,508,456},iconY[4]={135,121,173,187};
 for(int mode=0;mode<4;mode++){
  map.mode=mode;tracker.numPlyrCurrGame=1;x=-6200;y=-4800;UI_Map_GetIconPos(&map,&x,&y);assert(x==iconX[mode]&&y==iconY[mode]);
  tracker.numPlyrCurrGame=3;x=-6200;y=-4800;UI_Map_GetIconPos(&map,&x,&y);assert(x==iconX[mode]-60&&y==iconY[mode]+10);
 }
 u32 ot[1021]={0},sentinel;struct PushBuffer pb={ot};struct QuadBlock block={{127,0,0,0}};int indices[4]={0,1,2,3};
 for(int i=0;i<4;i++)waterFrame[i].depth=65535;
 assert(Ovr226_800a2690_ResolveWaterListInheritedOtEntry(&pb,&block,waterFrame,indices,0,NULL)==ot+1020);
 assert(Ovr226_800a31f0_ResolveWaterRenderedInheritedOtEntry(&pb,&block,waterFrame,indices,0,NULL)==ot+1020);
 block.order[0]=-128;for(int i=0;i<4;i++)waterFrame[i].depth=0;
 assert(Ovr226_800a2690_ResolveWaterListInheritedOtEntry(&pb,&block,waterFrame,indices,0,NULL)==ot);
 assert(Ovr226_800a31f0_ResolveWaterRenderedInheritedOtEntry(&pb,&block,waterFrame,indices,0,NULL)==ot);
 assert(Ovr226_800a2690_ResolveWaterListInheritedOtEntry(&pb,&block,waterFrame,indices,0,&sentinel)==&sentinel);
 assert(Ovr226_800a2690_ResolveWaterListInheritedOtEntry(&pb,&block,waterFrame+1,indices,0,NULL)==NULL);
 assert(Ovr226_800a31f0_ResolveWaterRenderedInheritedOtEntry(&pb,&block,waterFrame+1,indices,0,NULL)==NULL);
 waterFrame[0].depth=100;waterFrame[1].depth=90;waterFrame[2].depth=120;waterFrame[3].depth=110;
 assert(DrawLevelOvr1P_GetWaterTopFrameOtDepth(waterFrame,indices)==110);
 puts("PASS actual effect helpers: particle flags/oscillator payload, parent world transform, hitbox LE transpose/packed inverse, native versus projection MAC, streak RGBC/XY, Crash Cove minimap, bounded far/negative water OT links");
 return 0;
}
'''
out.with_suffix('.c').write_text(prelude+helpers+tests, encoding='utf-8')
subprocess.run(['clang','-O2',str(out.with_suffix('.c')),'-o',str(out.with_suffix('.exe'))],check=True)
run = subprocess.run([str(out.with_suffix('.exe'))], capture_output=True, text=True)
out.with_suffix('.log').write_text(run.stdout+run.stderr, encoding='utf-8')
print(run.stdout+run.stderr, end='')
if run.returncode:
    raise SystemExit(run.returncode)
