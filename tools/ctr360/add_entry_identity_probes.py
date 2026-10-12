"""Identify the bucket entries that reach Execute with ptrCurrFrame==0, and
trace where QueueDraw actually writes entries (tree only)."""
import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
P = os.path.join(ROOT, "build-360", "gen", "game", "RenderBucket", "RenderBucket_QueueExecute.c")
t = io.open(P, encoding="utf-8", newline="").read()

NL = chr(92) + "n"

# 1) queue-side: print the exact entry slot written
old_q = ("\tg_ctr360_qdQueued++;\r\n\trbi->inst = inst;\r\n\trbi->instPlayerBase = instPlayerBase;\r\n")
new_q = ("\tg_ctr360_qdQueued++;\r\n"
         "\t{ static int s_qw = 0; if (s_qw < 24) { s_qw++; Platform_Log(\"[trace] qw f=%d rbi=%08x inst=%08x model=%08x" + NL + "\", "
         "(int)sdata->frameCounter, (unsigned)(u32)rbi, (unsigned)(u32)inst, (unsigned)(u32)inst->model); } }\r\n"
         "\trbi->inst = inst;\r\n\trbi->instPlayerBase = instPlayerBase;\r\n")
assert t.count(new_q) < 1 and t.count(old_q) == 1, (t.count(old_q), t.count(new_q))
t = t.replace(old_q, new_q)

# 2) execute-side: identify the mf==0 drop
old_d = ("\tif (mf == 0)\r\n\t{\r\n\t\tg_ctr360_qdDrop[7]++;\r\n\t\treturn 0;\r\n\t}",
         "if (mf == 0)\n\t{\n\t\tg_ctr360_qdDrop[7]++;\n\t\treturn 0;\n\t}")
done = False
for nl in ("\r\n", "\n"):
    o = old_d[0].replace("\r\n", nl)
    if t.count(o) == 0:
        continue
    ins = ("\t\t{ static int s_d7 = 0; if (s_d7 < 24) { s_d7++; Platform_Log(\"[trace] d7 f=%d inst=%08x model=%08x idpp=%08x curframe=%08x mh=%08x" + NL + "\", "
           "(int)sdata->frameCounter, (unsigned)(u32)inst, (unsigned)(u32)inst->model, (unsigned)(u32)idpp, (unsigned)(u32)mf, (unsigned)(u32)mh); } }\n")
    n = o if nl == "\n" else o
    n2 = ("\tif (mf == 0)" + nl + "\t{" + nl + "\t\tg_ctr360_qdDrop[7]++;" + nl + ins.replace("\n", nl) + "\t\treturn 0;" + nl + "\t}")
    t = t.replace(o, n2)
    done = True
    break
assert done, "d7 anchor not found"

io.open(P, "w", encoding="utf-8", newline="").write(t)
print("queue/execute identity probes added")
