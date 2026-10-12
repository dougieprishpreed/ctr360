"""ctr360 menu-path stall probes, batch 2 (repo + mirror tree).

Wedge #2: after the menu load completes (case1 + mainGameState=3, ~f=456) the
main thread stops within the next frames. Batch 1 could only see every 30th
frame; these probes run on a 10-frame cadence (so they keep printing across the
load) and bisect the frame body:

  l1 / l2 / l3      - around MainFrame_ResetDB / GameLogic
  rf-in             - inside MainFrame_RenderFrame after mesh_info pickup
  lg-in / lg-out    - around RenderAllLevelGeometry (mesh scalar values)
  ot                - DrawOTag entry (every 20th call)
  vl / vl-cb        - MainLoadVLC entry + queue callback
  ovr               - LOAD_OvrThreads entry

Every edit asserts exactly one match; repo and tree are edited together.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")

BS = chr(92)
N = BS + "n"

L1 = ('\t\t\t{ static int s_l1 = 0; if ((s_l1++ % 10) == 0) { Platform_Log("[probe] l1 f=%d'
      + N + '", (int)sdata->frameCounter); } }')
L2 = ('\t\t\t\t{ static int s_l2 = 0; if ((s_l2++ % 10) == 0) { Platform_Log("[probe] l2 f=%d mode1=%08x'
      + N + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }')
L3 = ('\t\t\t\t{ static int s_l3 = 0; if ((s_l3++ % 10) == 0) { Platform_Log("[probe] l3 f=%d mode1=%08x'
      + N + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }')

RFIN = ('\t{ static int s_rf = 0; if ((s_rf++ % 10) == 0) { Platform_Log("[probe] rf-in f=%d flags=%08x lev=%08x mesh=%08x'
        + N + '", (int)sdata->frameCounter, (unsigned)gGT->renderFlags, (unsigned)(u32)lev, (unsigned)(u32)ptr_mesh_info); } }')
LGIN = ('\t\t\t{ static int s_lg = 0; if ((s_lg++ % 10) == 0) { Platform_Log("[probe] lg-in f=%d nq=%d nv=%d nb=%d bsp=%08x'
        + N + '", (int)sdata->frameCounter, (int)ptr_mesh_info->numQuadBlock, (int)ptr_mesh_info->numVertex, (int)ptr_mesh_info->numBspNodes, (unsigned)(u32)ptr_mesh_info->bspRoot); } }')
LGOUT = ('\t\t\t{ static int s_lx = 0; if ((s_lx++ % 10) == 0) { Platform_Log("[probe] lg-out f=%d'
         + N + '", (int)sdata->frameCounter); } }')

OTP = ('\t{ static int s_ot = 0; if ((s_ot++ % 20) == 0) { Platform_Log("[probe] ot n=%d p=%p'
       + N + '", s_ot, p); } }')

VLE = ('\t{ static int s_vl = 0; if (s_vl < 20) { s_vl++; Platform_Log("[probe] vl entry isLoaded=%d'
       + N + '", (int)sdata->bool_IsLoaded_VlcTable); } }')
VLCB = ('\t{ static int s_vc = 0; if (s_vc < 20) { s_vc++; Platform_Log("[probe] vl cb ptr=%08x'
        + N + '", (unsigned)(u32)param_1->ptrDestination); } }')

OVR = ('\t{ static int s_ov = 0; if (s_ov < 20) { s_ov++; Platform_Log("[probe] ovr idx=%d cur=%d'
       + N + '", (int)overlayIndex, (int)((sdata->gGT != NULL) ? (int)sdata->gGT->overlayIndex_Threads : -1)); } }')

EDITS = {
    os.path.join("game", "MAIN", "MainMain.c"): [
        ("\t\t\tMainFrame_ResetDB(gGT);", None, "after", L1),
        ("\t\t\t\tMainFrame_GameLogic(gGT, gGS);", L2, "both", L3),
    ],
    os.path.join("game", "MAIN", "MainFrame_RenderFrame.c"): [
        ("\tif (lev != 0)\n\t{\n\t\tptr_mesh_info = lev->ptr_mesh_info;\n\t}", None, "after", RFIN),
        ("\t\t\tRenderAllLevelGeometry(gGT, lev, ptr_mesh_info);", LGIN, "both", LGOUT),
    ],
    os.path.join("platform", "native_libgpu.c"): [
        ("\t\tPlatform_Log(\"[trace] DrawOTag#%d enter p=%p\\n\", s_drawOTagTrace, p);", None, "after", OTP),
    ],
    os.path.join("game", "MAIN", "MainLoadVLC.c"): [
        ("\tsdata->bool_IsLoaded_VlcTable = 0;", VLE, "before", None),
        ("\tsdata->bool_IsLoaded_VlcTable = 1;", None, "after", VLCB),
    ],
    os.path.join("game", "LOAD", "LOAD_Overlays.c"): [
        ("\tstruct GameTracker *gGT = sdata->gGT;", None, "after", OVR),
    ],
}


def build_pairs(old_line, before, after):
    return before, after


problems = []
applied = []

for rel, entries in EDITS.items():
    for label, base in (("repo", ROOT), ("tree", TREE)):
        path = os.path.join(base, rel)
        text = io.open(path, encoding="utf-8", newline="").read()
        ok = False
        for nl_name, nl in (("CRLF", "\r\n"), ("LF", "\n")):
            file_ok = True
            work = text
            for old_line, before, kind, after in entries:
                old_l = old_line.replace("\n", nl)
                if before is not None and kind == "before" and work.count(before.replace("\n", nl) if isinstance(before, str) else before) == 0:
                    pass
                cands = []
                if kind == "before":
                    cands.append((old_l, before + nl + old_l))
                elif kind == "after":
                    cands.append((old_l, old_l + nl + after))
                else:
                    cands.append((old_l, before + nl + old_l + nl + after))
                # already-applied guard
                if kind == "before" and work.count(before) >= 1:
                    continue
                if kind == "after" and work.count(after) >= 1:
                    continue
                if kind == "both" and work.count(before) >= 1 and work.count(after) >= 1:
                    continue
                counts = [work.count(o) for o, _ in cands]
                if not all(c == 1 for c in counts):
                    file_ok = False
                    break
                for o, nw in cands:
                    work = work.replace(o, nw)
            if file_ok and work != text:
                io.open(path, "w", encoding="utf-8", newline="").write(work)
                print("%s %s: applied (%s)" % (label, rel, nl_name))
                applied.append(path)
                ok = True
                break
        if not ok:
            problems.append("%s %s: could not apply cleanly" % (label, rel))

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
print("add_menu_stall_probes2: ok")
