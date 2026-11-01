"""Run the actual VBlank clock of native_xbox360_platform.c against a simulated TV.

Frames start their GPU work at the game's VBlank. With the game's VBlanks on
QPC at 59.83 Hz they drift against the TV's 60 Hz refreshes, so the time a
frame has before the next refresh sweeps from a whole refresh to almost none.
Following the TV's own vblank count (xsdk_present_stats), each game VBlank
comes just after a refresh, every time. The test also checks the catch-up
after a long frame, sleeping rather than spinning through a wait, the switch
to the TV once its count moves, and the return to QPC when it stops. The
negative control is the same code kept on QPC.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
src=(root/'platform/xbox360/native_xbox360_platform.c').read_text()
wait=src.index('void Platform_WaitUntilVBlank(int targetVBlank)')
clock=src[src.index('#define NATIVE_VBLANK_GPU_CYCLES'):src.index('\n}\n',wait)+3]
frame=(root/'game/MAIN/MainFrame_RenderFrame.c').read_text()
def function(text,head):
 start=text.index(head);return text[start:text.index('\n}\n',start)+3]
render=function(frame,'int ReadyToFlip(struct GameTracker *gGT)')+function(frame,'void RenderVSYNC(struct GameTracker *gGT)')
c=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define CTR_XSDK 1
#define internal static
#define global_variable static
typedef uint64_t u64;typedef uint32_t u32;typedef int32_t s32;
/* The console's clock in 50 MHz ticks, moved by the code's own looking and sleeping. */
#define FREQ 50000000ull
static u64 now_ticks=1000000;
static u64 X360_GetCounter(void){now_ticks+=25;return now_ticks;}            /* half a microsecond a look */
static u64 X360_GetFrequency(void){return FREQ;}
static double Native_CounterToMs(u64 d){return (double)d*1000.0/(double)FREQ;}
static u64 slept;
static void Sleep(unsigned ms){now_ticks+=ms*(FREQ/1000)+FREQ/5000;slept+=ms*(FREQ/1000);} /* wakes 0.2 ms late */
/* The TV: 60.000 Hz from display_open on, counting until display_stop. */
static u64 display_open=~0ull,display_stop=~0ull;static const u64 refresh=FREQ/60;
typedef struct {u32 vblanks,flips,missed,late,first_late_vblank,first_late_line,first_flip_vblank,last_flip_vblank,longest_wait_us,system_frames;} XsdkPresentStats;
static void xsdk_present_stats(XsdkPresentStats *s){
 u64 t=now_ticks<display_stop?now_ticks:display_stop;
 *s=(XsdkPresentStats){0};
#ifndef QPC_ONLY
 if(t>=display_open)s->vblanks=(u32)((t-display_open)/refresh)+1;
#endif
}
static void Platform_WatchStage(const char *s){(void)s;}
static int logs_display,logs_stopped;
#include <string.h>
static void Platform_Log(const char *f,...){if(strstr(f,"follow the display"))logs_display++;if(strstr(f,"stopped"))logs_stopped++;}
static u64 emitted_at[100000];static unsigned emitted;
static void NativeRCnt_EmitVBlank(void){emitted_at[emitted++]=now_ticks;}
static void (*vsync_callback)(void);
static void NativeAudio_StepVBlank(void){}
'''+clock+r'''
/* RenderVSYNC as the game has it: the flip waits until the VBlank callback
 * has counted the frame's two VBlanks down. */
#define CTR_NATIVE 1
#define RENDER_FLAG_CHECKERED_FLAG 0x1000
struct GameTracker {int clockDurationStall;unsigned renderFlags;int bool_DrawOTag_InProgress;};
static struct {int vsyncTillFlip;} sdataStorage,*sdata=&sdataStorage;
static int Timer_GetTime_Total(void){return 0;}
static int DrawSync(int mode){(void)mode;return 0;}
static void CountTillFlip(void){sdata->vsyncTillFlip--;}
'''+render+r'''
/* After a game VBlank: how far past the TV's last refresh it came. QPC_ONLY
 * keeps the count from the code, as before it followed the TV. */
static double since_refresh_ms(u64 t){return t<display_open?0:Native_CounterToMs((t-display_open)%refresh);}
int main(void){
 /* Before the display opens, QPC keeps the time. */
 for(int i=0;i<30;i++)Native_WaitAndEmitVBlank();
 assert(emitted==30 && logs_display==0);
 display_open=now_ticks+FREQ/100;
 /* The game: each update draws its frames, then waits for its VBlanks. */
 unsigned first=0;double worst=0,best=1e9;u64 slept0=0,waited=0;
 for(int i=0;i<1200;i++){
  now_ticks+=FREQ/1000*4;                                  /* 4 ms of game work */
  u64 t0=now_ticks;unsigned before=emitted;
  Native_CatchUpDueVBlanks();Native_WaitAndEmitVBlank();
  waited+=now_ticks-t0;
  if(i==300){first=emitted;slept0=slept;waited=0;}
  if(i>300){double s=since_refresh_ms(emitted_at[emitted-1]);if(s>worst)worst=s;if(s<best)best=s;
   assert(emitted-before==1);}                              /* one VBlank a refresh, none caught up */
 }
 printf("after the switch: each VBlank %.3f to %.3f ms after the TV's refresh; %.0f%% of the waiting slept\n",best,worst,100.0*(slept-slept0)/waited);
 fflush(stdout);
#ifdef QPC_ONLY
 assert(worst<2.0);                                         /* fails: QPC drifts across the refresh */
#else
 assert(logs_display==1 && worst<0.05);
 assert((double)(slept-slept0)/waited>0.6);                 /* sleeps through most of each wait */
 /* A long frame: 40 ms of work, then the VBlanks it missed come at once. */
 XsdkPresentStats s;xsdk_present_stats(&s);u32 shown=s.vblanks;
 now_ticks+=FREQ/1000*40;unsigned before=emitted;
 Native_CatchUpDueVBlanks();xsdk_present_stats(&s);
 assert(emitted-before==s.vblanks-shown);
 /* RenderVSYNC: a frame drawn in 36 ms, past its two refreshes, flips as soon as it's drawn. */
 struct GameTracker gt={0};vsync_callback=CountTillFlip;
 Native_WaitAndEmitVBlank();sdata->vsyncTillFlip=2;
 now_ticks+=FREQ/1000*36;u64 drawn=now_ticks;
 RenderVSYNC(&gt);
 double flipLate=Native_CounterToMs(now_ticks-drawn);
 printf("a frame drawn past its VBlanks flips %.3f ms after it's drawn\n",flipLate);fflush(stdout);
 assert(flipLate<0.1);
 /* One drawn in time flips on its second VBlank. */
 Native_WaitAndEmitVBlank();sdata->vsyncTillFlip=2;now_ticks+=FREQ/1000*5;
 RenderVSYNC(&gt);assert(sdata->vsyncTillFlip==0 && since_refresh_ms(now_ticks)<0.05);
 vsync_callback=0;
 /* The TV stops counting: back on QPC after 100 ms, without a hang. */
 display_stop=now_ticks;before=emitted;
 Native_WaitAndEmitVBlank();
 assert(logs_stopped==1 && emitted==before+1);
 for(int i=0;i<10;i++)Native_WaitAndEmitVBlank();
 assert(emitted==before+11);
 puts("PASS: actual VBlank clock follows the TV's vblanks once they count, sleeps through most of a wait, catches up after a long frame, flips a late frame (RenderVSYNC) as soon as it's drawn and returns to QPC when they stop");
#endif
}
'''
def run(source,name,*defs):
 path=a.out/(name+'.c');path.write_text(source);exe=a.out/name
 subprocess.run(['cc','-std=gnu17','-O1','-w',*defs,str(path),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'display-pacing');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip())
r=run(c,'display-pacing-qpc','-DQPC_ONLY');assert r.returncode!=0,r.stdout
print('PASS: the same code kept on QPC rejected:',r.stdout.strip().splitlines()[0])
late=c.replace('\t\tPlatform_CatchUpVBlanks();\n','')
assert late!=c;r=run(late,'display-pacing-late-flip');assert r.returncode!=0,r.stdout
print('PASS: RenderVSYNC without counting the due VBlanks first rejected:',r.stdout.strip().splitlines()[-1])
