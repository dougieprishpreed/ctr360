"""Execute glow routing and HUD capture/replay without ticking UI animation."""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
weapon=(root/'game/UI/UI_Weapon.c').read_text();gpu=(root/'platform/native_gpu.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
body=function(weapon,'void UI_Weapon_DrawBG(')
constants='enum {'+''.join(re.findall(r'\bUI_WEAPON_BG_\w+\s*=\s*[^,;]+,',weapon))+'};\n'
color=re.search(r'static const u32 UI_WEAPON_BG_SHINE_COLOR[^;]+;',weapon)[0]
c=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef int16_t s16;typedef uint16_t u16;typedef uint32_t u32;
typedef struct {s16 x,y,page,clut;unsigned char rest[12];} GrVertex;
struct Icon {int identity;};struct PrimMem {int unused;};
struct PushBuffer {u32 *ptrOT;};
struct GameTracker {struct Icon *ptrIcons[64];struct {struct PrimMem primMem;} *backBuffer;struct PushBuffer pushBuffer[4],pushBuffer_UI;};
struct Driver {int driverID;struct {int juicedUpCooldown;} BattleHUD;};
static struct {struct GameTracker *gGT;int wumpaShineTheta;} state,*sdata=&state;
typedef struct {int uiPass;struct {int dfe;} drawenv;u16 startVertex,numVerts;} GPUDrawSplit;
enum {NATIVE_HD_HUD_VERTICES=24576,NATIVE_HD_HUD_SPLITS=1024};
static GrVertex s_hdHUDVertices[NATIVE_HD_HUD_VERTICES];static GPUDrawSplit s_hdHUDSplits[NATIVE_HD_HUD_SPLITS];
static int s_hdHUDVertexCount,s_hdHUDSplitCount,s_hdHUDCaptureEnabled,s_hdHUDValid;
static unsigned calls,replays,uploads;static s16 expectedX,expectedY;
'''+constants+color+function(gpu,'static void NativeGpu_CaptureHUD(')+r'''
static void UI_WeaponBG_DrawShine(struct Icon *icon,s16 x,s16 y,struct PrimMem *mem,u32 *ot,char transparency,s16 sx,s16 sy,int color){
 assert(ot==sdata->gGT->pushBuffer_UI.ptrOT);assert(x==expectedX && y==expectedY);
 assert(sx==4096 && sy==3328 && transparency==2+(calls%2));
 assert(icon==sdata->gGT->ptrIcons[49]);calls++;
 GrVertex vertices[3]={{0}};vertices[0].x=x;vertices[0].y=y;
 GPUDrawSplit split={.uiPass=ot==sdata->gGT->pushBuffer_UI.ptrOT,.drawenv={1},.numVerts=3};
 NativeGpu_CaptureHUD(&split,vertices);
}
static void NativeRenderer_UpdateVertexBuffer(const GrVertex *v,int count){assert(count==6 && v[0].x==expectedX && v[0].y==expectedY);uploads++;}
static void DrawSplit(const GPUDrawSplit *split){assert(split->uiPass && split->numVerts==3);replays++;}
'''+body+function(gpu,'void NativeGpu_ReplayHUD(')+r'''
int main(void){
 u32 world[4][4],ui[4];struct GameTracker gt={0};struct Icon icon={1};struct {struct PrimMem primMem;} db;
 gt.backBuffer=(void*)&db;gt.ptrIcons[49]=&icon;gt.pushBuffer_UI.ptrOT=ui;sdata->gGT=&gt;
 for(int i=0;i<4;i++)gt.pushBuffer[i].ptrOT=world[i];
 for(int player=0;player<4;player++)for(int center=0;center<2;center++){
  struct Driver driver={.driverID=player,.BattleHUD={1}};
  expectedX=center?256:345;expectedY=center?8:17;
  s_hdHUDVertexCount=s_hdHUDSplitCount=0;s_hdHUDValid=s_hdHUDCaptureEnabled=1;
  unsigned theta=state.wumpaShineTheta;UI_Weapon_DrawBG(expectedX,expectedY,4096,&driver);
  assert(driver.BattleHUD.juicedUpCooldown==0 && state.wumpaShineTheta==theta+256);
  assert(s_hdHUDSplitCount==2 && s_hdHUDVertexCount==6);
  theta=state.wumpaShineTheta;NativeGpu_ReplayHUD();
  assert(state.wumpaShineTheta==theta && driver.BattleHUD.juicedUpCooldown==0);
 }
 assert(calls==16 && replays==16 && uploads==8);
 puts("PASS: fruit/weapon glows use UI OT for all four players, captured/replayed on midpoints without animation ticks");
}
'''
def run(source,name):
 path=a.out/(name+'.c');path.write_text(source);exe=a.out/name
 subprocess.run(['cc','-std=c17',str(path),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'hud-glow');assert r.returncode==0,r.stderr;print(r.stdout.strip())
old=body.replace('gGT->pushBuffer_UI.ptrOT','gGT->pushBuffer[d->driverID].ptrOT')
assert old!=body and run(c.replace(body,old),'hud-glow-negative').returncode!=0
print('PASS: previous world-OT glow routing rejected')
