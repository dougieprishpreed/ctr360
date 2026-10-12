"""ctr360: stage the debug database as default.xdb so Xenia (which looks up
<xex name>.xdb) can load guest symbols. The XDK writes it as ctr360.xdb into
the project's dist folder."""
import io
import os
import shutil

ROOT = r'F:\downloads\temp\python\hermes\ctrport\ctr360'

p = os.path.join(ROOT, 'tools', 'ctr360', 'build_xex.sh')
s = io.open(p, encoding='utf-8').read()

old = """    # Xenia loads symbols from <xex name>.xdb; stage it under the same name so
    # function-level tracing and the debugger UI have the guest's symbols.
    BUILT_XDB="$ROOT/build-360/xex/$CONFIG/ctr360.xdb"
    [ -f "$BUILT_XDB" ] && cp -f "$BUILT_XDB" "$ROOT/build-360/xex/dist/default.xdb\""""
new = """    # Xenia loads symbols from <xex name>.xdb; stage it under the same name so
    # function-level tracing and the debugger UI have the guest's symbols.
    # The XDK writes it beside the xex in dist/ (Release|Debug/ on some setups).
    for cand in "$ROOT/build-360/xex/dist/ctr360.xdb" "$ROOT/build-360/xex/$CONFIG/ctr360.xdb"; do
        if [ -f "$cand" ]; then
            cp -f "$cand" "$ROOT/build-360/xex/dist/default.xdb"
            break
        fi
    done"""

assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8').write(s)
print('xdb staging fixed in build_xex.sh')

# verify the copy logic works right now
dist = os.path.join(ROOT, 'build-360', 'xex', 'dist')
src = os.path.join(dist, 'ctr360.xdb')
dst = os.path.join(dist, 'default.xdb')
if os.path.isfile(src):
    shutil.copyfile(src, dst)
    print('staged now: %s (%d bytes)' % (dst, os.path.getsize(dst)))
else:
    print('no ctr360.xdb found to stage')
