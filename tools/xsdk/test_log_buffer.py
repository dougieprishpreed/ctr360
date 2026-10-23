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
static void RtlInitializeCriticalSection(RTL_CRITICAL_SECTION *s){pthread_mutex_init(s,0);}
static void RtlEnterCriticalSection(RTL_CRITICAL_SECTION *s){pthread_mutex_lock(s);}
static void RtlLeaveCriticalSection(RTL_CRITICAL_SECTION *s){pthread_mutex_unlock(s);}
''')
headers = a.out / 'platform'
headers.mkdir(exist_ok=True)
(headers / 'native_log.h').write_text((root/'include/platform/native_log.h').read_text().replace(
    '#include <macros.h>', '#define CTR_PRINTF_FORMAT(a,b)'))
c = r'''
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <pthread.h>
static char output[200000];static size_t used;static unsigned writes,tick;
unsigned GetTickCount(void){return tick;}
unsigned Platform_TraceClassify(const char *s){return !strncmp(s,"muted",5);}
int Platform_TraceEnabled(unsigned c){return !c;}
void xsdk_log_write_bytes(const char *s,size_t n){
 assert(used+n<sizeof(output));memcpy(output+used,s,n);used+=n;output[used]=0;
 writes+=(unsigned)((n+510)/511); /* The pinned SDK's synchronous chunks. */
}
#include "platform/xsdk/native_xsdk_log.c"
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
 puts("PASS: actual logger batches short writes, preserves 1000 concurrent lines, filters traces, flushes warnings/errors/boot/exit/time/wrap");
 return 0;
}
'''
source = a.out / 'logger.c'
source.write_text(c)
exe = (a.out / 'logger-test').resolve()
subprocess.run(['cc', '-std=c17', '-pthread', '-I'+str(a.out), '-I'+str(root),
                '-I'+str(root/'include'), str(source), '-o', str(exe)], check=True)
subprocess.run([str(exe)], check=True)
