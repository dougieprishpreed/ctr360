"""ctr360 GameLogic bisect probes, batch 3 (repo + mirror tree).

Wedge #2 pinned to MainFrame_GameLogic at the first MAIN_MENU frame (f=457):
the l2 probe (before the call) prints, l3 (after) does not. These probes
bisect the function body and watch the thread-tick machinery:

  g1        - GameLogic entry
  cd        - inside the driver/clock loop over threadBuckets[0]
  g2        - after CTR_CycleTex_AllModels (prints level1 numModels/ptr)
  g3        - after the driver scan loop
  g4 / g5   - around the bucket tick loop
  g6        - after PROC_CheckAllForDead
  g7        - after GAMEPAD_GetNumConnected (near function end)
  tt        - ThTick_RunBucket: thread + funcThTick about to run (menu only)
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")

BS = chr(92)
N = BS + "n"

G1 = ('\t{ static int s_g1 = 0; if ((s_g1++ % 5) == 0) { Platform_Log("[probe] g1 f=%d mode1=%08x'
      + N + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }')
CD = ('\t\t\t{ static int s_cd = 0; if (s_cd < 200) { s_cd++; Platform_Log("[probe] cd i=%d thr=%08x obj=%08x'
      + N + '", s_cd, (unsigned)(u32)psVar12, (unsigned)(u32)psVar12->object); } }')
G2 = ('\t\t{ static int s_g2 = 0; if ((s_g2++ % 5) == 0) { Platform_Log("[probe] g2 f=%d lvl1=%08x numModels=%d arr=%08x'
      + N + '", (int)sdata->frameCounter, (unsigned)(u32)gGT->level1, (int)((gGT->level1 != NULL) ? gGT->level1->numModels : -999), (unsigned)(u32)((gGT->level1 != NULL) ? (u32)gGT->level1->ptrModelsPtrArray : 0)); } }')
G3 = ('\t\t{ static int s_g3 = 0; if ((s_g3++ % 5) == 0) { Platform_Log("[probe] g3 f=%d'
      + N + '", (int)sdata->frameCounter); } }')
G4 = ('\t\t{ static int s_g4 = 0; if ((s_g4++ % 5) == 0) { Platform_Log("[probe] g4 f=%d'
      + N + '", (int)sdata->frameCounter); } }')
G5 = ('\t\t{ static int s_g5 = 0; if ((s_g5++ % 5) == 0) { Platform_Log("[probe] g5 f=%d'
      + N + '", (int)sdata->frameCounter); } }')
G6 = ('\t{ static int s_g6 = 0; if ((s_g6++ % 5) == 0) { Platform_Log("[probe] g6 f=%d'
      + N + '", (int)sdata->frameCounter); } }')
G7 = ('\t{ static int s_g7 = 0; if ((s_g7++ % 5) == 0) { Platform_Log("[probe] g7 f=%d'
      + N + '", (int)sdata->frameCounter); } }')
TT = ('\t\t{ static int s_tt = 0; if ((s_tt < 240) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_tt++; Platform_Log("[probe] tt thr=%08x fn=%08x'
      + N + '", (unsigned)(u32)t, (unsigned)(u32)(t->funcThTick)); } }')

EDITS = {
    os.path.join("game", "MAIN", "MainFrame.c"): [
        ("\tstruct Thread *psVar12;", None, "after", G1),
        ("\t\t\tpsVar9 = (struct Driver *)psVar12->object;\n\n\t\t\tif (psVar9->clockSend)", None, "after", CD),
        ("\t\tCTR_CycleTex_AllModels(gGT->level1->numModels, gGT->level1->ptrModelsPtrArray, gGT->timer);", None, "after", G2),
        ("\t\tif (((psVar8 != 0) && (psVar9 != 0)) &&", G3, "before", None),
        ("\t\tfor (iVar4 = 0; iVar4 < PAUSE; iVar4++)", G4, "before", None),
        ("#if defined(CTR_NATIVE)\n\t\tBOTS_UpdateGlobals();", G5, "before", None),
        ("\tPROC_CheckAllForDead();", None, "after", G6),
        ("\tuVar5 = GAMEPAD_GetNumConnected(gGamepads);", None, "after", G7),
    ],
    os.path.join("game", "PROC.c"): [
        ("\t\tif (t->funcThTick != NULL)", TT, "before", None),
    ],
}

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
                inserted = None
                if kind == "before":
                    inserted = before.replace("\n", nl) if before else None
                elif kind == "after":
                    inserted = after.replace("\n", nl) if after else None
                else:
                    inserted = None
                # skip if this probe is already present
                probe_line = (before or after).split(N)[0]
                if work.count(probe_line) >= 1:
                    continue
                if kind == "before":
                    pair = (old_l, before.replace("\n", nl) + nl + old_l)
                elif kind == "after":
                    pair = (old_l, old_l + nl + after.replace("\n", nl))
                else:
                    file_ok = False
                    break
                if work.count(pair[0]) != 1:
                    file_ok = False
                    break
                work = work.replace(pair[0], pair[1])
            if file_ok and work != text:
                io.open(path, "w", encoding="utf-8", newline="").write(work)
                print("%s %s: applied (%s)" % (label, rel, nl_name))
                applied.append(path)
                ok = True
                break
        if not ok:
            problems.append("%s %s: could not apply" % (label, rel))

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
print("add_menulogic_probes: ok")
