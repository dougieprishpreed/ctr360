"""Repair the broken qm trace insertion in the tree's QueueDraw drop block."""
import io

P = r"F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\gen\game\RenderBucket\RenderBucket_QueueExecute.c"
t = io.open(P, encoding="utf-8", newline="").read()

NL = chr(92) + "n"  # the two characters \ n as they must appear in a C literal

start_marker = "\t\t{ static int s_qm = 0;"
i = t.find(start_marker)
assert i != -1, "start marker not found"
end_marker = '"); } } }'
j = t.find(end_marker, i)
assert j != -1, "end marker not found"
j += len(end_marker)

good = ('\t\t{ static int s_qm = 0; if (s_qm < 36) { s_qm++; '
        'Platform_Log("[trace] qm f=%d inst=%08x model=%08x w0=%08x w1=%08x w2=%08x w3=%08x w4=%08x w5=%08x' + NL + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)inst, (unsigned)(u32)inst->model, '
        '(unsigned)(u32)((u32 *)inst->model)[0], (unsigned)(u32)((u32 *)inst->model)[1], '
        '(unsigned)(u32)((u32 *)inst->model)[2], (unsigned)(u32)((u32 *)inst->model)[3], '
        '(unsigned)(u32)((u32 *)inst->model)[4], (unsigned)(u32)((u32 *)inst->model)[5]); } }')

t = t[:i] + good + t[j:]
io.open(P, "w", encoding="utf-8", newline="").write(t)
print("repaired qm trace (%d chars replaced with %d)" % (j - i, len(good)))
