"""Run actual hub/mask queue, read, callback and allocator functions together.

Synthetic file bodies use the shipped files' byte counts, not retail content.
CD and GPU work are stubbed; queue delay, mempack reuse and callbacks are real.
This tests the overlap absent from the earlier isolated residency fixture.
"""
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/hub-queue-ownership'
out.mkdir(parents=True, exist_ok=True)


def block(text, opening):
    end, depth = opening + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return end


def function(path, name):
    text = (root / path).read_text()
    match = re.search(r'^.*\b' + name + r'\([^;]*?\)\s*\n\{', text, re.M)
    assert match, name
    opening = text.index('{', match.start())
    return text[match.start():block(text, opening)] + '\n'


def enum(path, name):
    return re.search(r'enum\s+' + name + r'\s*\{.*?\};',
                     (root / path).read_text(), re.S).group() + '\n'


c = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <setjmp.h>
#define CTR_NATIVE 1
#define inline static inline
#define CTR_PSX_REGISTER(x)
#define CTR_PSX_KEEP_VALUE_RELAXED(x)
#define CTR_PSX_OBSERVE_MEMORY(x)
#define CTR_PSX_RELOAD(x)
#define CTR_TRAP() assert(0)
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;
typedef int16_t s16;typedef int32_t s32;typedef int b32;
'''
c += enum('include/namespace_Level.h', 'LevelID')
for name in ('BigIndex', 'LoadCdSectorConstants', 'LoadCharacterConstants',
             'LoadBigfileGroupConstants', 'LoadHubConstants', 'LoadQueueConstants',
             'LoadTenStagesConstants', 'LoadLevelLod', 'LevVramIndex', 'LoadTypeLegacy', 'LoadType', 'DramPointerMapConstants'):
    c += enum('include/namespace_Load.h', name)
c += enum('include/namespace_Mempack.h', 'MempackConstants')
header = (root / 'include/namespace_Mempack.h').read_text()
c += re.search(r'struct Mempack\s*\{.*?\};', header, re.S).group() + '\n'
c += r'''
#define MEMPACK_ALIGN_SIZE(x) (((x)+MEMPACK_ALIGNMENT_MASK)&MEMPACK_ALIGNMENT_CLEAR_MASK)
struct BigEntry {int offset,size;};
struct BigHeader {int cdpos,numEntry;struct BigEntry entry[608];};
#define BIG_GETENTRY(x) ((x)->entry)
struct Model {int unused;};struct Level {int unused;};
struct GameTracker {int levelID,activeMempackIndex,levID_in_each_mempack[4],frameTimer_VsyncCallback,boolDemoMode;
 struct Level *level2;};
struct LoadQueueSlot {struct BigHeader*ptrBigfileCdPos_UNUSED;u16 flags,type_UNUSED;u32 subfileIndex;
 void*ptrDestination;u32 size_UNUSED;void(*callbackFuncPtr)(struct LoadQueueSlot*);};
struct DramPointerMap {int numBytes;};
#define DRAM_GETOFFSETS(x) ((int*)((char*)(x)+4))
#define LOAD_QUEUE_CALLBACK_SET_POINTER ((void(*)(struct LoadQueueSlot*))-2)
struct BossCutsceneData {s32 fileIDs[3];};
enum {CS_BOSS_MODEL_HEAD=0,CS_BOSS_MODEL_COUNT=2};
static struct {struct LoadQueueSlot currSlot;struct Model*boss[2];} data;
static struct {struct GameTracker*gGT;struct Mempack mempack[4],*PtrMempack;
 int queueLength,queueReady,queueRetry,load_inProgress,frameFinishedVRAM,XA_State,AkuAkuHintState;
 int frameCounter,AkuHint_RequestedHint,AkuHint_boolInterruptWarppad;
 struct {int stage;} Loading;
 struct LoadQueueSlot queueSlots[8];
 struct BigHeader *ptrBigfile1,*ptrBigfileCdPos_2;void*PatchMem_Ptr;
 struct Model*modelMaskHints3D;struct Level*ptrLevelFile;
 void(*callbackCdReadSuccess)(struct LoadQueueSlot*);
} state,*sdata=&state;
#define MEMPACK_ACTIVE sdata->PtrMempack
#define MEMPACK_POOLS sdata->mempack
#define GAME_TRACKER sdata->gGT
#define CS_BOSS_MODELS data.boss
#define CS_BOSS_HEAD_MODEL data.boss[0]
#define CS_BIGFILE_HEADER sdata->ptrBigfile1
#define CS_LOAD_IN_PROGRESS sdata->load_inProgress
static u8 arena[3][0x69000],patch[0x10000];
static struct GameTracker gt;static struct BigHeader big;
static int failedFile,failedFree,reads,maskStarts,ticks,armed,pauseSteps;
static jmp_buf failure;
static void Platform_Log(const char*fmt,...){(void)fmt;}
static void Platform_LogError(const char*fmt,...){
 va_list args;va_start(args,fmt);vfprintf(stderr,fmt,args);va_end(args);
 failedFile=(int)data.currSlot.subfileIndex;
 failedFree=(int)((u8*)MEMPACK_ACTIVE->lastFreeByte-(u8*)MEMPACK_ACTIVE->firstFreeByte);
}
static void Platform_LogFlush(void){}
static void fixtureExit(int code){assert(armed);longjmp(failure,code?code:1);}
#define exit fixtureExit
#define Platform_Exit fixtureExit
static void CTR_ErrorScreen(int a,int b,int c){(void)a;(void)b;(void)c;assert(0);}
static void CDSYS_SetMode_StreamData(void){}
static void CDSYS_XAPauseRequest(void){if(sdata->XA_State)sdata->XA_State=2;}
static void CDSYS_XAPauseAtEnd(void){if(sdata->XA_State && ++pauseSteps>=3)sdata->XA_State=0;}
typedef struct {int sector;} CdlLOC;
enum {CdlComplete=2,CdlDiskError=5,CdlSetloc=2,CdlModeSpeed=128};
static void CdIntToPos(int p,CdlLOC*l){l->sector=p;}
static int CdControl(int c,u8*l,u8*r){(void)c;(void)l;(void)r;return 1;}
static void CdReadCallback(void(*cb)(u8,u8*)){(void)cb;}
static int CdReadSync(int mode,u8*r){(void)mode;(void)r;return 0;}
static int CdRead(int sectors,void*dst,int mode){
 (void)mode;reads++;memset(dst,0,(size_t)sectors*2048);
 if(data.currSlot.type_UNUSED==LT_DRAM)*(int*)dst=-1;
 return 1;
}
static void LOAD_RunPtrMap(char*origin,int*patches,int count){(void)origin;(void)patches;assert(count==0);}
static void LOAD_VramFileCallback(struct LoadQueueSlot*lqs){(void)lqs;sdata->frameFinishedVRAM=gt.frameTimer_VsyncCallback;}
static void LOAD_NextQueuedFile(void);
static void VSync(int n){(void)n;gt.frameTimer_VsyncCallback++;ticks++;assert(ticks<200);}
static int LOAD_GetBigfileIndex(u32 lev,int lod,int kind){(void)lod;return BI_ADVENTUREHUB+(lev-GEM_STONE_VALLEY)*3+kind;}
'''
for name in ('MEMPACK_SwapPacks', 'MEMPACK_NewPack', 'MEMPACK_GetFreeBytes',
             'MEMPACK_AllocMem', 'MEMPACK_ReallocMem', 'MEMPACK_PushState',
             'MEMPACK_ClearLowMem', 'MEMPACK_ClearHighMem', 'MEMPACK_PopState'):
    c += function('game/MEMPACK.c', name)
for name in ('LOAD_NativeReadFailure', 'LOAD_ReadFileASyncCallback', 'LOAD_ReadFile_ex',
             'LOAD_DramFileCallback', 'LOAD_DramFile', 'LOAD_VramFile'):
    c += function('game/LOAD/LOAD_File.c', name)
for name in ('LOAD_Callback_LEV', 'LOAD_Callback_PatchMem', 'LOAD_HubCallback', 'LOAD_Callback_MaskHints3D'):
    c += function('game/LOAD/LOAD_Callbacks.c', name)
for name in ('LOAD_TraceDemoQueue', 'LOAD_AppendQueue', 'LOAD_CDRequestCallback', 'LOAD_NextQueuedFile'):
    source = function('game/LOAD/LOAD_Queue.c', name)
    # Forward declaration has the same storage class as the real definition.
    source = source.replace('void LOAD_NextQueuedFile()', 'static void LOAD_NextQueuedFile()')
    c += source
c += function('game/LOAD/LOAD_Hub.c', 'LOAD_Hub_ReadFile')
negative = '--negative-control' in sys.argv
for path, name in (('game/LOAD/LOAD_Level.c','LOAD_TalkingMask'),('game/233/CS_LoadBoss.c','CS_LoadBossCallback'),('game/233/CS_LoadBoss.c','CS_LoadBoss')):
    source = function(path,name)
    if negative:
        source = re.sub(r'#ifdef CTR_NATIVE\s*/\* A hub preload.*?#endif\n', '', source, flags=re.S)
    c += source
c += r'''
static void AH_MaskHint_Start(s16 hint,u16 interrupt){
 (void)hint;(void)interrupt;maskStarts++;LOAD_TalkingMask(1,0);
}
'''
render = (root/'game/MAIN/MainFrame_RenderFrame.c').read_text()
start = render.index('if (sdata->AkuHint_RequestedHint != -1')
opening = render.index('{',start)
bridge = render[start:block(render,opening)]
if negative:
    bridge = re.sub(r'#ifdef CTR_NATIVE\s*/\* Keep the hint request.*?#endif\n', '', bridge, flags=re.S)
c += 'static void renderHintBridge(void){\n' + bridge + '\n}\n'
c += r'''
static void init(void){
 memset(&state,0,sizeof state);memset(&data,0,sizeof data);memset(&gt,0,sizeof gt);memset(&big,0,sizeof big);
 memset(arena,0x7a,sizeof arena);memset(patch,0,sizeof patch);
 state.gGT=&gt;state.ptrBigfile1=state.ptrBigfileCdPos_2=&big;state.queueReady=1;
 state.AkuHint_RequestedHint=-1;state.PatchMem_Ptr=patch;state.Loading.stage=-1;
 gt.activeMempackIndex=2;gt.levelID=N_SANITY_BEACH;gt.frameTimer_VsyncCallback=10;
 gt.levID_in_each_mempack[1]=LOAD_NO_LEVEL_IN_MEMPACK;gt.levID_in_each_mempack[2]=N_SANITY_BEACH;
 for(int p=0;p<3;p++){MEMPACK_SwapPacks(p);MEMPACK_NewPack(arena[p],0x68800);MEMPACK_ACTIVE->endOfAllocator=arena[p]+0x68800;}
 MEMPACK_SwapPacks(2);MEMPACK_AllocMem(403400+128,NULL);
 big.numEntry=608;
 big.entry[200]=(struct BigEntry){200,229432};big.entry[201]=(struct BigEntry){201,421168};
 big.entry[202]=(struct BigEntry){202,48032};big.entry[438]=(struct BigEntry){438,229432};
 big.entry[439]=(struct BigEntry){439,4880};
 failedFile=-1;reads=maskStarts=ticks=pauseSteps=0;
}
static void tick(void){LOAD_NextQueuedFile();CDSYS_XAPauseAtEnd();VSync(0);}
static int busy(void){return state.load_inProgress||state.queueLength||!state.queueReady;}
static void finish(void){while(busy())tick();}
int main(void){
 armed=1;
 if(setjmp(failure)){
  fprintf(stderr,"FAIL overlap: file=%d free=%d reads=%d activePack=%d\n",failedFile,failedFree,reads,(int)(MEMPACK_ACTIVE-state.mempack));
  return 2;
 }
 for(int phase=0;phase<8;phase++){
  init();LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);
  for(int i=0;i<phase;i++)tick();
  state.AkuAkuHintState=1;state.AkuHint_RequestedHint=7;state.AkuHint_boolInterruptWarppad=3;
  int wasBusy=busy(),oldReads=reads;
  renderHintBridge();
  if(wasBusy && state.AkuHint_RequestedHint!=-1){
   assert(!maskStarts && state.AkuHint_boolInterruptWarppad==3 && reads==oldReads);
   while(busy()){
    tick();if(busy()){renderHintBridge();assert(!maskStarts && state.AkuHint_RequestedHint==7);}
   }
   assert(gt.level2==(struct Level*)(arena[1]+4));
   renderHintBridge();
  }
  assert(maskStarts==1 && state.AkuHint_RequestedHint==-1 && !state.AkuHint_boolInterruptWarppad);
  finish();assert((u8*)state.modelMaskHints3D==arena[1]+4 && !gt.level2);
  assert(gt.levID_in_each_mempack[1]==GEM_STONE_VALLEY);
  assert(state.mempack[2].firstFreeByte==arena[2]+403528);
  assert(state.mempack[1].numBookmarks==0);
  state.AkuAkuHintState=0;
  LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);finish();
  assert(gt.level2==(struct Level*)(arena[1]+4) && MEMPACK_ACTIVE==&state.mempack[2]);
 }
 /* Lower-level callers also must finish the old batch before reusing it. */
 init();LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);tick();LOAD_TalkingMask(1,0);
 assert(state.queueLength==2 && !gt.level2);finish();assert((u8*)state.modelMaskHints3D==arena[1]+4);
 init();LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);tick();
 struct BossCutsceneData boss={{438,439,0}};CS_LoadBoss(&boss);
 assert(state.queueLength==2 && !gt.level2);finish();assert((u8*)CS_BOSS_HEAD_MODEL==arena[1]+4);
 /* Blocking fallback must also service the XA fade, as the main loop does. */
 init();LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);state.XA_State=1;LOAD_TalkingMask(1,0);
 assert(pauseSteps==3 && !state.XA_State && state.queueLength==2);finish();
 init();LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);state.XA_State=1;CS_LoadBoss(&boss);
 assert(pauseSteps==3 && !state.XA_State && state.queueLength==2);finish();
 puts("PASS actual hub/mask/boss queue ownership: 8 hint-arrival phases, request retention, VRAM delay/bookmarks, callbacks, active-pack protection, mask invalidation/reload, guarded direct reuse");
}
'''
(out/'fixture.c').write_text(c,encoding='utf-8')
compile = subprocess.run(['clang','-O2','-Wno-pointer-to-int-cast','-Wno-int-to-pointer-cast',str(out/'fixture.c'),'-o',str(out/'fixture.exe')],capture_output=True,text=True)
(out/'compile.log').write_text(compile.stdout+compile.stderr,encoding='utf-8')
if compile.returncode:
    print(compile.stdout+compile.stderr)
    raise SystemExit(compile.returncode)
run = subprocess.run([str(out/'fixture.exe')],capture_output=True,text=True)
(out/('negative.log' if negative else 'fixture.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
print(run.stdout+run.stderr,end='')
if negative:
    assert run.returncode==2 and 'file=438' in run.stderr, 'old overlap policy did not reproduce the hardware allocation error'
    print('PASS negative control: old interleaving fails on Aku VRAM file 438')
else:
    raise SystemExit(run.returncode)
