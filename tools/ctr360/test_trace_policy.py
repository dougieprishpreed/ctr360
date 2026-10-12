"""Classify the actual hardware log using the actual trace implementation."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/trace-policy-contract'
out.mkdir(exist_ok=True)
stubs = out / 'include'
(stubs / 'platform').mkdir(parents=True, exist_ok=True)
(stubs / 'macros.h').write_text('#define CTR_PRINTF_FORMAT(a,b)\n')
(stubs / 'platform/native_perf.h').write_text('')
source = r'''
#include <stdio.h>
#include <assert.h>
'''
source += '#include "' + (root / 'platform/native_trace.c').as_posix() + '"\n'
source += r'''
int main(int argc,char **argv){
 char line[8192];int essential=0,detail=0,total=0;FILE*f;
 assert(!Platform_TraceEnabled(CTR_TRACE_VRAM|CTR_TRACE_WATCH));
 assert(Platform_TraceClassify("[probe] hb f=3540 ms=32") == CTR_TRACE_ESSENTIAL);
 assert(Platform_TraceClassify("[probe] hb rb f=3540 step=draw-exit") == CTR_TRACE_WATCH);
 assert(Platform_TraceClassify("[probe] hb render f=3540 step=enter") == CTR_TRACE_WATCH);
 assert(Platform_TraceClassify("[probe] hb terrain-bucket f=3540") == CTR_TRACE_WATCH);
 assert(Platform_TraceClassify("[probe] hb prim-guard invalid pointer") == CTR_TRACE_ESSENTIAL);
 assert(Platform_TraceClassify("[fault] TOP-LEVEL") == CTR_TRACE_ESSENTIAL);
 assert(Platform_TraceClassify("[load] hub reload") == CTR_TRACE_ESSENTIAL);
 assert(Platform_TraceClassify("[trace] UpdateVRAM: enter rectCount=2") == CTR_TRACE_VRAM);
 assert(argc==2);f=fopen(argv[1],"rb");assert(f);
 while(fgets(line,sizeof line,f)){
  unsigned c=Platform_TraceClassify(line);total++;
  if(c==CTR_TRACE_ESSENTIAL)essential++;
  else if(!Platform_TraceEnabled(c))detail++;
 }
 fclose(f);
 printf("PASS actual trace classifier: hardware log lines=%d essential=%d opt-in detail=%d; sparse heartbeat/guards/faults/load transitions retained\n",total,essential,detail);
 return 0;
}
'''
out.with_suffix('.c').write_text(source,encoding='utf8')
subprocess.run(['clang','-O2','-I'+str(stubs),'-I'+str(root/'include'),str(out.with_suffix('.c')),'-o',str(out.with_suffix('.exe'))],check=True)
run = subprocess.run([str(out.with_suffix('.exe')),str(root/'build-360/results/20261012-hardware-user/ctr360.log')],capture_output=True,text=True,check=True)
out.with_suffix('.log').write_text(run.stdout,encoding='utf8')
print(run.stdout,end='')
