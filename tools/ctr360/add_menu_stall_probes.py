"""ctr360 menu-path stall probes (repo + mirror tree, CRLF/LF aware).

The frame-13 print-path fix unblocked the walk; the cutscene script then
requested the menu level (~f=418) and the load transaction completed, after
which the main thread went silent. These probes localize the second stall:

  [probe] hb                - frame loop heartbeat every 30 frames
  [probe] render-enter/exit - around MainFrame_RenderFrame
  [probe] title-init        - MM_Title_Init gate inputs (obj/mode1/mstate/ring/st1)
  [probe] title-menu        - MM_Title_MenuUpdate state machine inputs
  [probe] title-dpp         - RenderAllTitleDPP gate inputs
  [probe] jump-to-title-first-time - stage-4 menu init ran

Every edit asserts exactly one match per file; both copies are edited in the
same run so repo and tree cannot drift. Probe blocks are C89-safe (a single
statement block; declarations first).
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

TREE = os.path.join(ROOT, "build-360", "gen")

BS = chr(92)
NL_ESC = BS + "n"

FILES = {
    "MainMain": os.path.join("game", "MAIN", "MainMain.c"),
    "MM_Title": os.path.join("game", "230", "MM_Title.c"),
    "RenderFrame": os.path.join("game", "MAIN", "MainFrame_RenderFrame.c"),
    "MenuFlow": os.path.join("game", "230", "MM_MenuFlow.c"),
}

HB_PROBE = ('\t\t\t{ static int s_hb = 0; if ((s_hb++ % 30) == 0) { Platform_Log("[probe] hb f=%d ms=%d state=%d stage=%d mode1=%08x lvl=%d'
            + NL_ESC + '", (int)sdata->frameCounter, (int)gGT->elapsedTimeMS, (int)sdata->mainGameState, (int)sdata->Loading.stage, (unsigned)gGT->gameMode1, (int)gGT->levelID); } }')
RE_PROBE = ('\t\t\t{ static int s_re = 0; if ((s_re++ % 30) == 0) { Platform_Log("[probe] render-enter f=%d'
            + NL_ESC + '", (int)sdata->frameCounter); } }')
RX_PROBE = ('\t\t\t{ static int s_rx = 0; if ((s_rx++ % 30) == 0) { Platform_Log("[probe] render-exit f=%d'
            + NL_ESC + '", (int)sdata->frameCounter); } }')

TI_PROBE = ('\t{ static int s_ti = 0; if (s_ti < 80) { s_ti++; Platform_Log("[probe] title-init obj=%08x mode1=%08x mstate=%d ring=%08x lvl1=%08x st1=%d'
             + NL_ESC + '", (unsigned)(u32)MM_TITLE_OBJECT, (unsigned)GAME_TRACKER->gameMode1, (int)MM_TITLE_MENU_STATE, (unsigned)(u32)GAME_TRACKER->modelPtr[STATIC_RINGTOP], (unsigned)(u32)GAME_TRACKER->level1, (int)((GAME_TRACKER->level1 != NULL && GAME_TRACKER->level1->ptrSpawnType1 != NULL) ? (int)GAME_TRACKER->level1->ptrSpawnType1->count : -1)); } }')
MU_PROBE = ('\t{ static int s_mu = 0; if (s_mu < 80) { s_mu++; Platform_Log("[probe] title-menu state=%d tframe=%d intro=%d'
            + NL_ESC + '", (int)MM_TITLE_MENU_STATE, (int)MM_TITLE_MENU_TRANSITION_FRAME, (int)MM_TITLE_INTRO_FRAME); } }')
RT_PROBE = ('\t{ static int s_rt = 0; if (s_rt < 80) { s_rt++; Platform_Log("[probe] title-dpp mode1=%08x open=%d'
            + NL_ESC + '", (unsigned)gGT->gameMode1, (int)LOAD_IsOpen_MainMenu()); } }')
JF_PROBE = ('\t{ static int s_jf = 0; if (s_jf < 8) { s_jf++; Platform_Log("[probe] jump-to-title-first-time'
            + NL_ESC + '"); } }')


def edits_for(nl):
    """Returns {file_key: [(old, new), ...]} with lines joined by nl."""
    e = {}

    # MainMain.c: heartbeat after frameCounter++, probes around RenderFrame
    a = "\t\t\tsdata->frameCounter++;"
    b = "\t\t\tMainFrame_RenderFrame(gGT, gGS);"
    e["MainMain"] = [
        (a, a + nl + HB_PROBE),
        (b, RE_PROBE + nl + b + nl + RX_PROBE),
    ]

    # MM_Title.c: probe before the MM_Title_Init gate
    a = '\tif (' + nl + '\t    // if "title" object is nullptr'
    b2 = TI_PROBE + nl + a
    # MM_Title.c: probe at the top of MM_Title_MenuUpdate dispatch
    c = "\t// 0 - watching Crash + C-T-R letters animation"
    e["MM_Title"] = [
        (a, b2),
        (c, MU_PROBE + nl + c),
    ]

    # MainFrame_RenderFrame.c: probe inside RenderAllTitleDPP before its gate
    a = "void RenderAllTitleDPP(struct GameTracker *gGT)" + nl + "{" + nl + "\tif ((gGT->gameMode1 & MAIN_MENU) == 0)"
    b3 = ("void RenderAllTitleDPP(struct GameTracker *gGT)" + nl + "{" + nl + RT_PROBE + nl
          + "\tif ((gGT->gameMode1 & MAIN_MENU) == 0)")
    e["RenderFrame"] = [(a, b3)]

    # MM_MenuFlow.c: probe at the top of MM_JumpTo_Title_FirstTime
    a = '\tregister struct RectMenu *mainMenu CTR_PSX_REGISTER("$5");'
    e["MenuFlow"] = [(a, a + nl + JF_PROBE)]

    return e


problems = []
applied = []

for key, rel in FILES.items():
    for label, base in (("repo", ROOT), ("tree", TREE)):
        path = os.path.join(base, rel)
        text = io.open(path, encoding="utf-8", newline="").read()
        done = False
        for nl_name, nl in (("CRLF", "\r\n"), ("LF", "\n")):
            edits = edits_for(nl)[key]
            if all(text.count(new_line) >= 1 for _, new_line in edits):
                print("%s %s: already applied" % (label, rel))
                done = True
                break
            counts = [text.count(old_line) for old_line, _ in edits]
            if all(c == 1 for c in counts):
                for old_line, new_line in edits:
                    text = text.replace(old_line, new_line)
                io.open(path, "w", encoding="utf-8", newline="").write(text)
                print("%s %s: %d edit(s) applied (%s)" % (label, rel, len(edits), nl_name))
                applied.append(path)
                done = True
                break
        if not done:
            problems.append("%s %s: anchor counts %s (need exactly 1 each, %s or %s endings)"
                            % (label, rel, [text.count(o) for o, _ in edits_for("\r\n")], "CRLF", "LF"))

if problems:
    print("FATAL: not applied:")
    for p in problems:
        print("  " + p)
    sys.exit(2)

# literal-newline scan on every edited file
import importlib.util
spec = importlib.util.spec_from_file_location("fnl", os.path.join(HERE, "fix_newline_in_literals.py"))
fnl = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(fnl)
except SystemExit:
    pass

bad_total = 0
for path in applied:
    bad = fnl.scan_for_bad_literals(io.open(path, "rb").read())
    if bad:
        bad_total += len(bad)
        print("literal newlines in %s: %d (run fix_newline_in_literals.py)" % (path, len(bad)))
if bad_total:
    sys.exit(3)
print("add_menu_stall_probes: ok")
