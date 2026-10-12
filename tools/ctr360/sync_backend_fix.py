"""Sync specific text edits from the repo backend files into the build-360/gen
mirror copy, which holds a C89-hoisted variant of the same file.

Method: find the anchor substring, then determine the whole physical line that
contains it (rfind/find of LF around the match - no line-ending assumptions and
no .count() on CRLF-joined strings). For each file every edit must match
exactly once; a file is written only when ALL of its edits matched.

    python tools/ctr360/sync_backend_fix.py [--check]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")

NK = 'NativeGpu_ConvertFormatIndexed'
NK1 = 'NativeGpu_ConvertFormat'

HELPER_LINES = [
    "/* Formats into dst and validates the conversion. If the CRT refuses the",
    " * format (the frame-13 '%zx' incident), dst is filled with plain text so the",
    " * caller's report still goes out. Returns the snprintf result for callers",
    " * that want to know. */",
    "internal int NativeGpu_ConvertFormat(char *dst, size_t dstSize, const char *fmt, unsigned value)",
    "{",
    "\tconst int written = snprintf(dst, dstSize, fmt, value);",
    "",
    "\tif ((written < 0) || ((size_t)written >= dstSize))",
    "\t{",
    '\t\tsnprintf(dst, dstSize, "fmt-fail");',
    "\t}",
    "",
    "\treturn written;",
    "}",
    "",
    '/* Two-argument variant for "name%d+0x%08x" region strings. */',
    "internal int NativeGpu_ConvertFormatIndexed(char *dst, size_t dstSize, const char *fmt, unsigned index, unsigned value)",
    "{",
    "\tconst int written = snprintf(dst, dstSize, fmt, index, value);",
    "",
    "\tif ((written < 0) || ((size_t)written >= dstSize))",
    "\t{",
    '\t\tsnprintf(dst, dstSize, "fmt-fail");',
    "\t}",
    "",
    "\treturn written;",
    "}",
    "",
    "/* One-shot plain-specifier trace for diagnosing a print-path lockup: if a",
    " * reporter never lands, the last DIAG line in the log localizes the stall.",
    " * Printed once per run (static flag), only on the error path. */",
    "internal void NativeGpu_DiagTraceOnce(const char *stage, const void *packet, int extra)",
    "{",
    "\tstatic int s_diagTraceWritten = 0;",
    "",
    "\tif (s_diagTraceWritten)",
    "\t{",
    "\t\treturn;",
    "\t}",
    "\ts_diagTraceWritten = 1;",
    "",
    '\tPlatform_Log("[trace] GPU diag %s packet=%p extra=%d\\n", stage, packet, extra);',
    "}",
    "",
]

COMMENT_LINES = [
    '#define NATIVE_GPU_ERROR_PLAIN(text) Platform_LogError("[CTR GPU] " text)',
    "",
    "/* The XDK CRT's _vsnprintf does not handle the 'z' length modifier ('%zx',",
    " * '%zu'): the character class falls through to CH_OTHER. On the console that",
    " * made the frame-13 error reporter vanish with the walk wedged inside the",
    " * print path, so a diagnostic that could not print made a cosmetic overshoot",
    " * fatal. All error-path formatting now goes through ConvertFormat, which",
    " * checks the return value and substitutes plain text if the conversion ever",
    " * fails again - a broken diagnostic must never block the walk. */",
    "#define NATIVE_GPU_FORMAT_CHECK_LOCKUP_TRACE 0",
]

EDITS = {}

# --- native_gpu.c -----------------------------------------------------------
EDITS["platform/native_gpu.c"] = [
    {
        "kind": "after",
        "anchor": '#define NATIVE_GPU_ERROR(fmt, ...) Platform_LogError("[CTR GPU] [%s] - " fmt, __func__, __VA_ARGS__)',
        "lines": COMMENT_LINES,
    },
    {
        "kind": "before",
        "anchor": "internal void NativeGpu_FormatPointerRegion(char *dst, size_t dstSize, uintptr_t ptr)",
        "lines": HELPER_LINES,
    },
    {
        "kind": "replace",
        "anchor": '\t\t\tsnprintf(dst, dstSize, "pb%d.ot+0x%zx", playerIndex, (size_t)(ptr - start));',
        "lines": ['\t\t\t' + NK + '(dst, dstSize, "pb%d.ot+0x%08x", (unsigned)playerIndex, (unsigned)(ptr - start));'],
    },
    {
        "kind": "replace",
        "anchor": '\t\tsnprintf(dst, dstSize, "ui.ot+0x%zx", (size_t)(ptr - uiStart));',
        "lines": ['\t\t' + NK1 + '(dst, dstSize, "ui.ot+0x%08x", (unsigned)(ptr - uiStart));'],
    },
    {
        "kind": "replace",
        "anchor": '\t\t\tsnprintf(dst, dstSize, "db%d.prim+0x%zx", dbIndex, (size_t)(ptr - primStart));',
        "lines": ['\t\t\t' + NK + '(dst, dstSize, "db%d.prim+0x%08x", (unsigned)dbIndex, (unsigned)(ptr - primStart));'],
    },
    {
        "kind": "replace",
        "anchor": '\t\t\tsnprintf(dst, dstSize, "db%d.ot+0x%zx", dbIndex, (size_t)(ptr - otStart));',
        "lines": ['\t\t\t' + NK + '(dst, dstSize, "db%d.ot+0x%08x", (unsigned)dbIndex, (unsigned)(ptr - otStart));'],
    },
    {
        "kind": "replace",
        "anchor": '\t\t\t\tif (currentPacket != endPacket)\n\t\t\t\t{\n\t\t\t\t\tchar packetRegion[64];\n\t\t\t\t\tNativeGpu_FormatPointerRegion(packetRegion, sizeof(packetRegion), (uintptr_t)basePacket);',
        "lines": ['\t\t\t\tif (currentPacket != endPacket)',
                  '\t\t\t\t{',
                  '\t\t\t\t\tchar packetRegion[64];',
                  '\t\t\t\t\tNativeGpu_DiagTraceOnce("prims-overshoot", (const void *)basePacket, (int)(endPacket - currentPacket));',
                  '\t\t\t\t\tNativeGpu_FormatPointerRegion(packetRegion, sizeof(packetRegion), (uintptr_t)basePacket);'],
    },
]

# --- native_gpu_links.c -----------------------------------------------------
EDITS["platform/native_gpu_links.c"] = [{
    "kind": "fragment",
    "anchor": "GPU link bridge failed to register %s range start=%p size=%zu",
    "lines": ["GPU link bridge failed to register %s range start=%p size=%08x"],
}]

check_only = "--check" in sys.argv


def whole_line_bounds(text, pos):
    """Bounds (start, end) of the physical line containing pos, end exclusive
    of the line terminator; also returns the terminator string."""
    start = text.rfind("\n", 0, pos) + 1
    lf = text.find("\n", pos)
    if lf < 0:
        return start, len(text), ""
    if lf > start and text[lf - 1] == "\r":
        return start, lf - 1, "\r\n"
    return start, lf, "\n"


def do_edit(text, edit):
    """Returns (new_text, problem_or_None)."""
    anchor = edit["anchor"]
    kind = edit["kind"]

    # Resolve the anchor to the exact in-file form: multi-line anchors may be
    # stored with LF or CRLF joinings in the mixed-ending tree file.
    variants = [anchor]
    if "\n" in anchor:
        variants.append(anchor.replace("\n", "\r\n"))
    matches = [v for v in variants if text.count(v) == 1]
    if len(matches) != 1:
        return text, ("anchor matches %s, expected exactly 1: %r"
                      % (", ".join("%d" % text.count(v) for v in variants), anchor[:140]))
    a = matches[0]

    if kind == "fragment":
        return text.replace(a, edit["lines"][0]), None

    if kind == "replace" and "\n" in a:
        sep = "\r\n" if "\r\n" in a else "\n"
        block = sep.join(edit["lines"])
        return text.replace(a, block), None

    pos = text.find(a)
    lstart, lend, eol = whole_line_bounds(text, pos)
    if eol == "":
        return text, "anchor is on the last line (no terminator)"
    if kind in ("before", "after") and not (lstart == pos and lend == pos + len(a)):
        return text, "anchor is not a whole line: %r" % anchor[:140]
    block = eol.join(edit["lines"])
    if kind == "replace":
        return text[:lstart] + block + text[lend:], None
    if kind == "before":
        return text[:lstart] + block + eol + text[lstart:], None
    if kind == "after":
        return text[:lend] + eol + block + text[lend:], None
    return text, "unknown kind %r" % kind


problems = []
writes = []

for rel, edits in EDITS.items():
    path = os.path.join(TREE, rel)
    text = io.open(path, encoding="utf-8", newline="").read()
    file_ok = True
    for i, edit in enumerate(edits):
        text, prob = do_edit(text, edit)
        if prob:
            problems.append("%s edit#%d: %s" % (rel, i, prob))
            file_ok = False
    if file_ok:
        writes.append((path, text))
        print("prepared %s (%d edit(s))" % (rel, len(edits)))

if problems:
    print("FATAL: %d problem(s) - nothing written:" % len(problems))
    for p in problems:
        print("  " + p)
    sys.exit(2)

for path, text in writes:
    if check_only:
        print("check-only: would write %s" % path)
    else:
        io.open(path, "w", encoding="utf-8", newline="").write(text)
        print("wrote %s" % path)

print("sync_backend_fix: ok")
