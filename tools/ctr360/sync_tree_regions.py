"""Splice the repo's FormatPointerRegion + overshoot reporter into the mirror
copy of platform/native_gpu.c.

The mirror is a C89-hoisted variant with mixed line endings, so whole regions
are replaced by structure (function start line -> first column-0 '}' line; if
block -> closing brace line) and re-emitted with the EOL of the replaced
region's first line. Replacement text below is written in the mirror's own
style (declarations hoisted to block top).

    python tools/ctr360/sync_tree_regions.py [--check]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen", "platform", "native_gpu.c")

FUNC_NEW = [
 "internal void NativeGpu_FormatPointerRegion(char *dst, size_t dstSize, uintptr_t ptr)",
 "{",
 "\tstruct GameTracker *gGT;",
 "\tstruct PushBuffer *pb;",
 "\tstruct PushBuffer *uiPB;",
 "\tstruct DB *db;",
 "\tuintptr_t start;",
 "\tuintptr_t end;",
 "\tuintptr_t uiStart;",
 "\tuintptr_t uiEnd;",
 "\tuintptr_t primStart;",
 "\tuintptr_t primEnd;",
 "\tuintptr_t otStart;",
 "\tuintptr_t otEnd;",
 "\tint playerIndex;",
 "\tint dbIndex;",
 "",
 '\tNativeGpu_DiagTraceOnce("region-enter", (const void *)ptr, 0);',
 "",
 "\tif ((sdata == NULL) || (sdata->gGT == NULL))",
 "\t{",
 '\t\tsnprintf(dst, dstSize, "no-gGT");',
 "\t\treturn;",
 "\t}",
 "",
 "\tgGT = sdata->gGT;",
 '\tNativeGpu_DiagTraceOnce("region-gGT", (const void *)gGT, 0);',
 "",
 "\tfor (playerIndex = 0; playerIndex < 4; playerIndex++)",
 "\t{",
 "\t\tpb = &gGT->pushBuffer[playerIndex];",
 "\t\tstart = (uintptr_t)pb->ptrOT;",
 "\t\tend = (uintptr_t)pb->renderBucketOTRangeEnd;",
 "\t\tif ((start != 0) && (end != 0) && (ptr >= start) && (ptr <= end))",
 "\t\t{",
 '\t\t\tNativeGpu_ConvertFormatIndexed(dst, dstSize, "pb%d.ot+0x%08x", (unsigned)playerIndex, (unsigned)(ptr - start));',
 '\t\t\tNativeGpu_DiagTraceOnce("region-pb", dst, 0);',
 "\t\t\treturn;",
 "\t\t}",
 "\t}",
 '\tNativeGpu_DiagTraceOnce("region-players-done", (const void *)ptr, 0);',
 "",
 "\tuiPB = &gGT->pushBuffer_UI;",
 "\tuiStart = (uintptr_t)uiPB->ptrOT;",
 "\tuiEnd = (uintptr_t)uiPB->renderBucketOTRangeEnd;",
 "\tif ((uiStart != 0) && (uiEnd != 0) && (ptr >= uiStart) && (ptr <= uiEnd))",
 "\t{",
 '\t\tNativeGpu_ConvertFormat(dst, dstSize, "ui.ot+0x%08x", (unsigned)(ptr - uiStart));',
 '\t\tNativeGpu_DiagTraceOnce("region-ui", dst, 0);',
 "\t\treturn;",
 "\t}",
 "",
 "\tfor (dbIndex = 0; dbIndex < 2; dbIndex++)",
 "\t{",
 "\t\tdb = &gGT->db[dbIndex];",
 "\t\tprimStart = (uintptr_t)db->primMem.start;",
 "\t\tprimEnd = (uintptr_t)db->primMem.end;",
 "\t\totStart = (uintptr_t)db->otMem.start;",
 "\t\totEnd = (uintptr_t)db->otMem.end;",
 "\t\tif ((primStart != 0) && (ptr >= primStart) && (ptr < primEnd))",
 "\t\t{",
 '\t\t\tNativeGpu_ConvertFormatIndexed(dst, dstSize, "db%d.prim+0x%08x", (unsigned)dbIndex, (unsigned)(ptr - primStart));',
 '\t\t\tNativeGpu_DiagTraceOnce("region-dbprim", dst, 0);',
 "\t\t\treturn;",
 "\t\t}",
 "\t\tif ((otStart != 0) && (ptr >= otStart) && (ptr < otEnd))",
 "\t\t{",
 '\t\t\tNativeGpu_ConvertFormatIndexed(dst, dstSize, "db%d.ot+0x%08x", (unsigned)dbIndex, (unsigned)(ptr - otStart));',
 '\t\t\tNativeGpu_DiagTraceOnce("region-dbot", dst, 0);',
 "\t\t\treturn;",
 "\t\t}",
 "\t}",
 "",
 '\tsnprintf(dst, dstSize, "unknown");',
 '\tNativeGpu_DiagTraceOnce("region-unknown", dst, 0);',
 "}",
]

REPORT_NEW = [
 "\t\t\t\tif (currentPacket != endPacket)",
 "\t\t\t\t{",
 "\t\t\t\t\tchar packetRegion[64];",
 "\t\t\t\t\tu32 w0, w1, w2, w3;",
 '\t\t\t\t\tNativeGpu_DiagTraceOnce("prims-overshoot", (const void *)basePacket, (int)(endPacket - currentPacket));',
 "\t\t\t\t\tw0 = NativeGpu_ReadPacketWordForLog((uintptr_t)basePacket, 0);",
 "\t\t\t\t\tw1 = NativeGpu_ReadPacketWordForLog((uintptr_t)basePacket, 1);",
 "\t\t\t\t\tw2 = NativeGpu_ReadPacketWordForLog((uintptr_t)basePacket, 2);",
 "\t\t\t\t\tw3 = NativeGpu_ReadPacketWordForLog((uintptr_t)basePacket, 3);",
 '\t\t\t\t\tNativeGpu_DiagTraceOnce("overshoot-words", (const void *)basePacket, 0);',
 '\t\t\t\t\tPlatform_Log("[trace] GPU invalid-prim-words diff=%d packet=%p words=%08x %08x %08x %08x\\n",',
 "\t\t\t\t\t             (int)(endPacket - currentPacket), (void *)basePacket, (unsigned)w0, (unsigned)w1, (unsigned)w2, (unsigned)w3);",
 '\t\t\t\t\tNativeGpu_DiagTraceOnce("overshoot-words-printed", (const void *)basePacket, 0);',
 "\t\t\t\t\tNativeGpu_FormatPointerRegion(packetRegion, sizeof(packetRegion), (uintptr_t)basePacket);",
 '\t\t\t\t\tNativeGpu_DiagTraceOnce("overshoot-region", packetRegion, 0);',
 "\t\t\t\t\t/* The report goes to the stdout path (proven alive in every",
 "\t\t\t\t\t   run); the stderr variant's first-ever console write wedged",
 "\t\t\t\t\t   the guest thread on frame 13 with no output and no fault.",
 "\t\t\t\t\t   Keep the durable report on the path that reaches the log. */",
 '\t\t\t\t\tPlatform_Log("[trace] GPU invalid-prim diff=%d packet=%p region=%s words=%08x %08x %08x %08x\\n",',
 "\t\t\t\t\t             (int)(endPacket - currentPacket), (void *)basePacket, packetRegion, (unsigned)w0, (unsigned)w1, (unsigned)w2,",
 "\t\t\t\t\t             (unsigned)w3);",
 '\t\t\t\t\tNativeGpu_DiagTraceOnce("overshoot-stdout", (const void *)basePacket, 0);',
 '\t\t\t\t\tNATIVE_GPU_ERROR("did not output valid primitive or ptag length is not valid (diff=%d packet=%p region=%s words=%08x %08x %08x %08x)\\n",',
 "\t\t\t\t\t                 (int)(endPacket - currentPacket), (void *)basePacket, packetRegion, (unsigned)w0, (unsigned)w1, (unsigned)w2,",
 "\t\t\t\t\t                 (unsigned)w3);",
 '\t\t\t\t\tNativeGpu_DiagTraceOnce("overshoot-stderr", (const void *)basePacket, 0);',
 "\t\t\t\t}",
]

check_only = "--check" in sys.argv

text = io.open(TREE, encoding="utf-8", newline="").read()
lines = text.split("\n")

# --- region A: the FormatPointerRegion function -----------------------------
i0 = None
for k, L in enumerate(lines):
    if L.rstrip("\r") == "internal void NativeGpu_FormatPointerRegion(char *dst, size_t dstSize, uintptr_t ptr)":
        i0 = k
        break
assert i0 is not None, "FormatPointerRegion signature not found"
i1 = None
for k in range(i0 + 1, len(lines)):
    if lines[k].rstrip("\r") == "}":
        i1 = k
        break
assert i1 is not None, "FormatPointerRegion closing brace not found"
eol = "\r" if lines[i0].endswith("\r") else ""
lines[i0:i1 + 1] = [L + eol for L in FUNC_NEW]
print("region A replaced (lines %d..%d, eol=%r)" % (i0 + 1, i1 + 1, eol))

# --- region B: the overshoot reporter block ---------------------------------
text = "\n".join(lines)
lines = text.split("\n")
ip = None
for k, L in enumerate(lines):
    if 'NATIVE_GPU_ERROR("did not output valid primitive' in L:
        ip = k
        break
assert ip is not None, "reporter ERROR line not found"
i0 = None
for k in range(ip, max(0, ip - 25), -1):
    if lines[k].rstrip("\r") == "\t\t\t\tif (currentPacket != endPacket)":
        i0 = k
        break
assert i0 is not None, "reporter if-line not found"
i1 = None
for k in range(i0 + 1, len(lines)):
    if lines[k].rstrip("\r") == "\t\t\t\t}":
        i1 = k
        break
assert i1 is not None, "reporter closing brace not found"
eol = "\r" if lines[i0].endswith("\r") else ""
lines[i0:i1 + 1] = [L + eol for L in REPORT_NEW]
print("region B replaced (lines %d..%d, eol=%r)" % (i0 + 1, i1 + 1, eol))

out = "\n".join(lines)
if check_only:
    print("check-only: not written")
else:
    io.open(TREE, "w", encoding="utf-8", newline="").write(out)
    print("written")

# --- literal-newline scan (reuse the repair tool's scanner) ------------------
import importlib.util
spec = importlib.util.spec_from_file_location("fnl", os.path.join(HERE, "fix_newline_in_literals.py"))
fnl = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(fnl)
except SystemExit:
    pass  # the repair tool exits after its own scan; its result is re-checked below
bad = fnl.scan_for_bad_literals(io.open(TREE, "rb").read())
print("literal newlines after splice: %d" % len(bad))
if bad:
    print("FATAL: run tools/ctr360/fix_newline_in_literals.py")
    sys.exit(3)
print("sync_tree_regions: ok")
