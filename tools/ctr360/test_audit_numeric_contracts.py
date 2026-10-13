"""Actual audited boundary helpers with asymmetric native/serialized data.

GTE operations are register fixtures; this is not PPC/GTE emulation or gameplay.
Credits validation additionally consumes the player's actual retail block.
"""
from pathlib import Path
import json
import re
import subprocess
import cook_disc as cook
root=Path(__file__).resolve().parents[2]
out=root/'build-360/results/audit-numeric-contracts'
out.mkdir(parents=True,exist_ok=True)

def function(path,name):
    s=(root/path).read_text();m=re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{',s,re.M);assert m,name
    start=s.index('{',m.start());end=start+1;depth=1
    while depth:
        depth+=(s[end]=='{')-(s[end]=='}');end+=1
    return s[m.start():end]+'\n'

evidence=json.loads((root/'build-360/results/20261012-engine-audit/credits-evidence.json').read_text())[0]
image=cook.IsoImage(str(root.parent/'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin'))
big=cook.BigFile(image);sector,size=big.entries[evidence['entry']]
raw=image.read(big.lba+sector,size);image.close()
offset=evidence['offset'];length=evidence['psx_size_count'][0]
(out/'credits.bin').write_bytes(raw[offset:offset+length])
c=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#define internal static
#define CTR_NATIVE 1
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef uint32_t u32;typedef int32_t s32;
typedef struct {s16 x,y,z;} SVec3;
typedef struct {s16 vx,vy,vz,pad;} SVECTOR;
typedef struct {s32 vx,vy,vz,pad;} VECTOR;
static u32 fixtureRegs[32],fixtureControls[32];
#define MFC2(n) (fixtureRegs[n])
#define MFC2_S(n) ((s32)fixtureRegs[n])
#define CFC2(n) (fixtureControls[n])
#define MTC2(v,n) (fixtureRegs[n]=(u32)(v))
#define CTC2(v,n) (fixtureControls[n]=(u32)(v))
static u32 CTR_PackS16Pair(s16 x,s16 y){return (u16)x|((u32)(u16)y<<16);}
static u16 CTR_ReadU16LE(const void*p){const u8*b=p;return b[0]|((u16)b[1]<<8);}
static u32 CTR_ReadU32LE(const void*p){const u8*b=p;return b[0]|((u32)b[1]<<8)|((u32)b[2]<<16)|((u32)b[3]<<24);}
static void gte_rt(void){fixtureRegs[25]=(s16)fixtureRegs[0]*2+10;fixtureRegs[26]=(s16)(fixtureRegs[0]>>16)*3-20;fixtureRegs[27]=(s16)fixtureRegs[1]*4+30;fixtureControls[31]=0x1234;}
static void gte_mvmva(int sf,int mx,int v,int cv,int lm){s32 x=(s16)fixtureRegs[0],y=(s16)(fixtureRegs[0]>>16),z=(s16)fixtureRegs[1];fixtureRegs[25]=x*x+y*y+z*z;}
static s32 SquareRoot0_stub(s32 sum){return sum;}
static struct {u8 rgb[3],enable;} clearColors[3];
static struct {struct {struct {struct {u8 rgb[3],enable;} clearColor[3];}*level1;}*gGT;u8 kartSpawnOrderArray[8];} state,*sdata=&state;
'''
for path,names in (
    ('include/ctr_gte.h',('CTR_GteStoreSXYWord',)),
    ('include/ctr_gte_transfer.h',('CTR_GteStorePositionXY','CTR_GteStoreLineXY')),
    ('game/MATH/MATH_4_VectorLength.c',('MATH_VectorLength',)),
    ('platform/native_libgte.c',('RotTrans',)),
    ('game/BOTS.c',('BOTS_Adv_CopySpawnOrder',)),
    ('game/CAM.c',('CAM_SkyboxGlow_ClearGradientColor',)),
    ('game/233/CS_Credits.c',('CS_Credits_ValidateStrings','CS_Credits_FadeColor')),
):
    for n in names:c+=function(path,n)
transfer=(root/'include/ctr_gte_transfer.h').read_text()
start=transfer.index('#define CTR_GteLoadLineV0V1');end=transfer.index('#else',start)
c+=transfer[start:end]
c+=r'''
int main(int argc,char**argv){
 SVec3 vectors[]={{0,0,0},{100,200,300},{-321,654,-987},{30000,0,0}};
 for(int i=0;i<4;i++){SVec3*v=&vectors[i];assert(MATH_VectorLength(v)==v->x*v->x+v->y*v->y+v->z*v->z);assert(fixtureRegs[0]==CTR_PackS16Pair(v->x,v->y));}
 SVECTOR v={-123,234,-345,0x7fff};VECTOR result={0};s32 flag=0;
 RotTrans(&v,&result,&flag);assert(result.vx==-236&&result.vy==682&&result.vz==-1350&&flag==0x1234);
 s16 xy[4]={0};fixtureRegs[14]=CTR_PackS16Pair(-77,199);CTR_GteStorePositionXY(xy);assert(xy[0]==-77&&xy[1]==199);
 u32 line[3]={CTR_PackS16Pair(111,-222),CTR_PackS16Pair(-333,444),(u32)-555};
 CTR_GteLoadLineV0V1(line);assert(fixtureRegs[0]==line[0]&&fixtureRegs[1]==line[2]&&fixtureRegs[2]==line[1]&&fixtureRegs[3]==line[2]);
 fixtureRegs[12]=line[0];fixtureRegs[13]=line[1];CTR_GteStoreLineXY(xy);assert(xy[0]==111&&xy[1]==-222&&xy[2]==-333&&xy[3]==444);
 BOTS_Adv_CopySpawnOrder(0x03020100,0x07060504);for(int i=0;i<8;i++)assert(state.kartSpawnOrderArray[i]==i);
 typeof(*state.gGT) gt;typeof(*gt.level1) level;state.gGT=&gt;gt.level1=&level;
 level.clearColor[2].rgb[0]=128;level.clearColor[2].rgb[1]=7;level.clearColor[2].rgb[2]=224;level.clearColor[2].enable=119;
 assert(CAM_SkyboxGlow_ClearGradientColor()==0xe00780);
 assert(CS_Credits_FadeColor(0x91e4c82a,128)==0x91726415);
 assert(CS_Credits_FadeColor(0x00ffffff,0)==0&&CS_Credits_FadeColor(0x00123456,256)==0x00123456);
 assert(argc==2);FILE*f=fopen(argv[1],"rb");u8 bytes[11294];assert(f&&fread(bytes,1,sizeof bytes,f)==sizeof bytes);fclose(f);
 u32 size=0;u16 count=0;assert(CS_Credits_ValidateStrings(bytes,sizeof bytes,&size,&count)&&size==11294&&count==23);
 assert(!CS_Credits_ValidateStrings(bytes,sizeof bytes-1,&size,&count));
 memset(bytes+8,0xff,4);assert(!CS_Credits_ValidateStrings(bytes,sizeof bytes,&size,&count));
 assert(!CS_Credits_ValidateStrings(NULL,0,&size,&count));
 puts("PASS actual native vector/RotTrans/pickup/spider/spawn/RGB/fade boundaries and retail credits extent/offset validation; GTE operations are fixtures");
}
'''
(out/'fixture.c').write_text(c)
subprocess.run(['clang','-O2',str(out/'fixture.c'),'-o',str(out/'fixture.exe')],check=True)
subprocess.run([str(out/'fixture.exe'),str(out/'credits.bin')],check=True)
