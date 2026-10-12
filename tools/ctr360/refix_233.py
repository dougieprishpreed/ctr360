"""Targeted re-transform of the game/233 unit after macro-designator expansion.

The D233_data.inc elements are OVR233_CS_OP_*_AT(...) macro calls that expand
to C99 array designators ([(OFFSET)] = ...); the source-text scan cannot see
them, so this script expands the macros first (preprocessor), then runs the
normal AST designator pass on the resulting literal designators.

Run: py tools/ctr360/refix_233.py
"""
import importlib.util
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "build-360", "gen")

spec = importlib.util.spec_from_file_location(
    "b360", os.path.join(ROOT, "tools", "ctr360", "build_360_mirror.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def log(s):
    print(s)


m.expand_macro_designators(OUT, log)

# rebuild the 233 wrapper unit exactly like main() does
unity_txt = m.b2s(m.read_bytes(os.path.join(OUT, "game", "game_unity.h")))
inc233 = re.findall(r'#include\s+"(233/[^"]+)"', unity_txt)
wrapper = os.path.join(OUT, "game", "_unit233.c")
body = "#include <common.h>\n" + "".join('#include "%s"\n' % p for p in inc233)
m.write_bytes(wrapper, m.s2b(body))

files = ["game/233/R233.c", "game/233/D233_data.inc"]
ctx = m.Ctx(OUT)
ok = False
for unit, file_list, dump in m.dump_units_batched([("game/_unit233.c", files)], OUT, "clang", log):
    if dump is None:
        log("DUMP FAILED for unit")
        sys.exit(2)
    for target in file_list:
        log("== transform: %s" % target)
        edits, skipped, unions, fixups = m.collect_edits_for_file(
            dump, m.rel_norm(target), ctx, log, 0, macro_only=False)
        log("   edits: %d  skipped: %d" % (len(edits), len(skipped)))
        if edits:
            p = os.path.join(OUT, target)
            buf = m.read_bytes(p)
            buf = m.apply_edits(buf, edits, log, target)
            m.write_bytes(p, buf)
            ctx.forget(m.rel_norm(target))
    ok = True

sys.exit(0 if ok else 2)
