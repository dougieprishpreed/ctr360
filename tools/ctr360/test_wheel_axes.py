"""Run the actual wheel-axis builders on the scalar GTE, including zero axes.

Projection uses the actual loop with only sprite selection/emission stubbed.
An archived pre-fix source, when present, checks unchanged ordinary geometry
and reproduces the divide-by-zero as a negative control in a child process.
"""
from pathlib import Path
import ctypes
import re
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/wheel-axes-contract'
out.mkdir(parents=True, exist_ok=True)
source = (root / 'game/DrawTires.c').read_text()
before = root / 'build-360/results/20261012-hardware-ripper-roo/DrawTires-before.c'


def function(text, name):
    match = re.search(r'^.*\b' + name + r'\([^;]*?\)\s*\n\{', text, re.M)
    assert match, name
    start = text.index('{', match.start())
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end] + '\n'


c = r'''
#include <common.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct Data data;
struct sData sdata_static;
'''
for name in ['DrawTiresSolid_CountLeadingSignBits', 'Unknown_8006ef98',
             'DrawTires_ReciprocalLength', 'DrawTires_HasWheelAxes',
             'DrawTiresSolid_BuildWheelAxes', 'DrawTiresReflection_BuildWheelAxes']:
    c += function(source, name)
for style in ['Solid', 'Reflection']:
    typename = 'DrawTires' + style + 'ProjectedWheel'
    c += re.search(r'struct ' + typename + r'\s*\{.*?\};', source, re.S)[0] + '\n'
    prefix = 'DrawTires' + style
    c += f'''
static void {prefix}_LoadCorner(struct DrawTiresScratch *s,int v,int w,int a,int r) {{}}
static struct {typename} {prefix}_SelectProjectedWheel(struct DrawTiresScratch *s,int w) {{
 struct {typename} result; memset(&result,0,sizeof result); return result;
}}
'''
    if style == 'Solid':
        c += f'static int {prefix}_EmitProjectedWheel(struct DrawTiresScratch *s,struct {typename} *w,struct PrimMem *p,int *count) {{ (*count)++; return 1; }}\n'
    else:
        c += f'static void {prefix}_EmitProjectedWheel(struct DrawTiresScratch *s,struct {typename} *w,struct PrimMem *p,int *count,int i) {{ (*count)++; }}\n'
    c += function(source, prefix + '_ProjectWheelQuads')

if before.exists():
    old = before.read_text()
    c += '#define HAVE_LEGACY 1\n'
    for style in ['Solid', 'Reflection']:
        name = 'DrawTires' + style + '_BuildWheelAxes'
        c += function(old, name).replace(name, 'Legacy' + style)

c += r'''
static void setup(struct DrawTiresScratch *s,int x,int y,int z,int rx,int ry,int rz) {
 memset(s,0,sizeof *s);
 s->wheelSize.word=4096;
 for(int i=0;i<4;i++) {
  s->wheelLocal[i].center.x=x;s->wheelLocal[i].center.y=y;s->wheelLocal[i].center.z.word=z;
  s->wheelLocal[i].rim.x=rx;s->wheelLocal[i].rim.y=ry;s->wheelLocal[i].rim.z.word=rz;
 }
 for(int i=0;i<32;i++) CTC2(0,i);
 CTC2(4096,16);CTC2(4096,18);CTC2(4096,20);
 CTC2(4096,8);CTC2(4096,10);CTC2(4096,12);
}
static void build(struct DrawTiresScratch *s,int reflected) {
 if(reflected)DrawTiresReflection_BuildWheelAxes(s);else DrawTiresSolid_BuildWheelAxes(s);
}
static int project(struct DrawTiresScratch *s,int reflected) {
 int count=0;struct PrimMem p;memset(&p,0,sizeof p);
 if(reflected)assert(DrawTiresReflection_ProjectWheelQuads(s,&p,&count));
 else assert(DrawTiresSolid_ProjectWheelQuads(s,&p,&count));
 return count;
}
int main(int argc,char **argv) {
 struct DrawTiresScratch s,old;
#ifdef HAVE_LEGACY
 if(argc>1) {setup(&s,1024,0,0,4096,0,0);LegacySolid(&s);return 0;}
#endif
 assert(DrawTires_ReciprocalLength(0)==0);
 assert(DrawTires_ReciprocalLength(1)==65536);
 assert(DrawTires_ReciprocalLength(256)==256);
 for(int reflection=0;reflection<2;reflection++) {
  setup(&s,0,0,0,4096,0,0);build(&s,reflection);
  for(int i=0;i<4;i++)assert(!DrawTires_HasWheelAxes(&s,i));
  assert(project(&s,reflection)==0);
  setup(&s,1024,0,0,4096,0,0);build(&s,reflection);
  for(int i=0;i<4;i++)assert(!DrawTires_HasWheelAxes(&s,i));
  assert(project(&s,reflection)==0);
  setup(&s,100,40,200,4096,0,200);
  memset(&s.wheelLocal[3].center,0,sizeof s.wheelLocal[3].center);
  build(&s,reflection);
  assert(!DrawTires_HasWheelAxes(&s,3));
  for(int i=0;i<3;i++)assert(DrawTires_HasWheelAxes(&s,i));
  assert(project(&s,reflection)==3);
  for(int n=0;n<256;n++) {
   setup(&s,20+n*7,30+n*3,1000+n*11,4096,0,100+n);
   build(&s,reflection);
   for(int i=0;i<4;i++)assert(DrawTires_HasWheelAxes(&s,i));
#ifdef HAVE_LEGACY
   setup(&old,20+n*7,30+n*3,1000+n*11,4096,0,100+n);
   if(reflection)LegacyReflection(&old);else LegacySolid(&old);
   assert(memcmp(&s,&old,sizeof s)==0);
#endif
  }
 }
 puts("PASS actual solid/reflected wheel math: zero view, parallel rim, isolated wheel, 512 ordinary poses");
 return 0;
}
'''
(out / 'fixture.c').write_text(c, encoding='utf-8')
exe = out / 'fixture.exe'
subprocess.run(['clang', '-O0', '-DCTR_NATIVE', '-D_Static_assert(x,y)=',
                '-Wno-everything', '-I', str(root / 'include'), '-I', str(root),
                str(out / 'fixture.c'), str(root / 'platform/native_inline_c.c'),
                str(root / 'platform/native_gte_core.c'), '-o', str(exe)], check=True)
subprocess.run([str(exe)], check=True)
if before.exists():
    if hasattr(ctypes, 'windll'):
        ctypes.windll.kernel32.SetErrorMode(0x8003)
    legacy = subprocess.run([str(exe), 'legacy-zero'], capture_output=True)
    assert legacy.returncode != 0, 'old wheel builder did not reproduce its zero-axis failure'
    print(f'PASS archived wheel builder fails on parallel rim: {legacy.returncode:#x}')
