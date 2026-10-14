"""Execute the actual warpball matrix setup and inspect its packed bytes."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/warpball-matrix'
out.mkdir(parents=True, exist_ok=True)
source = (root / 'game/Vehicle/VehPickupItem.c').read_text()
macro = re.search(r'#define VehPickupItem_SetWarpballMatrixPair\(.*?while \(0\)', source, re.S).group()
setup = '\n'.join(line for line in source.splitlines() if 'VehPickupItem_SetWarpballMatrixPair(&weaponInst->matrix' in line or
                 'VehMatrix_WriteS16(&weaponInst->matrix.m[2][2]' in line)
helper = (root / 'game/Vehicle/VehCommon.h').read_text()
helper = re.search(r'static inline void VehMatrix_WriteS16\([^}]+\}', helper, re.S).group()
c = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef int16_t s16;typedef uint16_t u16;
struct Instance {struct {s16 m[3][3],pad;int t[3];} matrix;};
static void CTR_WriteU16LE(void*p,u16 value){unsigned char*b=p;b[0]=(unsigned char)value;b[1]=(unsigned char)(value>>8);}
static u16 CTR_ReadU16LE(const void*p){const unsigned char*b=p;return b[0]|(u16)b[1]<<8;}
#define CTR_NATIVE 1
#define WARPBALL_MATRIX_IDENTITY_SCALE 4096
'''
c += helper + '\n' + macro + '\n'
c += 'int main(void){struct Instance inst={0};struct Instance*weaponInst=&inst;\n' + setup
c += r'''
 for(int row=0;row<3;row++)for(int col=0;col<3;col++)
  assert(CTR_ReadU16LE(&inst.matrix.m[row][col])==(row==col?4096:0));
 assert(((unsigned char*)inst.matrix.m)[0]==0&&((unsigned char*)inst.matrix.m)[1]==16);
 /* Explicit BE-native old-store image: X/Y shrink by 256, Z stays full. */
 unsigned char old[18]={16,0,0,0,0,0,0,0,16,0,0,0,0,0,0,0,0,16};
 assert(CTR_ReadU16LE(old)==16&&CTR_ReadU16LE(old+8)==16&&CTR_ReadU16LE(old+16)==4096);
 puts("PASS actual warpball setup: all 9 packed rotation entries, identity bytes; prior BE native stores reproduce 1/256 X/Y scale");return 0;
}
'''
(out / 'fixture.c').write_text(c)
subprocess.run(['clang', '-O2', str(out / 'fixture.c'), '-o', str(out / 'fixture.exe')], check=True)
run = subprocess.run([str(out / 'fixture.exe')], text=True, capture_output=True, check=True)
(out / 'fixture.log').write_text(run.stdout)
print(run.stdout, end='')
