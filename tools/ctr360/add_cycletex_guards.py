"""ctr360 CycleTex walk instruments (repo + tree).

The menu-frame wedge is inside CTR_CycleTex_AllModels(level1->numModels, arr,
timer) for the menu level: the player-list call returns, the level call does
not. These edits make the walk observable and self-bounding:

  globals g_ctr360_modelWalkGuard / hdrGuard / ctxWalkGuard  - walk counters
  am / am-guard    - per model in AllModels (menu frames only) + 8192 bound
  hd / hd-guard    - per model header (menu frames only) + 1024 bound
  cm / cm-guard    - per AnimTex chain node (menu frames only) + 4096 bound

The guards convert a runaway walk into a logged event and return/break, so the
menu can continue even when the data is wrong.

Anchors are identical in both copies; ones that legitimately occur twice
(CTR_CycleTex_LEV and CTR_CycleTex_Model share their bodies) are applied to
both occurrences.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")
REL = os.path.join("game", "CTR", "CTR_CycleTex.c")

BS = chr(92)
N = BS + "n"

GLOBALS = [
    "/* ctr360 walk instruments: bound the model / header / animtex-chain walks",
    " * and trace them on menu frames (mode1 MAIN_MENU, not LOADING). */",
    "int g_ctr360_modelWalkGuard = 0;",
    "int g_ctr360_hdrGuard = 0;",
    "int g_ctr360_ctxWalkGuard = 0;",
]

AM_GUARD = ('\t\t{ g_ctr360_modelWalkGuard++; g_ctr360_hdrGuard = 0; g_ctr360_ctxWalkGuard = 0; if (g_ctr360_modelWalkGuard > 8192) { Platform_Log("[probe] am-guard num=%d arr=%08x'
            + N + '", (int)numModels, (unsigned)(u32)pModelArray); return; } }')
AM_PROBE = ('\t\t{ static int s_am = 0; if ((s_am < 300) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_am++; Platform_Log("[probe] am f=%d num=%d arr=%08x m=%08x'
            + N + '", (int)sdata->frameCounter, (int)numModels, (unsigned)(u32)pModelArray, (unsigned)(u32)pModel); } }')
HD_BLOCK = ('\t\t\t{ static int s_hd = 0; g_ctr360_hdrGuard++; if (g_ctr360_hdrGuard > 1024) { Platform_Log("[probe] hd-guard nh=%d m=%08x'
            + N + '", (int)pModel->numHeaders, (unsigned)(u32)pModel); break; } if ((s_hd < 300) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_hd++; Platform_Log("[probe] hd f=%d j=%d hdr=%08x atx=%08x fl=%04x'
            + N + '", (int)sdata->frameCounter, (int)j, (unsigned)(u32)pHeader, (unsigned)(u32)pHeader->animtex, (unsigned)(pHeader->flags)); } }')
CTX_ENTRY = '\t{ g_ctr360_ctxWalkGuard = 0; }'
CM_BLOCK = ('\t\t{ static int s_cm = 0; g_ctr360_ctxWalkGuard++; if (g_ctr360_ctxWalkGuard > 4096) { Platform_Log("[probe] cm-guard a=%08x cur=%08x'
            + N + '", (unsigned)(u32)animtex, (unsigned)(u32)curAnimTex); break; } if ((s_cm < 300) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_cm++; Platform_Log("[probe] cm f=%d a=%08x cur=%08x nf=%d fo=%d fs=%d link=%08x'
            + N + '", (int)sdata->frameCounter, (unsigned)(u32)animtex, (unsigned)(u32)curAnimTex, (int)curAnimTex->numFrames, (int)curAnimTex->frameOffset, (int)curAnimTex->frameSkip, (unsigned)(u32)*(int *)curAnimTex); } }')

# (anchor, insert_before/after, block, expected_count)
EDITS = [
    ("#include <common.h>", "after", "\n".join(GLOBALS), 1),
    ("\t\tpModel = *pModelArray;", "before", AM_GUARD, 1),
    ("\t\tpModel = *pModelArray;", "after", AM_PROBE, 1),
    ("\t\t\tpHeader = &pModel->headers[j];", "after", HD_BLOCK, 1),
    ("\tstruct AnimTex *curAnimTex = animtex;", "after", CTX_ENTRY, 2),
    ("\t\tframeCurr = timer + curAnimTex->frameOffset;", "before", CM_BLOCK, 2),
]

problems = []
applied = []

for label, base in (("repo", ROOT), ("tree", TREE)):
    path = os.path.join(base, REL)
    text = io.open(path, encoding="utf-8", newline="").read()
    for nl_name, nl in (("CRLF", "\r\n"), ("LF", "\n")):
        file_ok = True
        work = text
        for anchor, where, block, expected in EDITS:
            a = anchor.replace("\n", nl)
            b = block.replace("\n", nl)
            n = work.count(a)
            if n != expected:
                file_ok = False
                break
            if where == "before":
                work = work.replace(a, b + nl + a)
            else:
                work = work.replace(a, a + nl + b)
        if file_ok and work != text:
            io.open(path, "w", encoding="utf-8", newline="").write(work)
            print("%s: applied (%s)" % (label, nl_name))
            applied.append(path)
            break
        if file_ok and work == text:
            print("%s: already applied" % label)
            break
    else:
        problems.append("%s %s" % (label, REL))

if problems:
    print("FATAL:")
    for p in problems:
        print("  " + p)
    sys.exit(2)

import importlib.util
spec = importlib.util.spec_from_file_location("fnl", os.path.join(HERE, "fix_newline_in_literals.py"))
fnl = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(fnl)
except SystemExit:
    pass

bad_total = 0
for path in set(applied):
    bad = fnl.scan_for_bad_literals(io.open(path, "rb").read())
    if bad:
        bad_total += len(bad)
        print("literal newlines in %s: %d" % (path, len(bad)))
if bad_total:
    sys.exit(3)
print("add_cycletex_guards: ok")
