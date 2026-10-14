"""Exercise the real request/flag transition, including a hidden hub flag."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/race-transition'
out.mkdir(parents=True, exist_ok=True)


def function(path, name):
    source = (root / path).read_text()
    match = re.search(r'^.*\b' + name + r'\([^;]*?\)\s*\n\{', source, re.M)
    assert match, name
    start = source.index('{', match.start())
    end, depth = start + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end] + '\n'


flag = (root / 'game/RaceFlag.c').read_text()
c = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define CTR_NATIVE 1
#define CTR_PSX_REGISTER(x)
#define ADVENTURE_ARENA 0x100000
#define RENDER_FLAG_CHECKERED_FLAG 0x800
#define HUD_FLAG_CLEAR_RACE_HUD_MASK 0xfffffffeu
#define LOAD_REQUESTED -4
typedef int32_t s32;typedef uint32_t u32;typedef int16_t s16;typedef uint16_t u16;typedef int b32;
struct GameTracker {u32 gameMode1,hudFlags,renderFlags;int elapsedTimeMS,swapchainIndex,levelID;
 u32 *otSwapchainDB[2];struct {u32 *ptrOT;} pushBuffer[1];};
static struct GameTracker tracker;
static struct {struct GameTracker*gGT;int RaceFlag_AnimationType; s16 RaceFlag_Position,RaceFlag_TransitionSpeed,
 RaceFlag_CanDraw,RaceFlag_DrawInitialized,RaceFlag_DrawOrder;int RaceFlag_LoadingTextAnimFrame,AkuAkuHintState;
 struct {int stage,Lev_ID_To_Load;} Loading;} state;
static typeof(state)*sdata=&state;
#define GAME_TRACKER (sdata->gGT)
static void Platform_Log(const char*text,...){(void)text;}
'''
c += re.search(r'enum RaceFlagConstants\s*\{.*?\};', flag, re.S).group() + '\n'
for name in ('RaceFlag_IsFullyOffScreen', 'RaceFlag_IsFullyOnScreen', 'RaceFlag_SetDrawOrder',
             'RaceFlag_SetCanDraw', 'RaceFlag_BeginTransition', 'RaceFlag_GetOT', 'RaceFlag_ResetTextAnim'):
    c += function('game/RaceFlag.c', name)
c += function('game/MAIN/MainRaceTrack.c', 'MainRaceTrack_RequestLoad')
c += r'''
int main(int argc,char**argv){
 u32 ot[2048]={0};(void)argv;sdata->gGT=&tracker;
 tracker.otSwapchainDB[0]=ot;tracker.pushBuffer[0].ptrOT=ot+1024;
 for(int ms=16;ms<=64;ms+=16)for(int hidden=0;hidden<2;hidden++)for(int partial=0;partial<2;partial++){
  int tick=0;memset(&state,0,sizeof state);sdata->gGT=&tracker;
  tracker.gameMode1=ADVENTURE_ARENA;tracker.elapsedTimeMS=ms;tracker.levelID=27;
  state.Loading.stage=-1;state.RaceFlag_Position=partial?1234:5000;state.RaceFlag_CanDraw=!hidden;
  tracker.renderFlags=0;
  MainRaceTrack_RequestLoad(5);
  assert(state.Loading.stage==LOAD_REQUESTED&&state.Loading.Lev_ID_To_Load==5);
  while(tick++<160&&!RaceFlag_IsFullyOnScreen()){
   if(state.RaceFlag_CanDraw&&(tracker.renderFlags&RENDER_FLAG_CHECKERED_FLAG))RaceFlag_GetOT();
  }
  if(argc>1&&hidden){assert(!RaceFlag_IsFullyOnScreen());continue;}
  assert(RaceFlag_IsFullyOnScreen()&&tick<160);
  RaceFlag_BeginTransition(2);tick=0;
  while(tick++<160&&(tracker.renderFlags&RENDER_FLAG_CHECKERED_FLAG))RaceFlag_GetOT();
  assert(RaceFlag_IsFullyOffScreen()&&tick<160);
 }
 /* Cutscene requests retain their deliberately hidden flag. */
 tracker.gameMode1=0;state.RaceFlag_CanDraw=0;MainRaceTrack_RequestLoad(40);assert(!state.RaceFlag_CanDraw);
 puts("PASS actual race requests and cover/uncover at 16/32/48/64 ms, hidden hub flag recovery and hidden cutscene preservation");return 0;
}
'''
draw = function('game/RaceFlag.c', 'RaceFlag_DrawSelf')
assert draw.count('RaceFlag_GetOT()') == 1, 'transition must advance once per draw'
assert 'RaceFlag_GetOT()' not in function('game/MAIN/MainFrame_RenderFrame.c', 'MainFrame_RenderFrame')
for old in (False, True):
    source = c.replace('RaceFlag_SetCanDraw(1);', '(void)0;') if old else c
    name = 'old-hidden' if old else 'fixture'
    (out / f'{name}.c').write_text(source)
    subprocess.run(['clang', '-O2', str(out / f'{name}.c'), '-o', str(out / f'{name}.exe')], check=True)
    run = subprocess.run([str(out / f'{name}.exe')] + (['old'] if old else []), text=True, capture_output=True, check=True)
    (out / f'{name}.log').write_text(run.stdout)
    print(('Negative control: hidden hub stays stuck. ' if old else '') + run.stdout, end='')
