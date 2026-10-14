"""Execute generated union startup assignments using an actual Clang AST.

The converter must preserve explicit integer/float leaves, array entries,
casts and pointers, and the Xbox unity must include/call the generated body.
"""
from pathlib import Path
import argparse
import inspect
import json
import re
import subprocess

import build_360_mirror as mirror

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/mirror-fixups'
out.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--old-literals', action='store_true', help='negative control: omit scalar leaves as the old converter did')
args = parser.parse_args()
if args.old_literals:
    old = inspect.getsource(mirror.flatten_fixups)
    condition = 'if is_implicit(node) or (not explicit and (rec or t.strip().endswith("]") or node.get("kind") == "InitListExpr")):'
    assert condition in old
    exec(old.replace(condition, 'if not explicit:'), mirror.__dict__)
fixture = r'''
#include <assert.h>
#include <stdio.h>
struct Payload { void *ptr; unsigned short color; short life; int type;
 float gain; int samples[3]; };
union Choice { char storage[64]; struct Payload active; };
int target;
union Choice values = {.active={.ptr=&target,.color=0xa1,.life=7,.type=1,
 .gain=1.25f,.samples={3,-4,19}}};
'''
(out / 'fixture.c').write_text(fixture)
run = subprocess.run(['clang', '-Xclang', '-ast-dump=json', '-fsyntax-only',
                      'fixture.c'], cwd=out, capture_output=True, text=True, check=True)
ast = json.loads(run.stdout)
mirror.annotate(ast, {'cur': 'fixture.c'})
ctx = mirror.Ctx(str(out))
log = lambda text: None
edits, skipped, unions, fixups = mirror.collect_edits_for_file(ast, 'fixture.c', ctx, log, False)
assert not skipped, skipped
assert len(fixups) == (4 if args.old_literals else 8), fixups
converted = mirror.apply_edits((out/'fixture.c').read_bytes(), edits, log, 'fixture.c').decode()
body = '\n'.join(item['stmt'] for item in fixups)
if not args.old_literals:
    assert 'values.active.type = 1;' in body and 'values.active.gain = 1.25f;' in body
main = r'''
int main(void){
 assert(values.active.life==0 && values.active.type==0);
 ApplyFixups();
 assert(values.active.ptr==&target && values.active.color==0xa1);
 printf("converted values life=%d type=%d gain=%.2f samples=%d,%d,%d\n",values.active.life,values.active.type,values.active.gain,
  values.active.samples[0],values.active.samples[1],values.active.samples[2]);fflush(stdout);
 assert(values.active.life==7 && values.active.type==1 && values.active.gain==1.25f);
 assert(values.active.samples[0]==3 && values.active.samples[1]==-4 && values.active.samples[2]==19);
 puts("PASS actual AST conversion and C89 execution: pointers, casts, integer/float leaves and array values preserved");
 return 0;
}
'''
path = out / 'converted.c'
path.write_text(converted + '\nvoid ApplyFixups(void){\n' + body + '\n}\n' + main)
subprocess.run(['clang', '-std=c89', '-pedantic-errors', str(path), '-o', str(out/'fixture.exe')], check=True)
result = subprocess.run([str(out/'fixture.exe')], capture_output=True, text=True)
if args.old_literals:
    assert result.returncode != 0 and 'life=7 type=0 gain=0.00 samples=0,-4,0' in result.stdout
else:
    assert result.returncode == 0, result.stdout+result.stderr
name = 'negative' if args.old_literals else 'fixture'
(out/(name+'.log')).write_text(result.stdout+result.stderr)
(out/(name+'-assignments.json')).write_text(json.dumps(fixups, indent=2)+'\n')
print(result.stdout, end='')
if args.old_literals:
    print('PASS negative control reproduces missing integer/float/array assignments')
entry = (root/'platform/xbox360/main_xbox360.c').read_text()
assert '#include "game/_ctr360_fixups.c"' in entry
assert entry.index('Ctr360_ApplyStaticFixups();') < entry.index('NativeAssets_Init(basePath)')
assert entry.count('Ctr360_ApplyStaticFixups();') == 1
print('PASS Xbox startup includes and applies generated assignments before asset/game initialization')
