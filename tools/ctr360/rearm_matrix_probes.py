"""Re-arm the VP probes as sparse forever-probes and dump the matrix sources
in QueueDraw (tree only)."""
import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
NL = chr(92) + "n"

# --- 1) rl probe: every 60th call, uncapped
P1 = os.path.join(ROOT, "build-360", "gen", "game", "MAIN", "MainFrame_RenderFrame.c")
t1 = io.open(P1, encoding="utf-8", newline="").read()
old = '{ static int s_rl = 0; if (s_rl < 12) { s_rl++;'
new = '{ static int s_rl = 0; if ((s_rl++ % 60) == 0) {'
assert t1.count(old) == 1
t1 = t1.replace(old, new)
io.open(P1, "w", encoding="utf-8", newline="").write(t1)
print("rl probe -> sparse")

# --- 2) sm probe: every 60th call
P2 = os.path.join(ROOT, "build-360", "gen", "game", "PushBuffer.c")
t2 = io.open(P2, encoding="utf-8", newline="").read()
old2 = '{ static int s_sm = 0; if (s_sm < 12) { s_sm++;'
new2 = '{ static int s_sm = 0; if ((s_sm++ % 60) == 0) {'
assert t2.count(old2) == 1
t2 = t2.replace(old2, new2)
io.open(P2, "w", encoding="utf-8", newline="").write(t2)
print("sm probe -> sparse")

# --- 3) qd4 probe: sparse + matrix sources
P3 = os.path.join(ROOT, "build-360", "gen", "game", "RenderBucket", "RenderBucket_QueueExecute.c")
t3 = io.open(P3, encoding="utf-8", newline="").read()
old3 = '{ static int s_qd4 = 0; if (s_qd4 < 24) { s_qd4++; Platform_Log("[trace] qd4 f=%d' + NL + '", (int)sdata->frameCounter); } }'
assert t3.count(old3) == 1, t3.count(old3)
new3 = ('{ static int s_qd4 = 0; if ((s_qd4++ % 30) == 0) { Platform_Log("[trace] qd4 f=%d m=%08x,%08x,%08x,%08x,%08x vp=%08x,%08x,%08x im=%08x,%08x,%08x mvp=%08x,%08x,%08x,%08x,%08x' + NL + '", '
        '(int)sdata->frameCounter, '
        '(unsigned)matrixState.m0, (unsigned)matrixState.m1, (unsigned)matrixState.m2, (unsigned)matrixState.m3, (unsigned)matrixState.m4, '
        '(unsigned)((u32 *)&pb->matrix_ViewProj)[0], (unsigned)((u32 *)&pb->matrix_ViewProj)[1], (unsigned)((u32 *)&pb->matrix_ViewProj)[2], '
        '(unsigned)((u32 *)&inst->matrix)[0], (unsigned)((u32 *)&inst->matrix)[1], (unsigned)((u32 *)&inst->matrix)[2], '
        '(unsigned)((u32 *)&projectionMvp)[0], (unsigned)((u32 *)&projectionMvp)[1], (unsigned)((u32 *)&projectionMvp)[2], (unsigned)((u32 *)&projectionMvp)[3], (unsigned)((u32 *)&projectionMvp)[4]); } }')
t3 = t3.replace(old3, new3)
io.open(P3, "w", encoding="utf-8", newline="").write(t3)
print("qd4 probe -> sparse with matrix sources")
