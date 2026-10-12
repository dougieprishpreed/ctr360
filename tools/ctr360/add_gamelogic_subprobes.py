"""ctr360 GameLogic sub-bisect probes (batch 5, repo + tree).

Between the g1 (entry) and g2 (after CycleTex) probes nothing printed at the
first menu frame. These probes cover every statement in between, printing on
every call while the menu is active, capped at 400 lines:

  pa - after pushBuffer = gGT->pushBuffer
  pc - inside the driver/clock loop, per thread (pointer)
  pd - after the driver loop
  pe - after the timer/unk1cc4 block
  pf - after Timer_GetTime_Elapsed (prints raw iVar4)
  pg - after CTR_CycleTex_AllModels(-1, PLYROBJECTLIST) (prints the list ptr)

If pg prints but g2 does not, the wedge is in the level1 CycleTex call
(numModels=20, ptrModelsPtrArray); if pg never prints, it is the player-list
call or the code above it.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")
BS = chr(92)
N = BS + "n"
MCOND = "(((gGT->gameMode1) & 0x2000) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)"


def probe(tag, fmt_tail, args, indent, cap=400):
    return ("\t" * indent + '{ static int s_' + tag + ' = 0; if (' + MCOND + ') { s_' + tag + '++; if (s_'
            + tag + ' < ' + str(cap) + ') { Platform_Log("[probe] ' + tag + ' f=%d ' + fmt_tail + N
            + '", (int)sdata->frameCounter' + (", " + args if args else "") + '); } } }')

PA = probe("pa", "", "", 2)
PC = probe("pc", "thr=%08x obj=%08x", "(unsigned)(u32)psVar12, (unsigned)(u32)psVar12->object", 3, cap=400)
PD = probe("pd", "", "", 2)
PE = probe("pe", "", "", 2)
PF = probe("pf", "iVar4=%d", "(int)iVar4", 2)
PG = probe("pg", "plyrlist=%08x", "(unsigned)(u32)sdata->PLYROBJECTLIST", 2)

EDITS = [
    ("\t\tpushBuffer = gGT->pushBuffer;", None, "after", PA),
    ("\t\t\tpsVar9 = (struct Driver *)psVar12->object;\n\n\t\t\tif (psVar9->clockSend)", None, "before", PC),
    ("\t\tLAB_80034e74:\n\t\t\tpushBuffer = pushBuffer + 1;\n\t\t}", None, "after", PD),
    ("\t\tgGT->unk1cc4[4] = 0;", None, "after", PE),
    ("\t\tiVar4 = Timer_GetTime_Elapsed(gGT->clockFrameStart, &gGT->clockFrameStart);", None, "after", PF),
    ("\t\tCTR_CycleTex_AllModels(-1, (struct Model **)sdata->PLYROBJECTLIST, gGT->timer);", None, "after", PG),
]

rel = os.path.join("game", "MAIN", "MainFrame.c")
problems = []
applied = []

for label, base in (("repo", ROOT), ("tree", TREE)):
    path = os.path.join(base, rel)
    text = io.open(path, encoding="utf-8", newline="").read()
    ok = False
    for nl_name, nl in (("CRLF", "\r\n"), ("LF", "\n")):
        file_ok = True
        work = text
        for old_line, _b, kind, new_line in EDITS:
            old_l = old_line.replace("\n", nl)
            new_l = new_line.replace("\n", nl)
            tag = new_line.split('s_')[1].split(' ')[0]
            if work.count('[probe] ' + tag + ' ') >= 1:
                continue
            if work.count(old_l) != 1:
                # pc anchor occurs twice (3-tab and 7-tab lines) - need the
                # unique full-line form for the 3-tab one
                file_ok = False
                break
            work = work.replace(old_l, old_l + nl + new_l)
        if file_ok and work != text:
            io.open(path, "w", encoding="utf-8", newline="").write(work)
            print("%s %s: applied (%s)" % (label, rel, nl_name))
            applied.append(path)
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

bad_total = 0
for path in set(applied):
    bad = fnl.scan_for_bad_literals(io.open(path, "rb").read())
    if bad:
        bad_total += len(bad)
        print("literal newlines in %s: %d" % (path, len(bad)))
if bad_total:
    sys.exit(3)
print("add_gamelogic_subprobes: ok")
