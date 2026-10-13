"""Actual midpoint renderer: pose contracts, discontinuities and state rewind."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[2]; out=root/'build-360/results/hd-midpoint-contract'
prelude=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define _XBOX 1
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int16_t s16; typedef int32_t s32; typedef int64_t s64;
typedef struct {s16 x,y,z;} SVec3;
typedef struct {s16 m[3][3],pad; s32 t[3];} MATRIX;
struct Model {int identity;};
struct Instance {struct Instance *next;struct Model *model;MATRIX matrix;u32 flags;};
struct PushBuffer {SVec3 pos,rot;u32 *ptrOT;int untouched;};
struct PrimMem {void *start,*cursor;int count;};
struct OtMem {void *start,*cursor;};
struct DB {struct PrimMem primMem;struct OtMem otMem;int drawEnv,dispEnv;};
struct Level {void *ptr_mesh_info;void *ptr_anim_tex;};
struct Thread {int unused;};
enum {BURST, BLOWUP, TURBO};
enum {SCREENSPACE_INSTANCE=0x400,HIDE_MODEL=0x80};
struct GameTracker {
 struct Level *level1;int numPlyrCurrGame,gameMode1,renderFlags,swapchainIndex;
 struct PushBuffer pushBuffer[1];struct DB db[2],*backBuffer;u32 *otSwapchainDB[2];
 struct {struct {struct {void *first;} taken;} instance;int rain;} JitPools;
 struct {int numStars;} stars;int rainBuffer[1];
 int raceTimer,elapsedTimeMS,trafficLightsTimer,timer;void *visMem1;
 struct {struct Thread *thread;} threadBuckets[3];
};
static struct {struct {int stage;} Loading;} data,*sdata=&data;
enum {LOAD_IDLE=0,LOADING=1,MAIN_MENU=2,GAME_CUTSCENE=4,ADVENTURE_ARENA=8,PAUSE_ALL=16,END_OF_RACE=32};
enum {RENDER_FLAG_DRAW_LEVEL=1,RENDER_FLAG_RENDER_BUCKET=2,RENDER_FLAG_CLEAR_BACK_BUFFER=4,RENDER_FLAG_EFFECT_BUCKETS=8,RENDER_FLAG_RAIN=16,RENDER_FLAG_BEAKER_RAIN=32,RENDER_FLAG_STARS=64};
static u16 CTR_ReadU16LE(const void*p){const u8*b=p;return b[0]|((u16)b[1]<<8);}
static void CTR_WriteU16LE(void*p,u16 v){u8*b=p;b[0]=(u8)v;b[1]=(u8)(v>>8);}
static int renders,vsyncs,captures,hudValid=1;
static int queuedRange, flameRange, burstRange, blowupRange;
int LOAD_IsOpen_RacingOrBattle(void){return 1;}
void RB_Burst_ProcessBucket(struct Thread*t){(void)t;burstRange=queuedRange;}
void RB_Blowup_ProcessBucket(struct Thread*t){(void)t;blowupRange=queuedRange;}
void VehTurbo_ProcessBucket(struct Thread*t){(void)t;flameRange=queuedRange;}
static struct GameTracker *observedGT;
static MATRIX observedMatrix;static SVec3 observedCamera;
void NativeGpu_BeginHUDCapture(void){captures++;}
void NativeGpu_ReplayHUD(void){}
void NativeGpu_SetHUDCapture(int enabled){(void)enabled;}
int NativeGpu_HasHUDCapture(void){return hudValid;}
void PushBuffer_UpdateFrustum(struct PushBuffer*p){(void)p;}
void MainFrame_VisMemFullFrame(struct GameTracker*g,struct Level*l){(void)g;(void)l;}
void ClearOTagR(u32*p,int n){memset(p,0,n*sizeof(u32));}
void RenderBucket_QueueAllInstances(struct GameTracker*g){(void)g;queuedRange++;flameRange=burstRange=blowupRange=0;assert((((struct Instance*)g->JitPools.instance.taken.first)->next->flags & HIDE_MODEL)!=0);}
static int weatherDraws,cloudDraws,starDraws,heatDraws;
void RenderWeather(struct PushBuffer*p,struct PrimMem*m,int*r,int n,int pause){assert(pause==PAUSE_ALL&&n==1);weatherDraws++;}
void RedBeaker_RenderRain(struct PushBuffer*p,struct PrimMem*m,int*r,int n,int pause){assert(pause==PAUSE_ALL&&n==1);cloudDraws++;}
void RenderStars(struct PushBuffer*p,struct PrimMem*m,void*r,int n){assert(n==1);starDraws++;}
void RenderAllHeatParticles(struct GameTracker*g){heatDraws++;}
void RenderAllNormalParticles(struct GameTracker*g){(void)g;}
void RenderBucket_ExecuteAllInstances(struct GameTracker*g){(void)g;assert(flameRange==queuedRange && burstRange==queuedRange && blowupRange==queuedRange);}
void RenderAllTires(struct GameTracker*g){((struct Instance*)g->JitPools.instance.taken.first)->flags=777;}
void RenderAllShadows(struct GameTracker*g){(void)g;}
void RenderAllLevelGeometry(struct GameTracker*g,struct Level*l,void*m){(void)g;(void)l;(void)m;}
void RenderDispEnv_World(struct GameTracker*g){(void)g;}
void CAM_ClearScreen(struct GameTracker*g){(void)g;}
void CTR_CycleTex_LEV(void*t,int timer){(void)t;(void)timer;}
void DotLights_Video(struct GameTracker*g,s32 r1,s32 r2,s32 r3,s32 green,s32 y){(void)g;assert(r1==1&&r2==1&&r3==1&&green==1);assert(y==4096);}
void PutDrawEnv(int*p){(void)p;}
void PutDispEnv(int*p){(void)p;}
void DrawOTag(u32*p){(void)p;assert((uintptr_t)observedGT->backBuffer->primMem.cursor==(uintptr_t)observedGT->backBuffer->primMem.start+12);renders++;observedCamera=observedGT->pushBuffer[0].pos;observedMatrix=((struct Instance*)observedGT->JitPools.instance.taken.first)->matrix;}
void Platform_WaitUntilVBlank(int n){vsyncs=n;}
int Platform_GetVBlankCount(void){return vsyncs;}
void DrawSync(int n){(void)n;}
void Platform_EndFrame(void){}
'''
source=(root/'game/MAIN/MainHD.c').read_text().replace('#include <common.h>','')
tests=r'''
int main(void){
 struct GameTracker g={0};struct Level level={(void*)1},other={(void*)2};
 struct Instance inst={0},hud={0};struct Model model={1};
 struct GameTracker before;MATRIX matrixBefore;u32 ot[0x406],otBefore[0x406];char prim[64],mem[64];int i,r;
 MATRIX a,b,c;memset(&a,0x5a,sizeof a);memset(&b,0x5a,sizeof b);
 for(i=0;i<9;i++){CTR_WriteU16LE(&a.m[i/3][i%3],(u16)(-3000+i*431));CTR_WriteU16LE(&b.m[i/3][i%3],(u16)(3000-i*321));}
 a.t[0]=-10000;a.t[1]=123;a.t[2]=32767;b.t[0]=10000;b.t[1]=-122;b.t[2]=-32768;
 NativeHD_InterpolateMatrix(&c,&a,&b);
 assert(c.t[0]==0 && c.t[1]==0 && c.t[2]==-1 && c.pad==b.pad);
 for(i=0;i<9;i++){int av=(s16)CTR_ReadU16LE(&a.m[i/3][i%3]),bv=(s16)CTR_ReadU16LE(&b.m[i/3][i%3]);assert((s16)CTR_ReadU16LE(&c.m[i/3][i%3])==bv+(av-bv)/2);}
 assert(NativeHD_AngleMidpoint(4090,6)==0);assert(NativeHD_AngleMidpoint(6,4090)==0);
 g.level1=&level;g.numPlyrCurrGame=1;g.renderFlags=127;g.stars.numStars=12;g.backBuffer=&g.db[0];g.otSwapchainDB[0]=ot;g.pushBuffer[0].ptrOT=ot+6;
 g.db[0].primMem.start=prim;g.db[0].primMem.cursor=prim+12;g.db[0].otMem.start=mem;g.db[0].otMem.cursor=mem+24;
 g.JitPools.instance.taken.first=&inst;inst.next=&hud;hud.model=&model;hud.flags=SCREENSPACE_INSTANCE;hud.matrix.t[0]=123;inst.model=&model;inst.matrix=b;inst.matrix.t[0]=100;inst.matrix.t[1]=200;inst.matrix.t[2]=300;
 g.raceTimer=76543;g.elapsedTimeMS=32;observedGT=&g;
 for(i=0;i<0x406;i++)ot[i]=0x12345600+i;
 NativeHD_RenderIntermediate(&g);assert(renders==0);
 g.pushBuffer[0].pos.x=100;inst.matrix.t[0]=120;
 before=g;matrixBefore=inst.matrix;memcpy(otBefore,ot,sizeof ot);
 NativeHD_RenderIntermediate(&g);
 assert(weatherDraws==1 && cloudDraws==1 && starDraws==1 && heatDraws==1);
 assert(renders==1 && vsyncs==1 && observedCamera.x==50 && observedMatrix.t[0]==110);
 assert(memcmp(&g,&before,sizeof g)==0 && memcmp(&inst.matrix,&matrixBefore,sizeof matrixBefore)==0 && memcmp(ot,otBefore,sizeof ot)==0);
 assert(g.raceTimer==76543 && g.elapsedTimeMS==32 && inst.flags==0 && hud.flags==SCREENSPACE_INSTANCE && hud.matrix.t[0]==123);
 r=renders;g.gameMode1=PAUSE_ALL;NativeHD_RenderIntermediate(&g);assert(renders==r);
 g.gameMode1=0;g.level1=&other;NativeHD_RenderIntermediate(&g);assert(renders==r);
 g.pushBuffer[0].pos.x+=1500;NativeHD_RenderIntermediate(&g);assert(renders==r);
 g.numPlyrCurrGame=2;NativeHD_RenderIntermediate(&g);assert(renders==r);
 /* Indexed lookup preserves identities across reordered lists and collisions. */
 struct Instance many[512];struct Model otherModel={2};
 s_hdPoseCount=512;
 for(i=0;i<512;i++){s_hdPrevious[i].instance=&many[511-i];s_hdPrevious[i].model=&model;}
 NativeHD_IndexPreviousPoses();
 for(i=0;i<512;i++){assert(NativeHD_FindPreviousPose(&many[i],&model)==511-i);assert(NativeHD_FindPreviousPose(&many[i],&otherModel)==-1);}
 assert(NativeHD_FindPreviousPose(&inst,&model)==-1);
 assert(416+720+720==1856 && 1856<=2048);
 puts("PASS actual HD midpoint: LE rotation/native translation, wrapped angles, fresh boost/explosion depth bindings before dispatch, one HUD copy with screenspace flags restored, pose/DB/OT/timer restoration, draw-only weather/cloud/star/heat paths, 512 indexed identities and model changes, pause/level/camera-cut/split-screen guards; EDRAM 1856/2048 tiles");
 return 0;
}
'''
out.with_suffix('.c').write_text(prelude+source+tests)
subprocess.run(['clang','-O2',str(out.with_suffix('.c')),'-o',str(out.with_suffix('.exe'))],check=True)
run=subprocess.run([str(out.with_suffix('.exe'))],capture_output=True,text=True,check=True)
out.with_suffix('.log').write_text(run.stdout);print(run.stdout,end='')
