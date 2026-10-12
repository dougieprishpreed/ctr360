"""Restore the headers==0 guard in the tree's QueueDraw: the old probe batch
had turned `if (X) { return rbi; }` into `if (X) { trace } { return rbi; }`,
i.e. an unconditional return for every instance (empty render bucket, no 3D).

Rewrite that site to the repo's semantics with our probes inside the if-body.
"""
import io

P = r"F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\gen\game\RenderBucket\RenderBucket_QueueExecute.c"
t = io.open(P, encoding="utf-8", newline="").read()

NL = chr(92) + "n"
i = t.find("\tif (inst->model->headers == 0)")
assert i != -1
j = t.find("#endif", i)
assert j != -1

block = (
    "\tif (inst->model->headers == 0)\r\n"
    "\t{\r\n"
    "\t\tg_ctr360_qdDrop[2]++;\r\n"
    '\t\t{ static int s_q9 = 0; if (s_q9 < 60) { s_q9++; Platform_Log("[trace] q9 f=%d hdr=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)(u32)inst->model->headers); } }\r\n'
    '\t\t{ static int s_qm = 0; if (s_qm < 36) { s_qm++; Platform_Log("[trace] qm f=%d inst=%08x model=%08x w0=%08x w1=%08x w2=%08x w3=%08x w4=%08x w5=%08x' + NL + '", (int)sdata->frameCounter, (unsigned)(u32)inst, (unsigned)(u32)inst->model, (unsigned)(u32)((u32 *)inst->model)[0], (unsigned)(u32)((u32 *)inst->model)[1], (unsigned)(u32)((u32 *)inst->model)[2], (unsigned)(u32)((u32 *)inst->model)[3], (unsigned)(u32)((u32 *)inst->model)[4], (unsigned)(u32)((u32 *)inst->model)[5]); } }\r\n'
    "\t\treturn rbi;\r\n"
    "\t}\r\n"
)

old = t[i:j]
t = t[:i] + block + t[j:]
io.open(P, "w", encoding="utf-8", newline="").write(t)
print("replaced %d chars with the corrected guard block" % len(old))
