"""Actual hub/mask/boss entry points: cache reuse must not publish overwritten LEVs.

The CD/allocator fixture models in-place reuse and queued completion, rather
than rendering gameplay. This is a lifetime regression, not a BE emulator.
"""
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/hub-residency-contract'

def function(path, name):
    text = (root / path).read_text()
    start = re.search(r'(?m)^void\s+' + name + r'\s*\(', text).start()
    opening = text.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'

def enum(path, name):
    text = (root / path).read_text()
    return re.search(r'enum\s+' + name + r'\s*\{.*?\};', text, re.S).group() + '\n'

prelude = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdarg.h>
#define CTR_NATIVE 1
typedef int32_t s32; typedef uint32_t u32; typedef int16_t s16;
'''
prelude += enum('include/namespace_Level.h', 'LevelID')
for name in ['BigIndex', 'LoadBigfileGroupConstants', 'LoadHubConstants', 'LoadTenStagesConstants', 'LoadLevelLod', 'LevVramIndex', 'LoadTypeLegacy', 'LoadType']:
    prelude += enum('include/namespace_Load.h', name)
prelude += r'''
enum {CS_BOSS_MODEL_HEAD=0,CS_BOSS_MODEL_COUNT=2};
struct Model {int id;};
struct VisMem {void *visLeafSrc[1],*visFaceSrc[1],*visOVertSrc[1],*visSCVertSrc[1];};
struct CameraDC {void *ptrQuadBlock,*visLeafSrc,*visFaceSrc,*visInstSrc,*visOVertSrc,*visSCVertSrc;};
struct Driver {void *underDriver;};
struct Level {int numModels; struct Model **ptrModelsPtrArray;void *ptr_mesh_info,*ptrInstDefs,*levTexLookup;int numInstances;};
struct GameTracker {
 struct Level *level1,*level2;struct VisMem *visMem1,*visMem2;
 struct CameraDC cameraDC[1];struct Driver *drivers[1];
 int bool_AdvHub_NeedToSwapLEV;int activeMempackIndex,levelID,prevLEV,framesInThisLEV,msInThisLEV,boolHubSwapped;
 int levID_in_each_mempack[4];
};
struct BigHeader {int unused;};
struct LoadQueueSlot {int file;void *ptrDestination;void (*callback)(struct LoadQueueSlot*);};
struct BossCutsceneData {s32 fileIDs[3];};
static struct {struct GameTracker *gGT;struct Model *modelMaskHints3D;int load_inProgress,queueLength,queueReady;
 struct BigHeader *ptrBigfile1,*ptrBigfileCdPos_2;void *PatchMem_Ptr;int AkuAkuHintState;} state,*sdata=&state;
static struct Model *bossModels[CS_BOSS_MODEL_COUNT];
#define GAME_TRACKER (sdata->gGT)
#define CS_BOSS_MODELS bossModels
#define CS_BOSS_HEAD_MODEL bossModels[0]
#define CS_BIGFILE_HEADER (sdata->ptrBigfileCdPos_2)
#define CS_LOAD_IN_PROGRESS (sdata->load_inProgress)
#define LOAD_QUEUE_CALLBACK_SET_POINTER ((void (*)(struct LoadQueueSlot*))1)
static struct LoadQueueSlot queue[8];
static struct Level resident[4];static struct Model validModel={49};static struct Model *validModels[]={&validModel};
static int pack,clearCount,hubReads,modelReads,waits;
static void Platform_Log(const char *fmt,...){(void)fmt;}
static void Platform_LogFlush(void){}
static void MEMPACK_SwapPacks(int id){pack=id;}
static void MEMPACK_ClearLowMem(void){memset(&resident[pack],0x61,sizeof resident[pack]);clearCount++;}
static void LOAD_AppendQueue(struct BigHeader*b,int type,int file,void*dst,void(*cb)(struct LoadQueueSlot*)){
 (void)b;(void)type;assert(sdata->queueLength<8);
 queue[sdata->queueLength++]=(struct LoadQueueSlot){file,dst,cb};
}
static void LOAD_HubCallback(struct LoadQueueSlot*l){(void)l;
 resident[pack]=(struct Level){1,validModels,(void*)7,(void*)8,(void*)9,3};
 GAME_TRACKER->level2=&resident[pack];sdata->load_inProgress=0;hubReads++;
 MEMPACK_SwapPacks(GAME_TRACKER->activeMempackIndex);
}
static void LOAD_Callback_LEV(struct LoadQueueSlot*l){(void)l;}
static void LOAD_Callback_MaskHints3D(struct LoadQueueSlot*l){(void)l;sdata->modelMaskHints3D=&validModel;sdata->load_inProgress=0;}
static void LOAD_NextQueuedFile(void){
 assert(sdata->queueLength>0);
 struct LoadQueueSlot l=queue[0];memmove(queue,queue+1,(--sdata->queueLength)*sizeof *queue);
 if(l.callback && l.callback!=LOAD_QUEUE_CALLBACK_SET_POINTER)l.callback(&l);
 sdata->queueReady=1;
}
static void VSync(int unused){(void)unused;waits++;assert(waits<50);}
static int LOAD_GetBigfileIndex(int lev,int lod,int kind){(void)lod;return lev*3+kind;}
static void LevInstDef_RePack(void*p,int v){(void)p;(void)v;}
static void Audio_AdvHub_SwapSong(int lev){(void)lev;}
static void LibraryOfModels_Clear(struct GameTracker*g){(void)g;}
static void LOAD_GlobalModelPtrs_MPK(void){}
static void LibraryOfModels_Store(struct GameTracker*g,u32 n,struct Model**m){(void)g;assert(n==1&&m==validModels&&m[0]->id==49);modelReads++;}
static void INSTANCE_LevInitAll(void*p,int n){assert(p==(void*)8&&n==3);}
static void LevInstDef_UnPack(void*p){assert(p==(void*)7);}
static void DecalGlobal_Store(struct GameTracker*g,void*p){(void)g;assert(p==(void*)9);}
static void MainInit_VisMem(struct GameTracker*g){(void)g;}
static void CDSYS_XAPauseRequest(void){}
'''
# Existing conditional model publication is unrelated to the residency test.
prelude = prelude.replace('void *PatchMem_Ptr;', 'void *PatchMem_Ptr;int PLYROBJECTLIST;')
source = function('game/LOAD/LOAD_Hub.c', 'LOAD_Hub_ReadFile')
negative = '--negative-control' in sys.argv
if negative:
    source, replaced = re.subn(r'#ifdef CTR_NATIVE\s*/\* The preload trigger.*?#endif', '', source, count=1, flags=re.S)
    assert replaced == 1
source += function('game/LOAD/LOAD_ModelPtrs.c', 'LOAD_HubSwapPtrs')
source += function('game/LOAD/LOAD_Hub.c', 'LOAD_Hub_SwapNow')
source += function('game/LOAD/LOAD_Level.c', 'LOAD_TalkingMask')
source += function('game/233/CS_LoadBoss.c', 'CS_LoadBossCallback')
source += function('game/233/CS_LoadBoss.c', 'CS_LoadBoss')
tests = r'''
int main(void){
 struct GameTracker g={0};struct BigHeader big={0};struct VisMem vm[2]={0};struct Driver d={0};
 struct BossCutsceneData boss={{0,20,0}};
 sdata->gGT=&g;sdata->ptrBigfile1=sdata->ptrBigfileCdPos_2=&big;sdata->queueReady=1;
 g.drivers[0]=&d;g.visMem1=&vm[0];g.visMem2=&vm[1];g.activeMempackIndex=2;g.levelID=N_SANITY_BEACH;
 g.levID_in_each_mempack[1]=GEM_STONE_VALLEY;g.levID_in_each_mempack[2]=N_SANITY_BEACH;
 resident[1]=resident[2]=(struct Level){1,validModels,(void*)7,(void*)8,(void*)9,3};
 g.level1=&resident[2];g.level2=&resident[1];
 LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);assert(clearCount==0&&sdata->queueLength==0);
 LOAD_TalkingMask(1,1);
 assert(!g.level2&&g.levID_in_each_mempack[1]==GEM_STONE_VALLEY&&sdata->queueLength==2);
 LOAD_Hub_SwapNow();
 assert(hubReads==1&&modelReads==1&&g.levelID==GEM_STONE_VALLEY&&g.prevLEV==N_SANITY_BEACH);
 assert(g.level1==&resident[1]&&g.level2==&resident[2]&&sdata->queueLength==0);
 /* Returning across a cached boundary should not reread the disc. */
 LOAD_Hub_SwapNow();assert(hubReads==1&&g.levelID==N_SANITY_BEACH);
 /* Boss assets reuse the same pack and must trigger an equivalent reload. */
 CS_LoadBoss(&boss);assert(!g.level2&&g.levID_in_each_mempack[1]==GEM_STONE_VALLEY);
 LOAD_Hub_SwapNow();assert(hubReads==2&&g.levelID==GEM_STONE_VALLEY&&modelReads==3);
 /* A matching ID with an invalid pointer must never be a cache hit. */
 g.level2=NULL;int oldClear=clearCount;
 LOAD_Hub_ReadFile(&big,N_SANITY_BEACH,2);assert(clearCount==oldClear+1&&sdata->queueLength==3);
 /* Real MainFrame samples the same trigger while these files are pending.
  * The old cache check restarted and appended this batch every frame. */
 for(int tick=0;tick<20;tick++)LOAD_Hub_ReadFile(&big,N_SANITY_BEACH,2);
 assert(clearCount==oldClear+1&&sdata->queueLength==3);
 while(sdata->queueLength)LOAD_NextQueuedFile();
 LOAD_Hub_SwapNow();assert(hubReads==3&&g.levelID==N_SANITY_BEACH);
 /* A speaking mask keeps ownership of the alternate pack even after I/O. */
 g.level2=NULL;sdata->AkuAkuHintState=4;oldClear=clearCount;
 LOAD_Hub_ReadFile(&big,GEM_STONE_VALLEY,1);
 assert(clearCount==oldClear&&sdata->queueLength==0);
 int oldLevel=g.levelID,oldHubReads=hubReads,oldWaits=waits;
 LOAD_Hub_SwapNow();
 assert(g.bool_AdvHub_NeedToSwapLEV==1&&g.levelID==oldLevel&&hubReads==oldHubReads&&waits==oldWaits);
 assert(clearCount==oldClear&&sdata->queueLength==0);
 sdata->AkuAkuHintState=0;
 /* An uninitialized destination cannot silently swap or hang waiting. */
 g.level2=NULL;g.levID_in_each_mempack[1]=-1;int oldModels=modelReads;
 LOAD_Hub_SwapNow();assert(modelReads==oldModels&&sdata->queueLength==0&&g.levelID==N_SANITY_BEACH);
 puts("PASS actual hub entry points: mask/boss invalidation, destination retention, pending queue drain, repeated preload triggers, live mask ownership, fresh reload, cached return, invalid destination deferral");
 return 0;
}
'''
out.with_suffix('.c').write_text(prelude + source + tests, encoding='utf8')
subprocess.run(['clang','-O2',str(out.with_suffix('.c')),'-o',str(out.with_suffix('.exe'))],check=True)
run = subprocess.run([str(out.with_suffix('.exe'))],capture_output=True,text=True)
out.with_suffix('.log').write_text(run.stdout+run.stderr,encoding='utf8')
print(run.stdout+run.stderr,end='')
if negative:
    assert run.returncode != 0, 'old repeated-trigger policy unexpectedly passed'
    print('PASS negative control: old policy fails repeated preload assertion')
    raise SystemExit(0)
if run.returncode: raise SystemExit(run.returncode)
