"""Run the mirror's mechanical C89 pass as a SEPARATE process, after
build_360_mirror.py has fully exited.

Why this exists: build_360_mirror.py's final apply_text_transforms() call runs
inside main(), but the hoist pass works through a process pool whose writes have
been observed to land after that call, re-introducing C99 `inline` (clang prints
it for __inline) and dropping the stdbool shim. The XDK C compiler rejects
`inline` in C mode (error C2054), so the build fails with ~100 cascading header
errors - and the failure looks like a header problem rather than a pipeline
ordering problem.

Always run this between the mirror regen and the build:

    python tools/ctr360/build_360_mirror.py --root . --out build-360/gen
    python tools/ctr360/finalize_mirror.py build-360/gen
    cp platform/xbox360/*.c build-360/gen/platform/xbox360/
    bash tools/ctr360/build_xex.sh Release
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIRROR = sys.argv[1] if len(sys.argv) > 1 else "build-360/gen"

spec = importlib.util.spec_from_file_location(
    "b360mirror", os.path.join(HERE, "build_360_mirror.py"))
mir = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mir)

mirror = os.path.abspath(MIRROR)
mir.apply_text_transforms(mirror, lambda m: sys.stdout.write("[finalize] " + m + "\n"))

# verification: no bare C99 `inline` may survive anywhere in the mirror
import re
bad = []
for dirpath, dirnames, filenames in os.walk(mirror):
    dirnames[:] = [d for d in dirnames if d != ".git"]
    for fn in filenames:
        if not fn.endswith((".c", ".h", ".inc")):
            continue
        p = os.path.join(dirpath, fn)
        t = mir.b2s(mir.read_bytes(p))
        n = len(re.findall(r"\binline\b", t))
        if n:
            bad.append((os.path.relpath(p, mirror), n))

# C99 designators (.field = / [idx] = in initializers) must be resolved by the
# pipeline's clang passes; if the passes raced the mirror writes, files come back
# byte-identical to the repo and the XDK rejects them (C2059 syntax error : '.').
leftovers = mir.scan_designator_lines(mirror)
if leftovers:
    print("[finalize] FATAL: %d file(s) still contain C99 designators:" % len(leftovers))
    for rel, hits in list(leftovers.items())[:10]:
        print("   %s (%d line(s), first at %d)" % (rel, len(hits), hits[0][0]))
    sys.exit(4)
print("[finalize] ok: no C99 designators left in the mirror")

shim = os.path.join(mirror, "include", "stdbool.h")
print("[finalize] stdbool.h shim present:", os.path.exists(shim))
if bad:
    print("[finalize] FATAL: bare 'inline' still present in %d file(s):" % len(bad))
    for rel, n in bad[:10]:
        print("   %s (%d)" % (rel, n))
    sys.exit(3)
print("[finalize] ok: every mirrored source uses __inline")
