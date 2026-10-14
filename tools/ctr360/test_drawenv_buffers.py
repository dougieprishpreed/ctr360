"""Execute the actual draw-environment writer with exact-fit/canary buffers."""
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[2]
out=root/'build-360/results/drawenv-buffers';out.mkdir(parents=True,exist_ok=True)
def function(path,name):
    source=(root/path).read_text();m=re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{',source,re.M);assert m,name
    begin=source.index('{',m.start());end=begin+1;depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[m.start():end]+'\n'
c=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define _XBOX 1
typedef uint8_t u8;typedef uint32_t u32;typedef int16_t s16;typedef int b32;
struct Rect {s16 x,y,w,h;};
typedef struct {struct Rect clip;s16 ofs[2];u8 isbg,pad[3];} DRAWENV;
typedef struct {u32 tag,code[15];} DR_ENV;
struct PushBuffer {struct Rect rect;};
struct DB {DRAWENV drawEnv;struct {void*cursor,*guardEnd;} primMem;};
static struct {struct PushBuffer pushBuffer_UI;} gt;
static struct {typeof(gt)*gGT;} state={&gt};static typeof(state)*sdata=&state;
static unsigned links;static DRAWENV last;
static u32 CTR_ReadU32LE(const void*p){const u8*b=p;return b[0]|((u32)b[1]<<8)|((u32)b[2]<<16)|((u32)b[3]<<24);}
static void CTR_WriteU32LE(void*p,u32 v){u8*b=p;for(int i=0;i<4;i++)b[i]=(u8)(v>>(i*8));}
static void CtrGpu_WriteControlWord(u32*p,u32 v){CTR_WriteU32LE(p,v);}
static void SetDrawEnv(void*p,DRAWENV*d){DR_ENV*env=p;last=*d;memset(p,0,64);CtrGpu_WriteControlWord(&env->code[2],0xe5000000);}
static void AddPrim(void*ot,void*p){(void)ot;(void)p;links++;}
'''
c+=function('include/gpu.h','CtrGpu_PrimFits')
c+=function('game/PushBuffer.c','PushBuffer_SetDrawEnv_Normal')
c+=r'''
int main(void){
 u8 arena[160];struct DB db={0};u32 ot=0;DR_ENV*packet=(DR_ENV*)(arena+16);int room;
 gt.pushBuffer_UI.rect=(struct Rect){0,0,512,240};
 for(room=0;room<64;room++){
  memset(arena,0xa5,sizeof arena);db.primMem.cursor=arena+16;db.primMem.guardEnd=arena+16+room;links=0;
  PushBuffer_SetDrawEnv_Normal(&ot,&gt.pushBuffer_UI,&db,NULL,0);
  assert(!links&&db.primMem.cursor==arena+16);
  for(int i=0;i<160;i++)assert(arena[i]==0xa5);
 }
 memset(arena,0xa5,sizeof arena);db.primMem.cursor=arena+16;db.primMem.guardEnd=arena+80;links=0;
 PushBuffer_SetDrawEnv_Normal(&ot,&gt.pushBuffer_UI,&db,NULL,0);
 assert(links==1&&db.primMem.cursor==arena+80&&last.clip.w==512&&last.clip.h==240);
 assert(CTR_ReadU32LE(&packet->code[2])&0x800000u);
 for(int i=80;i<160;i++)assert(arena[i]==0xa5);
 /* The flag keeps the full UI rectangle, but selects full-width projection. */
 struct PushBuffer flag=gt.pushBuffer_UI;db.primMem.cursor=arena+16;
 PushBuffer_SetDrawEnv_Normal(&ot,&flag,&db,NULL,0);
 assert(!(CTR_ReadU32LE(&packet->code[2])&0x800000u)&&last.clip.w==512&&last.clip.h==240);
 db.primMem.cursor=arena+16;
 PushBuffer_SetDrawEnv_Normal(&ot,&gt.pushBuffer_UI,&db,NULL,0);
 assert(CTR_ReadU32LE(&packet->code[2])&0x800000u);
 puts("PASS actual draw environment: all 0..63-byte-short buffers untouched, exact 64-byte fit, full-width flag rectangle and restored UI marker");
 return 0;
}
'''
(out/'fixture.c').write_text(c)
subprocess.run(['clang','-O2',str(out/'fixture.c'),'-o',str(out/'fixture.exe')],check=True)
run=subprocess.run([str(out/'fixture.exe')],capture_output=True,text=True,check=True)
(out/'fixture.log').write_text(run.stdout);print(run.stdout,end='')
