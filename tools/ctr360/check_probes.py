"""Pre-flight check for the mirror generator's probe/trace injections.

Boot-trace and header-patch probes are injected into the repo sources during a
mirror regen, and the generator ASSERTS that each anchor matches an exact number
of times. A mismatch raises *after* copy_tree but *before* the clang passes, which
leaves a half-transformed mirror whose build then fails with ~100 errors in files
nobody edited - hours of misdirected debugging. This script makes that failure
loud and cheap, BEFORE the regen runs.

Checks every BOOT_TRACE entry that carries a C line:
  * the anchor's line count in the untouched repo source equals `expected`
  * the emitted C line contains exactly one `\\n` escape (no bare backslash-n
    that re.sub would turn into a real newline => MSVC "newline in constant")
  * the emitted C line contains no embedded newline or CR

Usage (chain it with && so a failure stops the pipeline):

    python tools/ctr360/check_probes.py && python tools/ctr360/build_360_mirror.py ...
"""
import importlib.util
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

spec = importlib.util.spec_from_file_location(
    "b360mirror", os.path.join(HERE, "build_360_mirror.py"))
mir = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mir)

BS = chr(92)
NL = chr(10)
CR = chr(13)

problems = []
checked = 0

for entry in mir.BOOT_TRACE:
    rel, anchor, label, expected, when = entry[:5]
    cline = entry[5] if len(entry) > 5 else None
    if not cline:
        continue
    checked += 1
    path = os.path.join(ROOT, rel)
    text = io.open(path, encoding="utf-8", newline="").read()
    sep = CR + NL if (CR + NL) in text else NL
    hits = sum(1 for line in text.split(sep) if anchor in line)
    escapes = cline.count(BS + "n")
    embedded = cline.count(NL) + cline.count(CR)
    if hits != expected:
        problems.append("%s: anchor %r in %s matches %d line(s), expected %d"
                        % (label, anchor, rel, hits, expected))
    if escapes != 1:
        problems.append("%s: emitted C line has %d '\\n' escape(s), expected 1"
                        % (label, escapes))
    if embedded:
        problems.append("%s: emitted C line contains an embedded newline" % label)

print("check_probes: %d probe entries checked, %d problem(s)" % (checked, len(problems)))
for p in problems:
    print("   PROBLEM: " + p)
if problems:
    print("check_probes: FATAL - a probe would abort the mirror regen after copy_tree")
    sys.exit(1)
print("check_probes: ok")
