"""Bake the actual vehicle-animation tables with Xenon's byte order.

zGlobal_DATA writes each wheelie/jump/squish/crash-fall entry as a MatrixND, so the
authored scale.z and the pad after it share the int t[0], scale in the low half
(retail's little-endian image). Read as halfwords on big-endian Xenon the pad came
first: every baked matrix had scale.z 0 and flattened the kart front to back, both
wheel pairs at one spot. GCC's scalar_storage_order gives these structs Xenon's
order on the host, so the actual split runs against every table entry.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',default='cc')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
vector=(root/'game/Vector.c').read_text();data=(root/'game/zGlobal_DATA.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
split=function(vector,'static void Vector_BakeMatrixTable_SplitAuthoredScaleZ(')
tables=data[data.index('.matArr01 ='):data.index('.bakedGteMath =')]
arrays=[]
for m in re.finditer(r'\.(matArr[0-9A-F]{2}) =\s*\{',tables):
 depth=1;end=m.end()
 while depth:depth+=(tables[end]=='{')-(tables[end]=='}');end+=1
 arrays.append((m[1],tables[m.end()-1:end]))
assert len(arrays)==19,len(arrays)
counts=[len(re.findall(r'\.extraShort',body)) for _,body in arrays]
assert sum(counts)==131,counts   # 104 authored entries and the 27 blasted frames
def program(order):
 attribute='__attribute__((scalar_storage_order("%s")))'%order
 entries=''.join('static struct MatrixND %s[] = %s;\n'%(name,body) for name,body in arrays)
 table=''.join('{%s,%d},'%(name,count) for (name,_),count in zip(arrays,counts))
 return r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef short s16;typedef int s32;
#define NULL ((void *)0)
struct ATTR MatrixND {s16 m[3][3];s16 extraShort;int t[3];};
typedef struct ATTR SVec3Slot {s16 x,y,z,w;} SVec3Slot;
typedef struct ATTR MatrixNDAuthored {SVec3Slot bakedOffset,authoredRot,authoredScale;s32 authoredPad[2];} MatrixNDAuthored;
static MatrixNDAuthored *MatrixND_GetAuthored(struct MatrixND *matrix){return (MatrixNDAuthored *)matrix;}
enum {BAKED_GTE_MATRIX_COUNT=0x14};
ENTRIES
static struct {struct {void *physEntry;int numEntries;} bakedGteMath[BAKED_GTE_MATRIX_COUNT];} data;
static const struct {struct MatrixND *entries;int count;} tables[]={TABLE};
SPLIT
int main(void){
 /* bakedGteMath[0] is blank; the arrays follow in order. The blasted frames' scale is set at
  * run time afterwards, so only the other 104 entries carry authored scale.z. */
 for(int i=0;i<19;i++){data.bakedGteMath[i+1].physEntry=tables[i].entries;data.bakedGteMath[i+1].numEntries=tables[i].count;}
 static s16 before[19][32][4];static int t0[19][32];unsigned authored=0,zeroBefore=0;
 for(int i=0;i<19;i++)for(int j=0;j<tables[i].count;j++){
  MatrixNDAuthored *e=MatrixND_GetAuthored(&tables[i].entries[j]);
  before[i][j][0]=e->authoredScale.x;before[i][j][1]=e->authoredScale.y;before[i][j][2]=e->authoredScale.z;before[i][j][3]=e->authoredRot.x;
  t0[i][j]=tables[i].entries[j].t[0];zeroBefore+=e->authoredScale.z==0 && t0[i][j]!=0;
 }
 Vector_BakeMatrixTable_SplitAuthoredScaleZ();
 for(int i=0;i<19;i++)for(int j=0;j<tables[i].count;j++){
  if(i==5)continue;
  MatrixNDAuthored *e=MatrixND_GetAuthored(&tables[i].entries[j]);
  assert(e->authoredScale.z==t0[i][j] && e->authoredScale.z>=3000 && e->authoredScale.z<=5400 && e->authoredScale.w==0);
  assert(e->authoredScale.x==before[i][j][0] && e->authoredScale.y==before[i][j][1] && e->authoredRot.x==before[i][j][3]);
  authored++;
 }
 printf("%s order: %u authored entries, scale.z read as 0 before the split in %u\n",ORDER,authored,zeroBefore);
 assert(authored==104);
 return zeroBefore;
}
'''.replace('ATTR',attribute).replace('ENTRIES',entries).replace('TABLE',table).replace('SPLIT',split).replace('ORDER','"%s"'%order)
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=a.out/(name+'.exe')
 subprocess.run([a.cc,'-std=gnu17','-w',str(source),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
big=run(program('big-endian'),'matrix-bake-xenon')
# Xenon's order: every authored entry read scale.z as 0, and the split gives each its value.
assert big.returncode==131,big.stdout+big.stderr;print('PASS: '+big.stdout.strip())
little=run(program('little-endian'),'matrix-bake-retail')
# Retail's order is already right: the split changes nothing there.
assert little.returncode==0,little.stdout+little.stderr;print('PASS: '+little.stdout.strip())
without=program('big-endian').replace('Vector_BakeMatrixTable_SplitAuthoredScaleZ();\n for','for',1)
assert without!=program('big-endian') and run(without,'matrix-bake-unsplit').returncode not in (0,131)
print('PASS: baking Xenon-order tables without the split (scale.z 0, kart flattened) rejected')
