"""ctr360: instrument RenderBucket_QueueDraw's 9 silent-drop gates.

Counts per window (printed every 30 QueueAllInstances calls):
  att  = instances offered to QueueDraw
  q    = entries actually written to the bucket
  d[i] = which early-out dropped the instance
  lodm = sdata->LOD[lod] mask used for the (queuedFlags & lodMask) test
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")
QB = os.path.join("game", "RenderBucket", "RenderBucket_QueueExecute.c")
MF = os.path.join("game", "MAIN", "MainFrame_RenderFrame.c")

GLOBALS = '''static u32 s_rbDrop[8];
static u32 s_rbPrint;
u32 g_ctr360_qdAtt;
u32 g_ctr360_qdQueued;
u32 g_ctr360_qdDrop[9];'''

GLOBALS_OLD = '''static u32 s_rbDrop[8];
static u32 s_rbPrint;'''

QB_PAIRS = [
    (GLOBALS_OLD, GLOBALS),
    # d0/d1/d2
    ("\tif (inst == 0)\n\t{\n\t\treturn rbi;\n\t}",
     "\tif (inst == 0)\n\t{\n\t\tg_ctr360_qdDrop[0]++;\n\t\treturn rbi;\n\t}"),
    ("\tif (inst->model == 0)\n\t{\n\t\treturn rbi;\n\t}",
     "\tif (inst->model == 0)\n\t{\n\t\tg_ctr360_qdDrop[1]++;\n\t\treturn rbi;\n\t}"),
    ("\tif (inst->model->headers == 0)\n\t{\n\t\treturn rbi;\n\t}",
     "\tif (inst->model->headers == 0)\n\t{\n\t\tg_ctr360_qdDrop[2]++;\n\t\treturn rbi;\n\t}"),
    # d3: lod mask mismatch
    ("\tif ((queuedFlags & lodMask) == 0)\n\t{\n\t\t// NOTE(aalhendi): Retail 0x80070950-0x80070964 exits through the common",
     "\tif ((queuedFlags & lodMask) == 0)\n\t{\n\t\tg_ctr360_qdDrop[3]++;\n\t\t// NOTE(aalhendi): Retail 0x80070950-0x80070964 exits through the common"),
    # d4: pb == 0
    ("\tif (pb == 0)\n\t{\n\t\t// NOTE(aalhendi): Retail 0x80070964 reaches the same epilogue store.",
     "\tif (pb == 0)\n\t{\n\t\tg_ctr360_qdDrop[4]++;\n\t\t// NOTE(aalhendi): Retail 0x80070964 reaches the same epilogue store."),
    # d5: alpha scale write refused
    ("\tif (RenderBucket_WriteAlphaScale(inst, idpp, viewDepth, queuedFlags) == 0)\n\t{\n\t\tidpp->instFlags = queuedFlags;",
     "\tif (RenderBucket_WriteAlphaScale(inst, idpp, viewDepth, queuedFlags) == 0)\n\t{\n\t\tg_ctr360_qdDrop[5]++;\n\t\tidpp->instFlags = queuedFlags;"),
    # d6: mh == 0
    ("\tif (mh == 0)\n\t{\n\t\tif (lodExhausted != 0)",
     "\tif (mh == 0)\n\t{\n\t\tg_ctr360_qdDrop[6]++;\n\t\tif (lodExhausted != 0)"),
    # d7: frame == 0
    ("\tif (frame == 0)\n\t{\n\t\tidpp->instFlags = queuedFlags;\n\t\treturn rbi;\n\t}",
     "\tif (frame == 0)\n\t{\n\t\tg_ctr360_qdDrop[7]++;\n\t\tidpp->instFlags = queuedFlags;\n\t\treturn rbi;\n\t}"),
    # d8: depth range
    ("\tif (RenderBucket_BuildDepthRange(inst, frame, nextFrame, pb, idpp, queueState, viewDepth, normalDepthBias, secondaryDepthBias, &queuedFlags, &split,\n\t                                 &projectionMvp) == 0)\n\t{\n\t\tidpp->instFlags = queuedFlags;",
     "\tif (RenderBucket_BuildDepthRange(inst, frame, nextFrame, pb, idpp, queueState, viewDepth, normalDepthBias, secondaryDepthBias, &queuedFlags, &split,\n\t                                 &projectionMvp) == 0)\n\t{\n\t\tg_ctr360_qdDrop[8]++;\n\t\tidpp->instFlags = queuedFlags;"),
    # queued
    ("\trbi->inst = inst;\n\trbi->instPlayerBase = instPlayerBase;",
     "\tg_ctr360_qdQueued++;\n\trbi->inst = inst;\n\trbi->instPlayerBase = instPlayerBase;"),
    # attempts (both loops)
    ("\t\t\tentry = RenderBucket_QueueDraw(*visInstSrc, entry, player, lodMask, gameMode1, &queueState);",
     "\t\t\tg_ctr360_qdAtt++;\n\t\t\tentry = RenderBucket_QueueDraw(*visInstSrc, entry, player, lodMask, gameMode1, &queueState);"),
    ("\t\t\tentry = RenderBucket_QueueDraw((struct Instance *)curr, entry, player, lodMask, gameMode1, &queueState);",
     "\t\t\tg_ctr360_qdAtt++;\n\t\t\tentry = RenderBucket_QueueDraw((struct Instance *)curr, entry, player, lodMask, gameMode1, &queueState);"),
]

MF_OLD = "\t// null terminator at end of list\n\t*RBI = 0;\n}"

MF_NEW = '''\t// null terminator at end of list
\t*RBI = 0;

\t{
\t\textern u32 g_ctr360_qdAtt;
\t\textern u32 g_ctr360_qdQueued;
\t\textern u32 g_ctr360_qdDrop[9];
\t\tstatic u32 s_qall = 0;
\t\tif ((s_qall++ % 30) == 0)
\t\t{
\t\t\tPlatform_Log("[probe] qall att=%u q=%u d=%u,%u,%u,%u,%u,%u,%u,%u,%u lodm=%08x L=%08x,%08x,%08x,%08x,%08x\\n",
\t\t\t             (unsigned)g_ctr360_qdAtt, (unsigned)g_ctr360_qdQueued,
\t\t\t             (unsigned)g_ctr360_qdDrop[0], (unsigned)g_ctr360_qdDrop[1],
\t\t\t             (unsigned)g_ctr360_qdDrop[2], (unsigned)g_ctr360_qdDrop[3],
\t\t\t             (unsigned)g_ctr360_qdDrop[4], (unsigned)g_ctr360_qdDrop[5],
\t\t\t             (unsigned)g_ctr360_qdDrop[6], (unsigned)g_ctr360_qdDrop[7],
\t\t\t             (unsigned)g_ctr360_qdDrop[8],
\t\t\t             (unsigned)sdata->LOD[lod],
\t\t\t             (unsigned)sdata->LOD[0], (unsigned)sdata->LOD[1],
\t\t\t             (unsigned)sdata->LOD[2], (unsigned)sdata->LOD[3],
\t\t\t             (unsigned)sdata->LOD[4]);
\t\t\tg_ctr360_qdAtt = 0;
\t\t\tg_ctr360_qdQueued = 0;
\t\t\tg_ctr360_qdDrop[0] = 0;
\t\t\tg_ctr360_qdDrop[1] = 0;
\t\t\tg_ctr360_qdDrop[2] = 0;
\t\t\tg_ctr360_qdDrop[3] = 0;
\t\t\tg_ctr360_qdDrop[4] = 0;
\t\t\tg_ctr360_qdDrop[5] = 0;
\t\t\tg_ctr360_qdDrop[6] = 0;
\t\t\tg_ctr360_qdDrop[7] = 0;
\t\t\tg_ctr360_qdDrop[8] = 0;
\t\t}
\t}
}'''


def apply(path, pairs, label):
    text = io.open(path, encoding="utf-8", newline="").read()
    for nlname, nl in (("CRLF", "\r\n"), ("LF", "\n")):
        work = text
        ok = True
        for old_s, new_s in pairs:
            o = old_s.replace("\n", nl)
            n_ = new_s.replace("\n", nl)
            if work.count(n_) >= 1 and work.count(o) == 0:
                continue
            if work.count(o) != 1:
                ok = False
                print("  %s anchor x%d: %s" % (nlname, work.count(o), old_s.splitlines()[0][:70]))
                break
            work = work.replace(o, n_)
        if ok and work != text:
            io.open(path, "w", encoding="utf-8", newline="").write(work)
            print("%s: applied (%s)" % (label, nlname))
            return True
    return False


ok_all = True
for label, base in (("repo", ROOT), ("tree", TREE)):
    if not apply(os.path.join(base, QB), QB_PAIRS, label + " " + QB):
        ok_all = False
    if not apply(os.path.join(base, MF), [(MF_OLD, MF_NEW)], label + " " + MF):
        ok_all = False

if not ok_all:
    sys.exit(2)

import importlib.util
spec = importlib.util.spec_from_file_location("fnl", os.path.join(HERE, "fix_newline_in_literals.py"))
fnl = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(fnl)
except SystemExit:
    pass
for rel in (QB, MF):
    for base in (ROOT, TREE):
        p = os.path.join(base, rel)
        bad = fnl.scan_for_bad_literals(io.open(p, "rb").read())
        if bad:
            print("BAD literals in", p)
            sys.exit(3)
print("add_queue_drop_probes: ok")
