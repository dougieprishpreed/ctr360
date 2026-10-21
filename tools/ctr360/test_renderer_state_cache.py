"""Exercise the renderer's real constant cache under overlapping bridge writes."""
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
source=r"""
#include <assert.h>
#include <limits.h>
#include "platform/xbox360/native_xbox360_state_cache.h"
static Ctr360ConstantCache cache;
static float gpu[256][4];
static unsigned int uploads;
static void set(unsigned int first,const float *values,unsigned int count) {
    if(Ctr360ConstantsEqual(&cache,first,values,count))return;
    memcpy(gpu[first],values,count*4*sizeof(float));uploads++;
    Ctr360ConstantsRemember(&cache,first,values,count);
}
int main(void) {
    float matrix[16]={1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
    float bridge[4]={0,512,216,1},zero[4]={0,0,0,0};
    unsigned int i;
    assert(!Ctr360ConstantsEqual(&cache,0,zero,1));
    set(0,matrix,4);
    for(i=0;i<10000;i++)set(0,matrix,4);
    assert(uploads==1);
    set(1,bridge,1); /* fullscreen effect overwrites part of the matrix */
    assert(!Ctr360ConstantsEqual(&cache,0,matrix,4));
    set(0,matrix,4);assert(!memcmp(gpu,matrix,sizeof(matrix)));
    assert(uploads==3);
    set(255,zero,1);assert(Ctr360ConstantsEqual(&cache,255,zero,1));
    assert(!Ctr360ConstantsEqual(&cache,255,matrix,2));
    assert(!Ctr360ConstantsEqual(&cache,UINT_MAX,zero,1));
    Ctr360ConstantsRemember(&cache,UINT_MAX,zero,1);
    memset(&cache,0,sizeof(cache)); /* new device cannot inherit old values */
    assert(!Ctr360ConstantsEqual(&cache,0,matrix,4));
    set(0,matrix,4);assert(uploads==5);
    return 0;
}
"""
(root/'build-360/results').mkdir(parents=True,exist_ok=True)
directory=root/'build-360/results/state-cache-test'
directory.mkdir(exist_ok=True)
directory=Path(directory);c=directory/'cache.c';exe=directory/'cache.exe';c.write_text(source)
subprocess.run(['clang','-std=c89','-Wall','-Wextra','-Werror','-I',str(root),str(c),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
print('PASS: redundant uploads, overlapping constants, range limits, device invalidation')
