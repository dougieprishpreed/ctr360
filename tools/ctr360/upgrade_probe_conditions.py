"""ctr360 probe condition upgrade (batch 4): make the frame-loop probes
deterministic at the menu.

The mod-N cadence probes only print every Nth call, so the exact frame of
interest (first MAIN_MENU frame) may not be covered. Each probe now prints on
EVERY call while the menu is active (mode1 has MAIN_MENU=0x2000 and not
LOADING=0x40000000), capped at 400 lines, and falls back to a sparse cadence
otherwise. Tags gain an 'm' (hb -> hbm, l1 -> l1m, ...).

Edits repo and mirror tree together; every replacement must match once.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")

BS = chr(92)
NL = BS + "n"

MCOND = "(((gGT->gameMode1) & 0x2000) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)"


def win(tag_old, body_old, tag_new, body_new, indent):
    return ("\t" * indent + '{ static int s_' + tag_old + ' = 0; if ((s_' + tag_old + '++ % 30) == 0) { Platform_Log("[probe] ' + tag_old + ' ' + body_old + '"); } }',
            "\t" * indent + '{ static int s_' + tag_old + ' = 0; if (' + MCOND + ') { s_' + tag_old + '++; if (s_' + tag_old + ' < 400) { Platform_Log("[probe] ' + tag_new + ' ' + body_new + '"); } } else if ((sdata->frameCounter % 60) == 0) { Platform_Log("[probe] ' + tag_old + ' ' + body_old + '"); } }')


EDIT_LIST = []

# hb (MainMain.c)
EDIT_LIST.append((
    os.path.join("game", "MAIN", "MainMain.c"),
    '\t\t\t{ static int s_hb = 0; if ((s_hb++ % 30) == 0) { Platform_Log("[probe] hb f=%d ms=%d state=%d stage=%d mode1=%08x lvl=%d' + NL + '", (int)sdata->frameCounter, (int)gGT->elapsedTimeMS, (int)sdata->mainGameState, (int)sdata->Loading.stage, (unsigned)gGT->gameMode1, (int)gGT->levelID); } }',
    '\t\t\t{ static int s_hb = 0; if (' + MCOND + ') { s_hb++; if (s_hb < 400) { Platform_Log("[probe] hbm f=%d ms=%d state=%d stage=%d mode1=%08x lvl=%d' + NL + '", (int)sdata->frameCounter, (int)gGT->elapsedTimeMS, (int)sdata->mainGameState, (int)sdata->Loading.stage, (unsigned)gGT->gameMode1, (int)gGT->levelID); } } else if ((sdata->frameCounter % 60) == 0) { Platform_Log("[probe] hb f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }',
))

# l1 (MainMain.c)
EDIT_LIST.append((
    os.path.join("game", "MAIN", "MainMain.c"),
    '\t\t\t{ static int s_l1 = 0; if ((s_l1++ % 10) == 0) { Platform_Log("[probe] l1 f=%d' + NL + '", (int)sdata->frameCounter); } }',
    '\t\t\t{ static int s_l1 = 0; if (' + MCOND + ') { s_l1++; if (s_l1 < 400) { Platform_Log("[probe] l1m f=%d' + NL + '", (int)sdata->frameCounter); } } else if ((sdata->frameCounter % 60) == 0) { Platform_Log("[probe] l1 f=%d' + NL + '", (int)sdata->frameCounter); } }',
))

# l2 / l3 (MainMain.c)
EDIT_LIST.append((
    os.path.join("game", "MAIN", "MainMain.c"),
    '\t\t\t\t{ static int s_l2 = 0; if ((s_l2++ % 10) == 0) { Platform_Log("[probe] l2 f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }',
    '\t\t\t\t{ static int s_l2 = 0; if (' + MCOND + ') { s_l2++; if (s_l2 < 400) { Platform_Log("[probe] l2m f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } } else if ((sdata->frameCounter % 60) == 0) { Platform_Log("[probe] l2 f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }',
))
EDIT_LIST.append((
    os.path.join("game", "MAIN", "MainMain.c"),
    '\t\t\t\t{ static int s_l3 = 0; if ((s_l3++ % 10) == 0) { Platform_Log("[probe] l3 f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }',
    '\t\t\t\t{ static int s_l3 = 0; if (' + MCOND + ') { s_l3++; if (s_l3 < 400) { Platform_Log("[probe] l3m f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } } else if ((sdata->frameCounter % 60) == 0) { Platform_Log("[probe] l3 f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }',
))

# g1..g7 + cd in MainFrame.c (mod 5 -> menu window)
for tag in ("g1", "g2", "g3", "g4", "g5", "g6", "g7"):
    pass

EDIT_LIST.append((
    os.path.join("game", "MAIN", "MainFrame.c"),
    '\t{ static int s_g1 = 0; if ((s_g1++ % 5) == 0) { Platform_Log("[probe] g1 f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } }',
    '\t{ static int s_g1 = 0; if (' + MCOND + ') { s_g1++; if (s_g1 < 400) { Platform_Log("[probe] g1m f=%d mode1=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } } else if ((sdata->frameCounter % 60) == 0) { Platform_Log("[probe] g1 f=%d' + NL + '", (int)sdata->frameCounter); } }',
))
EDIT_LIST.append((
    os.path.join("game", "MAIN", "MainFrame.c"),
    '\t\t{ static int s_g2 = 0; if ((s_g2++ % 5) == 0) { Platform_Log("[probe] g2 f=%d lvl1=%08x numModels=%d arr=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)(u32)gGT->level1, (int)((gGT->level1 != NULL) ? gGT->level1->numModels : -999), (unsigned)(u32)((gGT->level1 != NULL) ? (u32)gGT->level1->ptrModelsPtrArray : 0)); } }',
    '\t\t{ static int s_g2 = 0; if (' + MCOND + ') { s_g2++; if (s_g2 < 400) { Platform_Log("[probe] g2m f=%d lvl1=%08x numModels=%d arr=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)(u32)gGT->level1, (int)((gGT->level1 != NULL) ? gGT->level1->numModels : -999), (unsigned)(u32)((gGT->level1 != NULL) ? (u32)gGT->level1->ptrModelsPtrArray : 0)); } } }',
))
for tag in ("g3", "g4", "g5"):
    indent = "\t\t"
    EDIT_LIST.append((
        os.path.join("game", "MAIN", "MainFrame.c"),
        indent + '{ static int s_' + tag + ' = 0; if ((s_' + tag + '++ % 5) == 0) { Platform_Log("[probe] ' + tag + ' f=%d' + NL + '", (int)sdata->frameCounter); } }',
        indent + '{ static int s_' + tag + ' = 0; if (' + MCOND + ') { s_' + tag + '++; if (s_' + tag + ' < 400) { Platform_Log("[probe] ' + tag + 'm f=%d' + NL + '", (int)sdata->frameCounter); } } }',
    ))
for tag in ("g6", "g7"):
    indent = "\t"
    EDIT_LIST.append((
        os.path.join("game", "MAIN", "MainFrame.c"),
        indent + '{ static int s_' + tag + ' = 0; if ((s_' + tag + '++ % 5) == 0) { Platform_Log("[probe] ' + tag + ' f=%d' + NL + '", (int)sdata->frameCounter); } }',
        indent + '{ static int s_' + tag + ' = 0; if (' + MCOND + ') { s_' + tag + '++; if (s_' + tag + ' < 400) { Platform_Log("[probe] ' + tag + 'm f=%d' + NL + '", (int)sdata->frameCounter); } } }',
    ))

EDIT_LIST.append((
    os.path.join("game", "MAIN", "MainFrame.c"),
    '\t\t\t{ static int s_cd = 0; if (s_cd < 200) { s_cd++; Platform_Log("[probe] cd i=%d thr=%08x obj=%08x' + NL + '", s_cd, (unsigned)(u32)psVar12, (unsigned)(u32)psVar12->object); } }',
    '\t\t\t{ static int s_cd = 0; if (' + MCOND + ') { s_cd++; if (s_cd < 400) { Platform_Log("[probe] cdm i=%d thr=%08x obj=%08x' + NL + '", s_cd, (unsigned)(u32)psVar12, (unsigned)(u32)psVar12->object); } } }',
))

problems = []
applied = []

for rel, old_text, new_text in EDIT_LIST:
    for label, base in (("repo", ROOT), ("tree", TREE)):
        path = os.path.join(base, rel)
        text = io.open(path, encoding="utf-8", newline="").read()
        # try both EOL joinings
        for nl_name, nl in (("CRLF", "\r\n"), ("LF", "\n")):
            old_l = old_text.replace("\n", "\r\n") if nl == "\r\n" else old_text
            new_l = new_text.replace("\n", "\r\n") if nl == "\r\n" else new_text
            n_old = text.count(old_l)
            n_new = text.count(new_l)
            if n_new == 1 and n_old == 0:
                print("%s %s: already upgraded (%s)" % (label, rel, nl_name))
                break
            if n_old == 1:
                text = text.replace(old_l, new_l)
                io.open(path, "w", encoding="utf-8", newline="").write(text)
                print("%s %s: upgraded (%s)" % (label, rel, nl_name))
                applied.append(path)
                break
        else:
            # report counts for debugging
            counts = [text.count(old_text.replace("\n", sep)) for sep in ("\r\n", "\n")]
            if 1 not in [text.count(new_text.replace("\n", sep)) for sep in ("\r\n", "\n")]:
                problems.append("%s %s: probe %s not upgraded (old counts %s)"
                                % (label, rel, old_text[:60], counts))

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
print("upgrade_probe_conditions: ok")
