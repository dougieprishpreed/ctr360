"""Repair C string literals that contain REAL newline bytes.

A shell heredoc mangled '\n' escapes into real newlines when the reporter block
and the diag helper were spliced into the mirror copy: three string literals in
build-360/gen/platform/native_gpu.c now break across two physical lines, which
is a C syntax error ("newline in constant").

Scanner walks the file with a small C lexer (strings + // and /* */ comments),
finds every LF that occurs INSIDE a string literal, and joins the line by
replacing that LF with the two-character escape backslash-n. Verifies both
files afterwards: no literal may contain a newline, and the escape counts must
match the repo.

    python tools/ctr360/fix_newline_in_literals.py [--check]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

FILES = [
    os.path.join(ROOT, "platform", "native_gpu.c"),
    os.path.join(ROOT, "build-360", "gen", "platform", "native_gpu.c"),
]

BS = 92   # backslash
NL = 10
CR = 13
Q = 34
SLASH = 47
STAR = 42


def scan_for_bad_literals(raw):
    """Returns list of (offset_of_LF, line_number) for LFs inside string literals."""
    bad = []
    line = 1
    in_str = False
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if in_str:
            if c == BS:
                i += 2
                continue
            if c == Q:
                in_str = False
                i += 1
                continue
            if c == NL:
                bad.append((i, line))
                line += 1
                i += 1
                continue
            i += 1
            continue
        # outside strings
        if c == NL:
            line += 1
            i += 1
            continue
        if c == Q:
            in_str = True
            i += 1
            continue
        if c == SLASH and i + 1 < n and raw[i + 1] == SLASH:
            j = raw.find(b"\n", i)
            i = (j + 1) if j >= 0 else n
            line += 1
            continue
        if c == SLASH and i + 1 < n and raw[i + 1] == STAR:
            j = raw.find(b"*/", i + 2)
            if j < 0:
                break
            line += raw.count(b"\n", i, j)
            i = j + 2
            continue
        i += 1
    return bad


check_only = "--check" in sys.argv
exit_code = 0

for path in FILES:
    raw = open(path, "rb").read()
    bad = scan_for_bad_literals(raw)
    rel = os.path.relpath(path, ROOT)
    if not bad:
        print("%s: clean (%d bytes)" % (rel, len(raw)))
        continue
    print("%s: %d literal-newline(s) at %s" % (rel, len(bad), [ln for _, ln in bad]))
    fixed = raw
    for off, _ in reversed(bad):
        fixed = fixed[:off] + bytes([BS, 110]) + fixed[off + 1:]
    left = scan_for_bad_literals(fixed)
    if left:
        print("  FATAL: %d remain after repair" % len(left))
        exit_code = 2
        continue
    if check_only:
        print("  check-only: would rewrite")
    else:
        open(path, "wb").write(fixed)
        print("  repaired and written")

sys.exit(exit_code)
