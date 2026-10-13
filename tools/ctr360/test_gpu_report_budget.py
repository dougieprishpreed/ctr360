"""Execute the GPU error budget, including a sustained malformed-packet flood."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/gpu-report-budget'
out.mkdir(parents=True, exist_ok=True)
source = (root / 'platform/native_gpu.c').read_text()
start = source.index('static int NativeGpu_PacketReportBudget(')
begin = source.index('{', start)
end, depth = begin + 1, 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
body = source[start:end]
c = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <assert.h>
#include <string.h>
typedef uint32_t u32;
static u32 vblank;static unsigned summaries, lastSuppressed[4];
static int Platform_GetVBlankCount(void){return (int)vblank;}
static void Platform_Log(const char*fmt,...){
 char line[128];va_list ap;va_start(ap,fmt);vsnprintf(line,sizeof line,fmt,ap);va_end(ap);
 unsigned kind,count;assert(sscanf(line,"[CTR GPU] packet reports kind=%u suppressed=%u",&kind,&count)==2);
 assert(kind<4 && count);lastSuppressed[kind]=count;summaries++;
}
'''+body+r'''
int main(void){
 unsigned allowed[4]={0};
 for(unsigned i=0;i<100000;i++)allowed[1]+=NativeGpu_PacketReportBudget(1);
 /* The byte dump and other fault samples retain their own quota. */
 for(unsigned kind=0;kind<4;kind++)if(kind!=1)
  for(unsigned i=0;i<100000;i++)allowed[kind]+=NativeGpu_PacketReportBudget(kind);
 for(unsigned kind=0;kind<4;kind++)assert(allowed[kind]==2);
 assert(summaries==0);
 vblank=59;assert(!NativeGpu_PacketReportBudget(3));assert(summaries==0);
 vblank=60;assert(NativeGpu_PacketReportBudget(3));assert(summaries==4);
 for(unsigned kind=0;kind<3;kind++)assert(lastSuppressed[kind]==99998);
 assert(lastSuppressed[3]==99999);
 assert(NativeGpu_PacketReportBudget(3));assert(!NativeGpu_PacketReportBudget(3));
 vblank=120;assert(NativeGpu_PacketReportBudget(0));assert(summaries==5&&lastSuppressed[3]==1);
 vblank=0xffffffe0u;assert(NativeGpu_PacketReportBudget(0));
 assert(NativeGpu_PacketReportBudget(0));assert(!NativeGpu_PacketReportBudget(0));
 vblank=28;assert(NativeGpu_PacketReportBudget(0));assert(lastSuppressed[0]==1);
 puts("PASS actual GPU report budget: 400000 faults -> 8 detailed samples, independent byte-dump quota, counted summaries, quiet recovery and VBlank counter wrap");
}
'''
(out/'fixture.c').write_text(c)
subprocess.run(['clang','-O2',str(out/'fixture.c'),'-o',str(out/'fixture.exe')],check=True)
run = subprocess.run([str(out/'fixture.exe')], capture_output=True, text=True, check=True)
(out/'fixture.log').write_text(run.stdout)
print(run.stdout,end='')
