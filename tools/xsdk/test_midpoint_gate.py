"""Evaluate the actual render-only midpoint gate against retail flag states.

The checkered flag advances its slide inside RaceFlag_GetOT and is not part of
the HUD replay, so midpoints must stay off while it is drawn: otherwise every
other displayed frame lacks the flag during the race intro.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
hd=(root/'game/MAIN/MainHD.c').read_text();header=(root/'include/namespace_Main.h').read_text()
begin=hd.index('if (!g_nativeHDEnableInterpolation');depth=0;end=hd.index('(',begin)
while True:
 depth+=(hd[end]=='(')-(hd[end]==')');end+=1
 if depth==0:break
condition=hd[hd.index('(',begin):end]
modes=hd[hd.index('    u32 originalRouteModes'):hd.index('\n',hd.index('if (g_nativeHDEnableInterpolation == 2)'))+1]
names=('LOAD_IDLE','LOADING','MAIN_MENU','GAME_CUTSCENE','ADVENTURE_ARENA','PAUSE_ALL','END_OF_RACE',
       'RENDER_FLAG_DRAW_LEVEL','RENDER_FLAG_RENDER_BUCKET','RENDER_FLAG_CHECKERED_FLAG')
values={n:re.search(r'\b'+n+r'\s*=\s*(-?(?:0x[0-9A-Fa-f]+|\d+))',header)[1] for n in names}
c='#include <assert.h>\n#include <stdio.h>\n'+''.join('#define %s (%s)\n'%(n,v) for n,v in values.items())+r'''
typedef unsigned u32;
struct Level {void *ptr_mesh_info;};
struct GameTracker {int numPlyrCurrGame;unsigned gameMode1,renderFlags;};
static struct {struct {int stage;} Loading;} state,*sdata=&state;
static int g_nativeHDEnableInterpolation=1;
static int skips(struct GameTracker *gGT,struct Level *level){
MODES return CONDITION;}
int main(void){
 int mesh;struct Level level={&mesh};
 struct GameTracker race={1,0,RENDER_FLAG_DRAW_LEVEL|RENDER_FLAG_RENDER_BUCKET};
 sdata->Loading.stage=LOAD_IDLE;
 assert(!skips(&race,&level));                                   /* ordinary race: midpoints */
 race.renderFlags|=RENDER_FLAG_CHECKERED_FLAG;assert(skips(&race,&level)); /* flag sliding off */
 race.renderFlags&=~RENDER_FLAG_CHECKERED_FLAG;assert(!skips(&race,&level));
 struct GameTracker paused=race;paused.gameMode1=PAUSE_ALL;assert(skips(&paused,&level));
 const unsigned scenes[]={ADVENTURE_ARENA,MAIN_MENU,GAME_CUTSCENE,END_OF_RACE};
 for(unsigned k=0;k<4;k++){struct GameTracker scene=race;scene.gameMode1=scenes[k];
  g_nativeHDEnableInterpolation=1;assert(!skips(&scene,&level));          /* 60 FPS everywhere */
  g_nativeHDEnableInterpolation=2;assert(skips(&scene,&level));           /* races only */
  g_nativeHDEnableInterpolation=1;}
 g_nativeHDEnableInterpolation=2;assert(!skips(&race,&level));g_nativeHDEnableInterpolation=0;assert(skips(&race,&level));g_nativeHDEnableInterpolation=1;
 struct GameTracker split=race;split.numPlyrCurrGame=2;assert(skips(&split,&level));
 sdata->Loading.stage=0;assert(skips(&race,&level));
 puts("PASS: actual midpoint gate keeps checkered-flag transitions on the original route; hub, menus, cutscenes and results with setting 1 only; pause, split-screen and loading unchanged");
}
'''.replace('CONDITION',condition).replace('MODES',modes)
def run(source,name):
 path=a.out/(name+'.c');path.write_text(source);exe=a.out/name
 subprocess.run(['cc','-std=c17',str(path),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'midpoint-gate');assert r.returncode==0,r.stderr;print(r.stdout.strip())
old=c.replace(' | RENDER_FLAG_CHECKERED_FLAG)) != (RENDER_FLAG_DRAW_LEVEL',')) != (RENDER_FLAG_DRAW_LEVEL')
assert old!=c and run(old,'midpoint-gate-negative').returncode!=0
print('PASS: previous gate that interpolated over the sliding flag rejected')
