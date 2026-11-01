"""Feed the actual [graphics] steady governor of native_xsdk_video.c GPU frame times.

While the GPU's recent frames average more than a refresh can hold, an
update's two frames can't show on its two refreshes, so the in-between frames
go off and each update shows for two refreshes; they come back once the
frames are short again. Hysteresis and a 2 s hold keep a scene that swings
from switching every few frames. The negative control has no hold.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
src=(root/'platform/xsdk/native_xsdk_video.c').read_text()
governor=src[src.index('enum { XV_STEADY_OFF_US'):src.index('\n}\n',src.index('static void XvSteadyFrame'))+3]
c=r'''
#include <assert.h>
#include <stdio.h>
static unsigned ms;
static unsigned GetTickCount(void){return ms;}
static unsigned switches_logged;
static void Platform_Log(const char *f,...){(void)f;switches_logged++;}
'''+governor+r'''
/* Frames of us each, the clock moving a refresh a frame; the switches seen. */
static unsigned run(unsigned frames,unsigned us){unsigned before=xvSteadySwitches;
 for(unsigned i=0;i<frames;i++){ms+=17;XvSteadyFrame(us);}return xvSteadySwitches-before;}
int main(void){
 ms=10000;
 assert(xvSteady==0);xvSteady=1;                                      /* off unless the ini turns it on */
 assert(run(300,13000)==0 && NativeRenderer_MidpointsFit());          /* light race: in-between frames */
 assert(run(120,16500)==1 && !NativeRenderer_MidpointsFit());         /* GPU behind: off */
 assert(run(300,15000)==0 && !NativeRenderer_MidpointsFit());         /* still too long to come back */
 assert(run(300,13000)==1 && NativeRenderer_MidpointsFit());          /* short again: on */
 unsigned swings=0,start=ms;for(int k=0;k<20;k++){swings+=run(20,18000);swings+=run(20,11000);}
 printf("a scene swinging every third of a second switched %u times in %.1f s\n",swings,(ms-start)/1000.0);fflush(stdout);
 assert(swings>=2 && swings<=(ms-start)/2000+1);                      /* at most once a hold */
 xvSteady=0;run(300,13000);assert(run(300,17000)==0 && NativeRenderer_MidpointsFit()); /* steady = 0 */
 puts("PASS: actual steady governor turns in-between frames off while the GPU's frames run long, back on when short, at most once every 2 s, and never with steady = 0");
}
'''
def run(source,name):
 path=a.out/(name+'.c');path.write_text(source);exe=a.out/name
 subprocess.run(['cc','-std=gnu17','-O1','-w',str(path),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'steady-frames');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip())
old=c.replace('now-xvSteadySince<XV_STEADY_HOLD_MS','0')
assert old!=c;r=run(old,'steady-frames-no-hold');assert r.returncode!=0,r.stdout
print('PASS: the governor without its hold rejected:',r.stdout.strip().splitlines()[-1])
