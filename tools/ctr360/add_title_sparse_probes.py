"""ctr360 title-transition probes: turn the one-shot title probes into sparse
forever-probes and add a probe on the title DPP's open path (repo + tree)."""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")
BS = chr(92)
N = BS + "n"

OLD_MU = ('\t{ static int s_mu = 0; if (s_mu < 80) { s_mu++; Platform_Log("[probe] title-menu state=%d tframe=%d intro=%d'
          + N + '", (int)MM_TITLE_MENU_STATE, (int)MM_TITLE_MENU_TRANSITION_FRAME, (int)MM_TITLE_INTRO_FRAME); } }')
NEW_MU = ('\t{ static int s_mu = 0; if ((s_mu++ % 30) == 0) { Platform_Log("[probe] title-menu state=%d tframe=%d intro=%d'
          + N + '", (int)MM_TITLE_MENU_STATE, (int)MM_TITLE_MENU_TRANSITION_FRAME, (int)MM_TITLE_INTRO_FRAME); } }')

OLD_TI = ('\t{ static int s_ti = 0; if (s_ti < 80) { s_ti++; Platform_Log("[probe] title-init obj=%08x mode1=%08x mstate=%d ring=%08x lvl1=%08x st1=%d'
          + N + '", (unsigned)(u32)MM_TITLE_OBJECT, (unsigned)GAME_TRACKER->gameMode1, (int)MM_TITLE_MENU_STATE, (unsigned)(u32)GAME_TRACKER->modelPtr[STATIC_RINGTOP], (unsigned)(u32)GAME_TRACKER->level1, (int)((GAME_TRACKER->level1 != NULL && GAME_TRACKER->level1->ptrSpawnType1 != NULL) ? (int)GAME_TRACKER->level1->ptrSpawnType1->count : -1)); } }')
NEW_TI = ('\t{ static int s_ti = 0; if ((s_ti++ % 30) == 0) { Platform_Log("[probe] title-init obj=%08x mode1=%08x mstate=%d ring=%08x lvl1=%08x st1=%d'
          + N + '", (unsigned)(u32)MM_TITLE_OBJECT, (unsigned)GAME_TRACKER->gameMode1, (int)MM_TITLE_MENU_STATE, (unsigned)(u32)GAME_TRACKER->modelPtr[STATIC_RINGTOP], (unsigned)(u32)GAME_TRACKER->level1, (int)((GAME_TRACKER->level1 != NULL && GAME_TRACKER->level1->ptrSpawnType1 != NULL) ? (int)GAME_TRACKER->level1->ptrSpawnType1->count : -1)); } }')

DPP_OLD = "\tMM_Title_SetTrophyDPP();"
DPP_NEW = '\t{ static int s_td = 0; if ((s_td++ % 30) == 0) { Platform_Log("[probe] rf13-open f=%d' + N + '", (int)sdata->frameCounter); } }\n\tMM_Title_SetTrophyDPP();'

EDITS = {
    os.path.join("game", "230", "MM_Title.c"): [(OLD_MU, NEW_MU), (OLD_TI, NEW_TI)],
    os.path.join("game", "MAIN", "MainFrame_RenderFrame.c"): [(DPP_OLD, DPP_NEW)],
}

problems = []
for rel, pairs in EDITS.items():
    for label, base in (("repo", ROOT), ("tree", TREE)):
        path = os.path.join(base, rel)
        text = io.open(path, encoding="utf-8", newline="").read()
        ok = False
        for nl_name, nl in (("CRLF", "\r\n"), ("LF", "\n")):
            work = text
            file_ok = True
            for old_s, new_s in pairs:
                o = old_s.replace("\n", nl)
                n_ = new_s.replace("\n", nl)
                if work.count(n_) == 1:
                    continue
                if work.count(o) != 1:
                    file_ok = False
                    break
                work = work.replace(o, n_)
            if file_ok and work != text:
                io.open(path, "w", encoding="utf-8", newline="").write(work)
                print("%s %s: applied (%s)" % (label, rel, nl_name))
                ok = True
                break
        if not ok:
            problems.append("%s %s" % (label, rel))

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
for rel in EDITS:
    for base in (ROOT, TREE):
        p = os.path.join(base, rel)
        bad = fnl.scan_for_bad_literals(io.open(p, "rb").read())
        if bad:
            print("BAD literals in", p, len(bad))
            sys.exit(3)
print("add_title_sparse_probes: ok")
