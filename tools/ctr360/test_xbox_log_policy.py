"""Actual logger/begin-scene/audio-report boundaries with a small XTL fixture."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/xbox-log-policy-contract'
out.mkdir(exist_ok=True)
stubs = out / 'include'
(stubs / 'platform').mkdir(parents=True, exist_ok=True)
(stubs / 'macros.h').write_text('#define CTR_PRINTF_FORMAT(a,b)\n#define global_variable static\n#define internal static\n')
(stubs / 'platform/native_perf.h').write_text('')
(stubs / 'xtl.h').write_text('')

def function(path, name):
    s = (root / path).read_text()
    start = re.search(r'(?m)^(?:internal\s+)?(?:int|DWORD\s+WINAPI)\s+'+name+r'\s*\(',s).start()
    begin = s.index('{',start)
    end, depth = begin + 1, 1
    while depth:
        depth += (s[end]=='{') - (s[end]=='}')
        end += 1
    return s[start:end]+'\n'

source = r'''
#define _CRT_SECURE_NO_WARNINGS 1
#include <stdio.h>
#include <stdint.h>
#include <assert.h>
typedef int32_t LONG;typedef uint32_t DWORD;typedef void *LPVOID;
typedef int16_t s16;typedef uint8_t u8;typedef uint32_t u32;
#define WINAPI
static unsigned tick;static int flushes,consoleWrites,audioHeld,audioMode,audioTicks;
static LONG InterlockedCompareExchange(volatile LONG*p,LONG v,LONG c){LONG old=*p;if(old==c)*p=v;return old;}
static LONG InterlockedExchange(volatile LONG*p,LONG v){LONG old=*p;*p=v;return old;}
static unsigned GetTickCount(void){return audioMode ? (audioTicks++ ? 6000 : 0) : tick;}
static void Sleep(unsigned ms);
static void OutputDebugStringA(const char*p){(void)p;}
static int TrackedFlush(FILE*f){assert(!audioHeld);flushes++;return fflush(f);}
static int TrackedConsole(const char*p,FILE*f){(void)p;(void)f;assert(!audioHeld);consoleWrites++;return 0;}
'''
source += '#include "'+(root/'platform/native_trace.c').as_posix()+'"\n'
source += '#define fflush TrackedFlush\n#define fputs TrackedConsole\n'
source += '#include "'+(root/'platform/xbox360/native_xbox360_log.c').as_posix()+'"\n'
source += '#undef fflush\n#undef fputs\n'
source += r'''
typedef struct {s16 x,y,w,h;} RECT16;
static struct {int isbg;RECT16 clip;u8 r0,g0,b0;} activeDrawEnv;
static int s_platformBeginScene,begins;
static void NativeRenderer_BeginScene(void){begins++;}
static void NativeRenderer_Clear(int x,int y,int w,int h,u8 r,u8 g,u8 b){(void)x;(void)y;(void)w;(void)h;(void)r;(void)g;(void)b;}
'''
source += function('platform/xbox360/native_xbox360_platform.c','Platform_BeginScene')
source += r'''
#define X360_AUDIO_PULL_FRAMES 512
#define X360_AUDIO_TARGET_BUFFERS 3
typedef struct SDL_AudioStream SDL_AudioStream;
struct SDL_AudioStream {int running,resumed,lock;void *voice,*userdata;void(*callback)(void*,SDL_AudioStream*,int,int);LONG pullCount;u32 nonzeroSamples,submitFailures;struct {int channels;} spec;};
typedef struct {u32 BuffersQueued;uint64_t SamplesPlayed;} XAUDIO2_VOICE_STATE;
static SDL_AudioStream *audio;
static void Sleep(unsigned ms){if(audioMode&&ms==1)audio->running=0;}
static void RtlEnterCriticalSection(void*l){(void)l;assert(!audioHeld);audioHeld=1;}
static void RtlLeaveCriticalSection(void*l){(void)l;assert(audioHeld);audioHeld=0;}
static void IXAudio2SourceVoice_GetState(void*v,XAUDIO2_VOICE_STATE*s,int flags){(void)v;(void)flags;assert(audioHeld);s->BuffersQueued=3;s->SamplesPlayed=100;}
'''
source += function('platform/xbox360/native_xbox360_audio_out.c','X360Audio_ThreadProc')
source += r'''
int main(int argc,char**argv){
 assert(argc==2);assert(Platform_LogSetPath(argv[1]));Platform_LogInit("fixture");
 int baseFlush=flushes,baseConsole=consoleWrites;
 for(int i=0;i<12000;i++)Platform_Log("[probe] hb rb f=%d step=draw-exit\n",3535+i%20);
 assert(flushes==baseFlush&&consoleWrites==baseConsole&&s_logBufferLen==0);
 Platform_Log("[perf] level=8 frames=120 periodMax=32ms\n");
 assert(s_logBufferLen>0&&flushes==baseFlush&&consoleWrites==baseConsole);
 assert(Platform_BeginScene()==1&&begins==1&&flushes==baseFlush);
 assert(Platform_BeginScene()==0&&begins==1&&flushes==baseFlush);
 tick=1001;Platform_Log("[probe] hb f=3540 ms=32\n");
 assert(flushes==baseFlush+1&&s_logBufferLen==0&&consoleWrites==baseConsole);
 Platform_Log("[fault] fixture fault pc=12345678\n");
 assert(flushes==baseFlush+2&&s_logBufferLen==0&&consoleWrites==baseConsole+1);
 SDL_AudioStream stream={0};stream.running=1;stream.spec.channels=2;audio=&stream;audioMode=1;
 X360Audio_ThreadProc(&stream);assert(!audioHeld&&audioTicks>=2);audioMode=0;
 Platform_LogShutdown();
 FILE*f=fopen(argv[1],"rb");assert(f);char contents[2048]={0};fread(contents,1,sizeof(contents)-1,f);fclose(f);
 assert(strstr(contents,"[perf]")&&strstr(contents,"[probe] hb f=")&&strstr(contents,"[fault]")&&strstr(contents,"[CTR Audio]"));
 assert(!strstr(contents,"hb rb"));
 puts("PASS actual Xbox boundaries: detailed probes suppressed, begin-scene never flushes, periodic batches and fault durability retained, audio status logged after releasing the mixer lock");
 return 0;
}
'''
out.with_suffix('.c').write_text(source,encoding='utf8')
subprocess.run(['clang','-O2','-I'+str(stubs),'-I'+str(root/'include'),str(out.with_suffix('.c')),'-o',str(out.with_suffix('.exe'))],check=True)
run = subprocess.run([str(out.with_suffix('.exe')),str(out/'fixture.log')],capture_output=True,text=True)
out.with_suffix('.log').write_text(run.stdout+run.stderr,encoding='utf8')
print(run.stdout+run.stderr,end='')
if run.returncode:raise SystemExit(run.returncode)
