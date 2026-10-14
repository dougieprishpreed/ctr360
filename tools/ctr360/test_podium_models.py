"""Check real podium files and actual rank selection/slot-bound actor birth.

Asset identity is checked independently against the retail and cooked disc.
Actor allocation is a stub of the shared model lookup used by CS_Thread_Init.
"""
from pathlib import Path
import json
import re
import struct
import subprocess

import cook_disc as cook

root = Path(__file__).resolve().parents[2]
out = root/'build-360/results/podium-models'
out.mkdir(parents=True, exist_ok=True)

def function(path, name):
    text = (root/path).read_text()
    m = re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{', text, re.M)
    assert m, name
    opening = text.index('{', m.start()); end = opening+1; depth = 1
    while depth:
        depth += (text[end]=='{')-(text[end]=='}'); end += 1
    return text[m.start():end]+'\n'

constants = {}
header = (root/'include/namespace_Load.h').read_text().split('enum BigIndex',1)[1].split('};',1)[0]
for name, expression in re.findall(r'\b(BI_\w+)\s*=([^,\n]+)', header):
    constants[name] = eval(expression, {'__builtins__':{}}, constants)
retail = cook.IsoImage(str(root.parent/'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin'))
big = cook.BigFile(retail)
cooked = cook.IsoImage(str(root/'build-360/ctr-u-360.bin'))
models = []
for winner in (True, False):
    base = constants['BI_DANCEMODELWIN' if winner else 'BI_DANCEMODELLOSE']
    for character in range(16):
        for variant in range(2):
            entry = base+character*2+variant
            sector, size = big.entries[entry]
            raw = retail.read(big.lba+sector, size)
            cooked_bytes = cooked.read(big.lba+sector, size)
            if not size:  # Oxide's unused victory/defeat files are empty.
                assert character == 15
                continue
            model_id = struct.unpack_from('<h',raw,20)[0]
            assert model_id == 126+character == struct.unpack_from('>h',cooked_bytes,20)[0]
            name = raw[4:20].split(b'\0')[0].decode('ascii')
            assert name.endswith('dance' if winner else 'lose'), (entry,name)
            models.append({'entry':entry,'character':character,'variant':variant,'winner':winner,
                           'id':model_id,'name':name})
retail.close(); cooked.close()
(out/'asset-identities.json').write_text(json.dumps(models,indent=2)+'\n')
prefix = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <assert.h>
#define CTR_NATIVE 1
typedef uint8_t u8; typedef int16_t s16; typedef int32_t s32;
struct Model {char name[16];s16 id;};
struct Driver {s16 driverID,driverRank;};
struct Thread {struct Model *model;};
struct CsThreadInitData {int cookie;};
struct GameTracker {u8 podium_modelIndex_First,podium_modelIndex_Second,
 podium_modelIndex_Third,podium_modelIndex_tawna;struct Driver*drivers[8];struct Model*modelPtr[256];};
static struct GameTracker gt;
#define GAME_TRACKER (&gt)
static struct {s16 characterIDs[8];} data;
enum {NOFUNC=0,STATIC_CRASHDANCE=126,STATIC_OXIDEDANCE=141,STATIC_TAWNA1=143,
 STATIC_TAWNA2=144,STATIC_TAWNA3=145,STATIC_TAWNA4=146,
 CRASH_BANDICOOT=0,NEO_CORTEX=1,COCO_BANDICOOT=3,N_GIN=4,POLAR=6,PURA=7};
static struct Thread actor;static int births,errors;
static struct Thread* CS_Thread_Init(s32 id,const char*name,struct CsThreadInitData*init,s16 yaw,struct Thread*parent){
 (void)name;(void)yaw;assert(init->cookie==123&&!parent);births++;
 actor.model=id?gt.modelPtr[id]:NULL;return &actor;
}
static void Platform_Log(const char*fmt,...){(void)fmt;}
static void Platform_LogError(const char*fmt,...){(void)fmt;errors++;}
'''
source = (root/'game/Podium.c').read_text().replace('#include <common.h>','')
source += function('game/233/CS_Podium.c','CS_Podium_InitDancer')
arrays = 'static struct Model loaded[] = {'+','.join('{"'+m['name']+'",'+str(m['id'])+'}' for m in models)+'};\n'
tests = r'''
int main(void){
 struct Driver drivers[8];int rotation,i;struct CsThreadInitData init={123};
 for(rotation=0;rotation<16;rotation++){
  for(i=0;i<8;i++){drivers[i].driverID=(i+3)&7;drivers[i].driverRank=i;
   data.characterIDs[drivers[i].driverID]=(rotation+i)%16;gt.drivers[i]=&drivers[i];}
  Podium_InitModels(&gt);
  assert(gt.podium_modelIndex_First==126+rotation);
  assert(gt.podium_modelIndex_Second==126+(rotation+1)%16);
  assert(gt.podium_modelIndex_Third==126+(rotation+2)%16);
 }
 for(i=0;i<(int)(sizeof loaded/sizeof loaded[0]);i++){
  struct Model unrelated={"savecan",120},otherVariant={"other-variant",loaded[i].id};
  struct Thread*th;
  /* The ordinary shared lookup really would create this unrelated object. */
  gt.modelPtr[loaded[i].id]=&unrelated;
  assert(CS_Thread_Init(loaded[i].id,"third",&init,0,NULL)->model==&unrelated);
  th=CS_Podium_InitDancer(&loaded[i],(u8)loaded[i].id,2,"third",&init,0);
  assert(th&&th->model==&loaded[i]&&gt.modelPtr[loaded[i].id]==&unrelated);
  gt.modelPtr[loaded[i].id]=&otherVariant;
  th=CS_Podium_InitDancer(&loaded[i],(u8)loaded[i].id,0,"first",&init,0);
  assert(th&&th->model==&loaded[i]&&gt.modelPtr[loaded[i].id]==&otherVariant);
 }
 i=births;
 assert(!CS_Podium_InitDancer(NULL,126,2,"third",&init,0));
 assert(!CS_Podium_InitDancer(&loaded[0],127,2,"third",&init,0));
 assert(!CS_Podium_InitDancer(&loaded[0],255,2,"third",&init,0));
 assert(births==i&&errors==3);
 assert(CS_Podium_InitDancer(NULL,0,0,"camera",&init,0)->model==NULL);
 puts("PASS 60 retail/cooked podium files, all 16 character selections, per-slot models survive unrelated/shared-variant lookups; invalid/missing slots rejected and camera-only birth retained");
 return 0;
}
'''
path = out/'fixture.c'; path.write_text(prefix+source+arrays+tests)
subprocess.run(['clang','-O2',str(path),'-o',str(out/'fixture.exe')],check=True)
run = subprocess.run([str(out/'fixture.exe')],capture_output=True,text=True,check=True)
(out/'fixture.log').write_text(run.stdout)
print(run.stdout,end='')
