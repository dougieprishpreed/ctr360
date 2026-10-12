"""Insert a one-shot model-dump trace at the headers==0 drop site (tree only)."""
import io

P = r"F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\gen\game\RenderBucket\RenderBucket_QueueExecute.c"
t = io.open(P, encoding="utf-8", newline="").read()

anchor = "g_ctr360_qdDrop[2]++;"
assert t.count(anchor) == 1, t.count(anchor)

dump = """g_ctr360_qdDrop[2]++;
\t\t{ static int s_qm = 0; if (s_qm < 36) { s_qm++; Platform_Log("[trace] qm f=%d inst=%08x model=%08x w0=%08x w1=%08x w2=%08x w3=%08x w4=%08x w5=%08x", (int)sdata->frameCounter, (unsigned)(u32)inst, (unsigned)(u32)inst->model, (unsigned)(u32)((u32 *)inst->model)[0], (unsigned)(u32)((u32 *)inst->model)[1], (unsigned)(u32)((u32 *)inst->model)[2], (unsigned)(u32)((u32 *)inst->model)[3], (unsigned)(u32)((u32 *)inst->model)[4], (unsigned)(u32)((u32 *)inst->model)[5]); if (s_qm == 36) { Platform_Log("\\n"); } } }"""

t = t.replace(anchor, dump, 1)
io.open(P, "w", encoding="utf-8", newline="").write(t)
print("inserted qm dump trace")
