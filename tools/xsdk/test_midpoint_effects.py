"""Find each instance's previous pose with the actual midpoint matcher.

The turbo flames change model every update (eight models in turn). Matching the
model as well as the instance found no previous pose for them, so midpoints drew
the flames at the update's end, half a frame ahead of the kart: at speed they
showed twice and too high. Threaded instances now match on their thread; a pooled
instance reused for a new object has a new thread, and threadless level
instances still need their model. An object the last update did not have (a new
boost's flames) is left out of the midpoint: the original first shows it at its
own update's frame, and at that pose it stood half a frame ahead of the kart.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',default='cc')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
hd=(root/'game/MAIN/MainHD.c').read_text()
def block(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]
pose=block(hd,'struct NativeHDPose')+';\n'
defines=''.join(re.findall(r'#define NATIVE_HD_(?:INSTANCE_LIMIT|POSE_HASH_SIZE) \d+\n',hd))
matcher=block(hd,'static void NativeHD_IndexPreviousPoses(')+'\n'+block(hd,'static int NativeHD_FindPreviousPose(')+'\n'+block(hd,'static int NativeHD_IsNewObject(')+'\n'
loop=hd[hd.index('j = NativeHD_FindPreviousPose('):hd.index('/* The frustum from the midpoint camera culls')]
assert re.search(r'else if \(NativeHD_IsNewObject\(s_hdCurrent\[i\]\.instance, s_hdCurrent\[i\]\.thread\)\)\s*\{\s*s_hdCurrent\[i\]\.instance->flags \|= HIDE_MODEL;',loop),'new objects not left out of the midpoint'
assert defines.count('#define')==2
c=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int16_t s16;typedef int32_t s32;typedef uint16_t u16;typedef uint32_t u32;
typedef struct {s16 m[3][3];s16 pad;s32 t[3];} MATRIX;
struct Instance{int id;};struct Model{int id;};struct Thread{int id;};
@@DEFINES@@
@@POSE@@
static struct NativeHDPose s_hdPrevious[NATIVE_HD_INSTANCE_LIMIT];
static int s_hdPoseCount;
static u16 s_hdPoseHash[NATIVE_HD_POSE_HASH_SIZE];
@@MATCHER@@
static struct Instance flame1,flame2,pickup,tree,newFlame;
static struct Model turbo[8],box,fruit,treeModel,treeStump;
static struct Thread turboThread,oldPickup,newPickup,newTurbo;
static void Previous(int i,struct Instance *inst,struct Model *model,struct Thread *thread)
{s_hdPrevious[i].instance=inst;s_hdPrevious[i].model=model;s_hdPrevious[i].thread=thread;}
int main(void){
 /* Last update: both flames at frames 2 and 5, a box, a level tree. */
 Previous(0,&flame1,&turbo[2],&turboThread);Previous(1,&flame2,&turbo[5],&turboThread);
 Previous(2,&pickup,&box,&oldPickup);Previous(3,&tree,&treeModel,NULL);
 s_hdPoseCount=4;NativeHD_IndexPreviousPoses();
 /* This update the flames show frames 3 and 6: still the same flames. */
 assert(NativeHD_FindPreviousPose(&flame1,&turbo[3],&turboThread)==0);
 assert(NativeHD_FindPreviousPose(&flame2,&turbo[6],&turboThread)==1);
 /* The box's instance went back to the pool and now holds a new pickup. */
 assert(NativeHD_FindPreviousPose(&pickup,&fruit,&newPickup)<0);
 assert(NativeHD_FindPreviousPose(&pickup,&box,&newPickup)<0);
 /* Level instances have no thread: their model has to match. */
 assert(NativeHD_FindPreviousPose(&tree,&treeModel,NULL)==3);
 assert(NativeHD_FindPreviousPose(&tree,&treeStump,NULL)<0);
 /* Which objects are new: a new boost's flames and the reused pickup are; the same
  * flames and the tree with another model are not. */
 assert(!NativeHD_IsNewObject(&flame1,&turboThread) && !NativeHD_IsNewObject(&flame2,&turboThread));
 assert(NativeHD_IsNewObject(&newFlame,&newTurbo) && NativeHD_IsNewObject(&pickup,&newPickup));
 assert(!NativeHD_IsNewObject(&tree,NULL));
 puts("PASS: actual matcher keeps the turbo flames' previous poses across model changes, not a reused instance's, and level instances by model; a new boost's flames are left out of the midpoint");
 return 0;
}
'''
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=(a.out/(name+'.exe')).resolve()
 subprocess.run([a.cc,'-std=gnu17','-w',str(source),'-o',str(exe)],check=True)
 return subprocess.run([str(exe)],capture_output=True,text=True)
test=c.replace('@@DEFINES@@',defines).replace('@@POSE@@',pose).replace('@@MATCHER@@',matcher)
r=run(test,'midpoint-effects');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip())
old=matcher.replace('(thread != NULL ? s_hdPrevious[index].thread == thread : s_hdPrevious[index].model == model)',
                    's_hdPrevious[index].model == model')
assert old!=matcher
r=run(c.replace('@@DEFINES@@',defines).replace('@@POSE@@',pose).replace('@@MATCHER@@',old),'midpoint-effects-model-only')
assert r.returncode!=0
print('PASS: matching on the model alone (flames drawn half a frame ahead) rejected')
