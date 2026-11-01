"""Exercise the actual xSDK game logger's batching, flushes and thread safety."""
import argparse
import subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[2]
a.out.mkdir(parents=True, exist_ok=True)
stub = a.out / 'xsdk'
stub.mkdir(exist_ok=True)
(stub / 'log.h').write_text('#include <stddef.h>\nvoid xsdk_log_write_bytes(const char *,size_t);\n')
(stub / 'kernel.h').write_text('''#include <pthread.h>
typedef pthread_mutex_t RTL_CRITICAL_SECTION;
typedef void *HANDLE;typedef int NTSTATUS;
static void RtlInitializeCriticalSection(RTL_CRITICAL_SECTION *s){pthread_mutex_init(s,0);}
static void RtlEnterCriticalSection(RTL_CRITICAL_SECTION *s){pthread_mutex_lock(s);}
static void RtlLeaveCriticalSection(RTL_CRITICAL_SECTION *s){pthread_mutex_unlock(s);}
static unsigned RtlTryEnterCriticalSection(RTL_CRITICAL_SECTION *s){return !pthread_mutex_trylock(s);}
''')
# The watchdog's thread is held until the test starts it; a modelled 500 ms sleep takes 1 ms.
(stub / 'thread.h').write_text('''#include <stdint.h>
#include <unistd.h>
typedef uint32_t (*XsdkThreadEntry)(void *);
static XsdkThreadEntry watchdogEntry;static unsigned watchdogHardwareThread;
static NTSTATUS xsdk_thread_create_on(HANDLE *h,uint32_t stack,XsdkThreadEntry entry,void *context,uint32_t hw)
{(void)h;(void)stack;(void)context;watchdogEntry=entry;watchdogHardwareThread=hw;return 0;}
static NTSTATUS xsdk_thread_sleep(uint32_t ms){usleep(ms*2);return 0;}
''')
headers = a.out / 'platform'
headers.mkdir(exist_ok=True)
(headers / 'native_log.h').write_text((root/'include/platform/native_log.h').read_text().replace(
    '#include <macros.h>', '#define CTR_PRINTF_FORMAT(a,b)'))
c = r'''
#define _DEFAULT_SOURCE
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <pthread.h>
static char output[200000];static size_t used;static unsigned writes,tick;
unsigned GetTickCount(void){return tick;}
struct GameTracker{short levelID;unsigned gameMode1,gameMode2;};
static struct GameTracker tracker={29,0x00180000,0x400};
static struct{struct GameTracker *gGT;}sdataStorage={&tracker};
#define sdata (&sdataStorage)
unsigned Platform_TraceClassify(const char *s){return !strncmp(s,"muted",5);}
int Platform_TraceEnabled(unsigned c){return !c;}
void xsdk_log_write_bytes(const char *s,size_t n){
 assert(used+n<sizeof(output));memcpy(output+used,s,n);used+=n;output[used]=0;
 writes+=(unsigned)((n+510)/511); /* The pinned SDK's synchronous chunks. */
}
#include "platform/xsdk/native_xsdk_log.c"
static void *watchdog(void *arg){(void)arg;watchdogEntry(0);return 0;}
static int waitFor(const char *text){for(int i=0;i<4000;i++){if(strstr(output,text))return 1;usleep(500);}return 0;}
static void *worker(void *arg){
 unsigned id=(unsigned)(uintptr_t)arg;
 for(unsigned i=0;i<250;i++)Platform_Log("thread=%u line=%u\n",id,i);
 return 0;
}
int main(void){
 Platform_LogInit("test");
 Platform_Log("routine\n");assert(writes==0);
 Platform_LogWarn("warn\n");assert(!strcmp(output,"routine\nwarn\n"));
 Platform_Log("[boot] checkpoint\n");assert(strstr(output,"checkpoint\n"));
 unsigned before=writes;Platform_Log("muted text\n");Platform_LogFlush();assert(writes==before);
 Platform_Log("timed\n");assert(writes==before);tick=1000;Platform_Log("next\n");assert(writes>before);
 before=writes;
 for(unsigned i=0;i<100;i++)Platform_Log("short line %u\n",i);
 Platform_LogFlush();assert(writes-before<10);
 pthread_t threads[4];
 for(uintptr_t i=0;i<4;i++)assert(!pthread_create(&threads[i],0,worker,(void *)i));
 for(unsigned i=0;i<4;i++)assert(!pthread_join(threads[i],0));
 Platform_LogShutdown();
 for(unsigned id=0;id<4;id++)for(unsigned i=0;i<250;i++){
  char line[80];snprintf(line,sizeof(line),"thread=%u line=%u\n",id,i);
  char *found=strstr(output,line);assert(found && !strstr(found+strlen(line),line));
 }
 before=writes;Platform_Log("pending\n");Platform_LogError("error\n");assert(writes>before && strstr(output,"pending\nerror\n"));
 xsdkGameLogLastFlush=UINT32_MAX-500;tick=600;
 before=writes;Platform_Log("wrap\n");assert(writes>before);
 /* Watchdog: started on its own hardware thread, silent while frames beat,
  * then the stuck place after 3 s without one, buffered lines first, and
  * again 10 s later. */
 assert(watchdogEntry && watchdogHardwareThread==5);
 Platform_WatchStage("bucket-enter");Platform_WatchTick((const void *)(uintptr_t)0x8215e380u);
 pthread_t dog;assert(!pthread_create(&dog,0,watchdog,0));
 for(unsigned i=0;i<400;i++){Platform_WatchBeat();usleep(250);}
 assert(!strstr(output,"[watchdog]"));
 Platform_Log("last line before the hang\n");assert(!strstr(output,"last line before the hang"));
 assert(waitFor("[watchdog] no frame for 3000 ms"));
 char *hang=strstr(output,"[watchdog] no frame for 3000 ms");
 assert(strstr(hang,"stage=bucket-enter tick=8215e380 level=29 mode1=00180000 mode2=00000400\n"));
 char *last=strstr(output,"last line before the hang\n");assert(last && last<hang);
 assert(waitFor("[watchdog] no frame for 13000 ms"));
 assert(!strstr(output,"no frame for 3500 ms") && !strstr(output,"no frame for 8000 ms"));
 puts("PASS: actual logger batches short writes, preserves 1000 concurrent lines, filters traces, flushes warnings/errors/boot/exit/time/wrap; the hang watchdog stays silent while frames beat, then logs the stuck stage and tick after 3 s and every 10 s");
 return 0;
}
'''
source = a.out / 'logger.c'
source.write_text(c)
exe = (a.out / 'logger-test').resolve()
subprocess.run(['cc', '-std=c17', '-pthread', '-I'+str(a.out), '-I'+str(root),
                '-I'+str(root/'include'), str(source), '-o', str(exe)], check=True)
subprocess.run([str(exe)], check=True)

# The freeze trace: in a FREEZE_TRACE=1 build, each line of a window goes to
# game:/freeze_trace.log with an fsync of its own; stages only in its close
# frames; nothing outside a window; and no file at all in other builds.
trace = c[:c.index('#include "platform/xsdk/native_xsdk_log.c"')] + r'''
#include <unistd.h>
static unsigned syncs,traceWrites;
static ssize_t countedWrite(int fd,const void *b,size_t n){traceWrites++;return write(fd,b,n);}
static int countedFsync(int fd){syncs++;return fsync(fd);}
#define write countedWrite
#define fsync countedFsync
#include "platform/xsdk/native_xsdk_log.c"
#undef write
#undef fsync
static char text[4096];
static const char *after(const char *from,const char *line){const char *at=strstr(from,line);assert(at);return at+strlen(line);}
int main(void){
 Platform_LogInit("trace");
 Platform_FreezeTrace("before");Platform_WatchStage("outside");Platform_WatchBeat();
 Platform_FreezeTraceOpen("podium",3,1);
 Platform_FreezeTrace("event %d",1);
 Platform_WatchStage("render-frame");Platform_WatchBeat();
 Platform_WatchStage("present");Platform_FreezeTrace("event %d",2);
 Platform_WatchBeat();Platform_WatchBeat();
 Platform_FreezeTrace("after");
 Platform_FreezeTraceOpen("again",2,0);Platform_WatchBeat();
 FILE *f=fopen("game:/freeze_trace.log","rb");
#if CTR360_FREEZE_TRACE
 assert(f);text[fread(text,1,sizeof(text)-1,f)]=0;fclose(f);
 const char *at=text;
 at=after(at,"open: podium, for 3 frames, stages for 1\n");at=after(at,"event 1\n");at=after(at,"stage render-frame\n");
 at=after(at,"frame shown: level=29 mode1=00180000 mode2=00000400\n");at=after(at,"event 2\n");
 at=after(at,"frame shown");at=after(at,"frame shown");at=after(at,"closed\n");
 at=after(at,"open: again, for 2 frames, stages for 0\n");at=after(at,"frame shown");
 assert(!strstr(text,"before") && !strstr(text,"outside") && !strstr(text,"stage present") && !strstr(text,"after\n"));
 unsigned lines=0;for(const char *s=text;*s;s++)lines+=*s=='\n';
 assert(lines==10 && traceWrites==lines && syncs==lines);
 puts("PASS: actual freeze trace writes and syncs each line of its windows, stages in the close frames only, nothing outside them");
#else
 assert(!f && traceWrites==0);
 puts("PASS: builds without FREEZE_TRACE=1 write no freeze trace");
#endif
 return 0;
}
'''
work = a.out / 'trace-run'
(work / 'game:').mkdir(parents=True, exist_ok=True)
for name, flags in (('trace-on', ['-DCTR360_FREEZE_TRACE=1']), ('trace-off', [])):
    (work / 'game:' / 'freeze_trace.log').unlink(missing_ok=True)
    source = a.out / (name + '.c')
    source.write_text(trace)
    exe = (a.out / name).resolve()
    subprocess.run(['cc', '-std=c17', '-pthread', *flags, '-I'+str(a.out), '-I'+str(root),
                    '-I'+str(root/'include'), str(source), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, cwd=work)
