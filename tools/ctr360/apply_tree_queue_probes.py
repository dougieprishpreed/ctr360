"""ctr360: apply the queue-drop probes to the TREE copy only (it carries extra
q-probes the repo lacks), matching its exact text."""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")
QB = os.path.join(TREE, "game", "RenderBucket", "RenderBucket_QueueExecute.c")
MF = os.path.join(TREE, "game", "MAIN", "MainFrame_RenderFrame.c")

GLOBALS_OLD = "static u32 s_rbDrop[8];\nstatic u32 s_rbPrint;\n"
GLOBALS_NEW = ("static u32 s_rbDrop[8];\nstatic u32 s_rbPrint;\n"
               "\tu32 g_ctr360_qdAtt;\n\tu32 g_ctr360_qdQueued;\n\tu32 g_ctr360_qdDrop[9];\n")

QB_PAIRS = [
    ("\tif (inst == 0)\n\t{\n\t\treturn rbi;\n\t}",
     "\tif (inst == 0)\n\t{\n\t\tg_ctr360_qdDrop[0]++;\n\t\treturn rbi;\n\t}"),
    ("\tif (inst->model == 0)\n\t{\n\t\treturn rbi;\n\t}",
     "\tif (inst->model == 0)\n\t{\n\t\tg_ctr360_qdDrop[1]++;\n\t\treturn rbi;\n\t}"),
    ('\tif (inst->model->headers == 0)\n\t{ static int s_q9 = 0; if (s_q9 < 60) { s_q9++; Platform_Log("[trace] q9 f=%d hdr=%08x\\n", (int)sdata->frameCounter, (unsigned)(u32)inst->model->headers); } }\n\t{',
     '\tif (inst->model->headers == 0)\n\t{ static int s_q9 = 0; if (s_q9 < 60) { s_q9++; Platform_Log("[trace] q9 f=%d hdr=%08x\\n", (int)sdata->frameCounter, (unsigned)(u32)inst->model->headers); } }\n\t{\n\t\tg_ctr360_qdDrop[2]++;'),
    ("\tif ((queuedFlags & lodMask) == 0)\n\t{\n\t\t// NOTE(aalhendi): Retail 0x80070950-0x80070964 exits through the common",
     "\tif ((queuedFlags & lodMask) == 0)\n\t{\n\t\tg_ctr360_qdDrop[3]++;\n\t\t// NOTE(aalhendi): Retail 0x80070950-0x80070964 exits through the common"),
    ("\tif (pb == 0)\n\t{\n\t\t// NOTE(aalhendi): Retail 0x80070964 reaches the same epilogue store.",
     "\tif (pb == 0)\n\t{\n\t\tg_ctr360_qdDrop[4]++;\n\t\t// NOTE(aalhendi): Retail 0x80070964 reaches the same epilogue store."),
    ("\tif (RenderBucket_WriteAlphaScale(inst, idpp, viewDepth, queuedFlags) == 0)\n\t{\n\t\tidpp->instFlags = queuedFlags;",
     "\tif (RenderBucket_WriteAlphaScale(inst, idpp, viewDepth, queuedFlags) == 0)\n\t{\n\t\tg_ctr360_qdDrop[5]++;\n\t\tidpp->instFlags = queuedFlags;"),
    ("\tif (mh == 0)\n\t{\n\t\tif (lodExhausted != 0)",
     "\tif (mh == 0)\n\t{\n\t\tg_ctr360_qdDrop[6]++;\n\t\tif (lodExhausted != 0)"),
    ("\tif (frame == 0)\n\t{\n\t\tidpp->instFlags = queuedFlags;\n\t\treturn rbi;\n\t}",
     "\tif (frame == 0)\n\t{\n\t\tg_ctr360_qdDrop[7]++;\n\t\tidpp->instFlags = queuedFlags;\n\t\treturn rbi;\n\t}"),
    ("&projectionMvp) == 0)\n\t{\n\t\tidpp->instFlags = queuedFlags;",
     "&projectionMvp) == 0)\n\t{\n\t\tg_ctr360_qdDrop[8]++;\n\t\tidpp->instFlags = queuedFlags;"),
    ("\trbi->inst = inst;\n\trbi->instPlayerBase = instPlayerBase;",
     "\tg_ctr360_qdQueued++;\n\trbi->inst = inst;\n\trbi->instPlayerBase = instPlayerBase;"),
    ("\t\t\tentry = RenderBucket_QueueDraw(*visInstSrc, entry, player, lodMask, gameMode1, &queueState);",
     "\t\t\tg_ctr360_qdAtt++;\n\t\t\tentry = RenderBucket_QueueDraw(*visInstSrc, entry, player, lodMask, gameMode1, &queueState);"),
    ("\t\t\tentry = RenderBucket_QueueDraw((struct Instance *)curr, entry, player, lodMask, gameMode1, &queueState);",
     "\t\t\tg_ctr360_qdAtt++;\n\t\t\tentry = RenderBucket_QueueDraw((struct Instance *)curr, entry, player, lodMask, gameMode1, &queueState);"),
]

MF_ANCHOR = '\t// null terminator at end of list\n\t*RBI = 0;\n\t{ static int s_q4 = 0; if (s_q4 < 24) { s_q4++; Platform_Log("[trace] q4 f=%d\\n", (int)sdata->frameCounter); } }\n}'
MF_PROBE = '''\t// null terminator at end of list
\t*RBI = 0;
\t{ static int s_q4 = 0; if (s_q4 < 24) { s_q4++; Platform_Log("[trace] q4 f=%d\\n", (int)sdata->frameCounter); } }

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
            if work.count(o) == 0 and work.count(n_) >= 1:
                continue  # already applied
            if work.count(o) != 1:
                ok = False
                print("  %s anchor x%d: %s" % (nlname, work.count(o), old_s.splitlines()[0][:70]))
                break
            work = work.replace(o, n_)
        if ok:
            if work != text:
                io.open(path, "w", encoding="utf-8", newline="").write(work)
                print("%s: applied (%s)" % (label, nlname))
            else:
                print("%s: up to date (%s)" % (label, nlname))
            return True
    return False


ok_all = True
if not apply(QB, [(GLOBALS_OLD, GLOBALS_NEW)] + QB_PAIRS, "tree QB"):
    ok_all = False
if not apply(MF, [(MF_ANCHOR, MF_PROBE)], "tree MF"):
    ok_all = False

if not ok_all:
    sys.exit(2)
print("apply_tree_queue_probes: ok")
