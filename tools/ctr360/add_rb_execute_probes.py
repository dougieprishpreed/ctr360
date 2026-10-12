"""ctr360: RenderBucket execute-path instrumentation (repo + tree).

Adds per-window counters for every silent-drop surface in the
instance draw pipeline:
  RenderBucket_Execute            -> entries seen / prepare-ok / dispatched
  RenderBucket_PrepareDrawContext -> 8 early-out reasons
  RenderBucket_DispatchDrawFunc   -> setup-callback bail + unknown drawfunc id
  drawfunc switch                 -> per-case counts

Prints one `[probe] rbe ...` line every 30 execute calls and resets the window.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TREE = os.path.join(ROOT, "build-360", "gen")
REL = os.path.join("game", "RenderBucket", "RenderBucket_QueueExecute.c")

COUNTERS = '''#include <common.h>

/* ctr360 rb-execute diagnostics */
static u32 s_rbEnts;
static u32 s_rbOk;
static u32 s_rbDisp;
static u32 s_rbCase[5];
static u32 s_rbSetup0;
static u32 s_rbUnk;
static u32 s_rbUnkEC[4];
static u32 s_rbDrop[8];
static u32 s_rbPrint;

struct RenderBucketEntry'''

REPORT_FN = '''static void ctr360_RbExecuteReport(void)
{
	if ((s_rbPrint++ % 30) != 0)
	{
		return;
	}

	Platform_Log("[probe] rbe ents=%u ok=%u disp=%u cas=%u,%u,%u,%u,%u setup0=%u unk=%u ec=%u,%u,%u,%u drop=%u,%u,%u,%u,%u,%u,%u,%u\\n",
	             (unsigned)s_rbEnts, (unsigned)s_rbOk, (unsigned)s_rbDisp,
	             (unsigned)s_rbCase[0], (unsigned)s_rbCase[1], (unsigned)s_rbCase[2],
	             (unsigned)s_rbCase[3], (unsigned)s_rbCase[4],
	             (unsigned)s_rbSetup0, (unsigned)s_rbUnk,
	             (unsigned)s_rbUnkEC[0], (unsigned)s_rbUnkEC[1],
	             (unsigned)s_rbUnkEC[2], (unsigned)s_rbUnkEC[3],
	             (unsigned)s_rbDrop[0], (unsigned)s_rbDrop[1], (unsigned)s_rbDrop[2],
	             (unsigned)s_rbDrop[3], (unsigned)s_rbDrop[4], (unsigned)s_rbDrop[5],
	             (unsigned)s_rbDrop[6], (unsigned)s_rbDrop[7]);

	s_rbEnts = 0;
	s_rbOk = 0;
	s_rbDisp = 0;
	s_rbCase[0] = 0;
	s_rbCase[1] = 0;
	s_rbCase[2] = 0;
	s_rbCase[3] = 0;
	s_rbCase[4] = 0;
	s_rbSetup0 = 0;
	s_rbUnk = 0;
	s_rbUnkEC[0] = 0;
	s_rbUnkEC[1] = 0;
	s_rbUnkEC[2] = 0;
	s_rbUnkEC[3] = 0;
	s_rbDrop[0] = 0;
	s_rbDrop[1] = 0;
	s_rbDrop[2] = 0;
	s_rbDrop[3] = 0;
	s_rbDrop[4] = 0;
	s_rbDrop[5] = 0;
	s_rbDrop[6] = 0;
	s_rbDrop[7] = 0;
}

void RenderBucket_Execute(void *param_1, struct PrimMem *param_2)'''

PAIRS = [
    # counters at top of file
    ("#include <common.h>\n\n\nstruct RenderBucketEntry", COUNTERS),
    # report fn before Execute
    ("void RenderBucket_Execute(void *param_1, struct PrimMem *param_2)",
     REPORT_FN),
    # count entries + call report after the loop
    ("\tscratch->pushBufferPtr32 = 0;\n\tfor (; entry->inst != 0; entry++)\n\t{",
     "\tscratch->pushBufferPtr32 = 0;\n\tfor (; entry->inst != 0; entry++)\n\t{\n\t\ts_rbEnts++;"),
    ("\t\tRenderBucket_DispatchDrawFunc(&ctx);\n\t}\n}",
     "\t\tRenderBucket_DispatchDrawFunc(&ctx);\n\t}\n\n\tctr360_RbExecuteReport();\n}"),
    # prepare-ok / dispatch counting
    ("\t\tif (RenderBucket_PrepareDrawContext(&ctx, entry->inst, entry->instPlayerBase, param_2) == 0)\n\t\t{\n\t\t\tcontinue;\n\t\t}",
     "\t\tif (RenderBucket_PrepareDrawContext(&ctx, entry->inst, entry->instPlayerBase, param_2) == 0)\n\t\t{\n\t\t\tcontinue;\n\t\t}\n\t\ts_rbOk++;"),
    # early-out reasons
    ("\tif (inst == 0)\n\t{\n\t\treturn 0;\n\t}",
     "\tif (inst == 0)\n\t{\n\t\ts_rbDrop[0]++;\n\t\treturn 0;\n\t}"),
    ("\tif (inst->model == 0)\n\t{\n\t\treturn 0;\n\t}",
     "\tif (inst->model == 0)\n\t{\n\t\ts_rbDrop[1]++;\n\t\treturn 0;\n\t}"),
    ("\tif (pb == 0)\n\t{\n\t\treturn 0;\n\t}",
     "\tif (pb == 0)\n\t{\n\t\ts_rbDrop[2]++;\n\t\treturn 0;\n\t}"),
    ("\tif ((idpp->instFlags & 0x40) == 0)\n\t{\n\t\treturn 0;\n\t}",
     "\tif ((idpp->instFlags & 0x40) == 0)\n\t{\n\t\ts_rbDrop[3]++;\n\t\treturn 0;\n\t}"),
    ("\tif ((idpp->instFlags & 0x80) != 0)\n\t{\n\t\treturn 0;\n\t}",
     "\tif ((idpp->instFlags & 0x80) != 0)\n\t{\n\t\ts_rbDrop[4]++;\n\t\treturn 0;\n\t}"),
    ("\tif (mh == 0)\n\t{\n\t\treturn 0;\n\t}",
     "\tif (mh == 0)\n\t{\n\t\ts_rbDrop[5]++;\n\t\treturn 0;\n\t}"),
    ("\tif ((mh->ptrCommandList == 0) || (mh->ptrColors == 0))\n\t{\n\t\treturn 0;\n\t}",
     "\tif ((mh->ptrCommandList == 0) || (mh->ptrColors == 0))\n\t{\n\t\ts_rbDrop[6]++;\n\t\treturn 0;\n\t}"),
    ("\tif (mf == 0)\n\t{\n\t\treturn 0;\n\t}",
     "\tif (mf == 0)\n\t{\n\t\ts_rbDrop[7]++;\n\t\treturn 0;\n\t}"),
    # dispatch: setup callback bail
    ("\tif (RenderBucket_RunInstanceSetupCallback(ctx) == 0)\n\t{\n\t\treturn;\n\t}",
     "\tif (RenderBucket_RunInstanceSetupCallback(ctx) == 0)\n\t{\n\t\ts_rbSetup0++;\n\t\treturn;\n\t}"),
    # drawfunc cases
    ("\tcase RB_RETAIL_DRAWFUNC_NORMAL:\n\t\tRenderBucket_DrawFunc_Normal(ctx);\n\t\treturn;",
     "\tcase RB_RETAIL_DRAWFUNC_NORMAL:\n\t\ts_rbCase[0]++;\n\t\tRenderBucket_DrawFunc_Normal(ctx);\n\t\treturn;"),
    ("\tcase RB_RETAIL_DRAWFUNC_NORMAL_ALT:\n\t\tRenderBucket_DrawFunc_NormalAlt(ctx);\n\t\treturn;",
     "\tcase RB_RETAIL_DRAWFUNC_NORMAL_ALT:\n\t\ts_rbCase[1]++;\n\t\tRenderBucket_DrawFunc_NormalAlt(ctx);\n\t\treturn;"),
    ("\tcase RB_RETAIL_DRAWFUNC_SPLIT:\n\t\tRenderBucket_DrawFunc_Split(ctx);\n\t\treturn;",
     "\tcase RB_RETAIL_DRAWFUNC_SPLIT:\n\t\ts_rbCase[2]++;\n\t\tRenderBucket_DrawFunc_Split(ctx);\n\t\treturn;"),
    ("\tcase RB_RETAIL_DRAWFUNC_SPECIAL:\n\t\tRenderBucket_DrawFunc_Special(ctx);\n\t\treturn;",
     "\tcase RB_RETAIL_DRAWFUNC_SPECIAL:\n\t\ts_rbCase[3]++;\n\t\tRenderBucket_DrawFunc_Special(ctx);\n\t\treturn;"),
    ("\tcase RB_RETAIL_DRAWFUNC_REFLECTION:\n\t\tRenderBucket_DrawFunc_Reflection(ctx);\n\t\treturn;",
     "\tcase RB_RETAIL_DRAWFUNC_REFLECTION:\n\t\ts_rbCase[4]++;\n\t\tRenderBucket_DrawFunc_Reflection(ctx);\n\t\treturn;"),
    # default case: unknown drawfunc id
    ("\tdefault:\n\t\t// TODO(aalhendi): Port any newly observed draw handlers.\n\t\t// Do not fall through to normal draw; that masks live retail handler rows.\n\t\treturn;",
     "\tdefault:\n\t\ts_rbUnk++;\n\t\tif (s_rbUnk <= 4)\n\t\t{\n\t\t\ts_rbUnkEC[s_rbUnk - 1] = (u32)ctx->idpp->unkEC;\n\t\t}\n\t\t// TODO(aalhendi): Port any newly observed draw handlers.\n\t\t// Do not fall through to normal draw; that masks live retail handler rows.\n\t\treturn;"),
]


def apply(path, pairs, label):
    text = io.open(path, encoding="utf-8", newline="").read()
    for nlname, nl in (("CRLF", "\r\n"), ("LF", "\n")):
        work = text
        ok = True
        for old_s, new_s in pairs:
            o = old_s.replace("\n", nl)
            n_ = new_s.replace("\n", nl)
            if work.count(n_) == 1 and o not in work:
                continue  # already applied
            if work.count(o) != 1:
                ok = False
                print("  anchor x%d (%s): %s" % (work.count(o), nlname, old_s.splitlines()[0][:60]))
                break
            work = work.replace(o, n_)
        if ok and work != text:
            io.open(path, "w", encoding="utf-8", newline="").write(work)
            print("%s: applied (%s), %d bytes" % (label, nlname, len(work)))
            return True
    return False


ok_all = True
for label, base in (("repo", ROOT), ("tree", TREE)):
    if not apply(os.path.join(base, REL), PAIRS, label):
        ok_all = False

if not ok_all:
    sys.exit(2)
print("add_rb_execute_probes: ok")
