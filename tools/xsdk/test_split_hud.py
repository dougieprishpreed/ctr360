"""Lay out the actual 3/4-player HUD tables through the widescreen HUD squeeze.

Each 3/4-player viewport is a 16:9 quarter of the 1280x720 screen, while the HUD
squeeze keeps the authored 512-wide layout at 4:3 around the screen's centre:
x -> 640 + (x - 256) * 1.875. That pulled every player's outer elements in over the
kart: the place number sat over the middle of its viewport. Widescreen moves the
outer-half elements out by the squeeze's margin; 4:3 keeps the tables as authored.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',default='cc')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
hd=(root/'game/MAIN/MainHD.c').read_text();data=(root/'game/zGlobal_DATA.c').read_text();ui=(root/'include/namespace_UI.h').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
code=re.search(r'#define NATIVE_HD_SPLIT_HUD_MARGIN \d+\n',hd)[0]+function(hd,'static int NativeHD_DivRound3(')+\
 function(hd,'void NativeHD_WidenSplitScreenHud(')+function(hd,'int NativeHD_ViewportMidX(')
slots=ui[ui.index('enum UIHudSlot'):ui.index('};',ui.index('enum UIHudSlot'))+2]
tables=''
for player in range(1,5):
 m=re.search(r'\.hud_4P_P%d =\s*\{'%player,data);depth=1;end=m.end()
 while depth:depth+=(data[end]=='{')-(data[end]=='}');end+=1
 tables+='static const struct UiElement2D authored%d[]=%s;\n'%(player,data[m.end()-1:end])
c=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef short s16;
struct UiElement2D {s16 x,y,z,scale;};
SLOTS
typedef struct {s16 x,y,w,h;} RECT;
struct PushBuffer {RECT rect;};
struct GameTracker {int numPlyrCurrGame;};
static struct GameTracker tracker;static struct {struct GameTracker *gGT;} state={&tracker},*sdata=&state;
static struct {struct UiElement2D hud_4P_P1[20],hud_4P_P2[20],hud_4P_P3[20],hud_4P_P4[20];} data;
static int g_nativeHDWidescreen=1;
TABLES
CODE
static const struct UiElement2D *authored[4]={authored1,authored2,authored3,authored4};
static struct UiElement2D *table(int p){return p==0?data.hud_4P_P1:p==1?data.hud_4P_P2:p==2?data.hud_4P_P3:data.hud_4P_P4;}
/* Output pixels: the squeeze, and each viewport's 16:9 span (PushBuffer_Init: 0 or 0x103, 0xfd wide). */
static double Out(int x){return 640+(x-256)*1.875;}
static double Left(int p){return (p&1)?0x103*2.5:0;}
static double Right(int p){return Left(p)+0xfd*2.5;}
static int Shines(int slot){return slot==UI_HUD_SLOT_BATTLE_WEAPON_BG || slot==UI_HUD_SLOT_RACING_WEAPON_BG;}
static int Abs(int p,int slot,int x){return x+(Shines(slot) && (p&1)?0x103:0);}
static void Load(void){for(int p=0;p<4;p++)memcpy(table(p),authored[p],sizeof(data.hud_4P_P1));}
int main(void){
 Load();g_nativeHDWidescreen=0;NativeHD_WidenSplitScreenHud();
 for(int p=0;p<4;p++)assert(!memcmp(table(p),authored[p],sizeof(data.hud_4P_P1)));   /* 4:3: as authored */
 g_nativeHDWidescreen=1;NativeHD_WidenSplitScreenHud();NativeHD_WidenSplitScreenHud();
 unsigned moved=0;
 for(int p=0;p<4;p++){
  double width=Right(p)-Left(p);
  for(int s=0;s<UI_HUD_SLOT_COUNT;s++){
   int was=Abs(p,s,authored[p][s].x),now=Abs(p,s,table(p)[s].x);
   assert(table(p)[s].y==authored[p][s].y && table(p)[s].scale==authored[p][s].scale);
   double before=Out(was),after=Out(now);
   if(now!=was){moved++;
    /* Outer elements keep their 4:3 distance from the screen edge (within a pixel)... */
    double edge=(p&1)?1280-after:after,authoredEdge=(p&1)?(512-was)*1.875:was*1.875;
    assert(edge>authoredEdge-1.2 && edge<authoredEdge+1.2);
    assert((p&1)?after>before:after<before);
   }
   /* ...and every anchor stays on its own player's side of the screen. */
   assert(after>=Left(p)-20 && after<=Right(p)+20);
  }
  /* The place number and its suffix sit at the outer side of the viewport, clear of the
   * kart in its middle (squeezed, they started at 37% and 52% of their viewports). */
  for(int k=0;k<2;k++){
   int s=k?UI_HUD_SLOT_RANK:UI_HUD_SLOT_BIG1;double at=(Out(Abs(p,s,table(p)[s].x))-Left(p))/width;
   assert((p&1)?at>0.7:at<0.2);
  }
  /* Groups keep their spacing: number and suffix; weapon and its shine; fruit, count and shine. */
  int groups[3][3]={{UI_HUD_SLOT_BIG1,UI_HUD_SLOT_RANK,UI_HUD_SLOT_RANK},{UI_HUD_SLOT_WEAPON,UI_HUD_SLOT_BATTLE_WEAPON_BG,UI_HUD_SLOT_WEAPON},
   {UI_HUD_SLOT_FRUIT_MODEL,UI_HUD_SLOT_WUMPA_COUNT,UI_HUD_SLOT_RACING_WEAPON_BG}};
  for(int g=0;g<3;g++)for(int k=1;k<3;k++){
   int s0=groups[g][0],s1=groups[g][k];
   assert(Abs(p,s1,table(p)[s1].x)-Abs(p,s0,table(p)[s0].x)==Abs(p,s1,authored[p][s1].x)-Abs(p,s0,authored[p][s0].x));
  }
 }
 /* Text centred on a viewport lands on its 16:9 centre; 1/2 players keep the screen's. */
 static const RECT quarters[4]={{0,0,0xfd,0x6a},{0x103,0,0xfd,0x6a},{0,0x6e,0xfd,0x6a},{0x103,0x6e,0xfd,0x6a}};
 for(int players=3;players<=4;players++)for(int p=0;p<players;p++){
  struct PushBuffer pb={quarters[p]};tracker.numPlyrCurrGame=players;
  assert(Out(NativeHD_ViewportMidX(&pb))>(Left(p)+Right(p))/2-2 && Out(NativeHD_ViewportMidX(&pb))<(Left(p)+Right(p))/2+2);
 }
 struct PushBuffer full={{0,0,0x200,0x6a}};tracker.numPlyrCurrGame=2;assert(NativeHD_ViewportMidX(&full)==256);
 g_nativeHDWidescreen=0;tracker.numPlyrCurrGame=4;{struct PushBuffer pb={quarters[1]};assert(NativeHD_ViewportMidX(&pb)==0x103+0xfd/2);}
 printf("PASS: %u outer 3/4-player HUD anchors moved to their screen edges; place numbers at each viewport's outer side; groups kept; centred text on each viewport; 4:3 as authored\n",moved);
}
'''.replace('SLOTS',slots).replace('TABLES',tables).replace('CODE',code)
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=a.out/(name+'.exe')
 subprocess.run([a.cc,'-std=gnu17','-w',str(source),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'split-hud');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip())
unmoved=c.replace('widened = 1;','widened = 1;return;',1)
assert unmoved!=c and run(unmoved,'split-hud-squeezed').returncode!=0
print('PASS: the squeezed layout (place numbers over the middle of each viewport) rejected')
