"""Probe RainLogic/PushBuffer_SetMatrixVP: does the per-frame view-projection
compose run, and what do pb->rot/pos + the result look like (tree only)."""
import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
NL = chr(92) + "n"

# 1) RainLogic (MainFrame_RenderFrame.c): print after the frustum update
P1 = os.path.join(ROOT, "build-360", "gen", "game", "MAIN", "MainFrame_RenderFrame.c")
t1 = io.open(P1, encoding="utf-8", newline="").read()
a1 = "\t\tPushBuffer_UpdateFrustum(&gGT->pushBuffer[i]);\r\n"
assert t1.count(a1) == 1, t1.count(a1)
n1 = (a1 +
      '\t\t{ static int s_rl = 0; if (s_rl < 12) { s_rl++; Platform_Log("[trace] rl f=%d i=%d rot=%d,%d,%d pos=%d,%d,%d' + NL + '", '
      "(int)sdata->frameCounter, (int)i, (int)gGT->pushBuffer[i].rot.x, (int)gGT->pushBuffer[i].rot.y, (int)gGT->pushBuffer[i].rot.z, "
      "(int)gGT->pushBuffer[i].pos.x, (int)gGT->pushBuffer[i].pos.y, (int)gGT->pushBuffer[i].pos.z); } }\r\n")
t1 = t1.replace(a1, n1)
io.open(P1, "w", encoding="utf-8", newline="").write(t1)
print("RainLogic probe added")

# 2) PushBuffer_SetMatrixVP (PushBuffer.c): print the composed ViewProj words
P2 = os.path.join(ROOT, "build-360", "gen", "game", "PushBuffer.c")
t2 = io.open(P2, encoding="utf-8", newline="").read()
a2 = "\tpb->matrix_ViewProj.t[1] = pb->matrix_ViewProj.t[1] * r360 / r600;\r\n"
assert t2.count(a2) == 1, t2.count(a2)
n2 = (a2 +
      '\t{ static int s_sm = 0; if (s_sm < 12) { s_sm++; Platform_Log("[trace] sm f=%d rot=%d,%d,%d vp=%08x,%08x,%08x,%08x,%08x t=%d,%d,%d' + NL + '", '
      "(int)sdata->frameCounter, (int)pb->rot.x, (int)pb->rot.y, (int)pb->rot.z, "
      "(unsigned)((u32 *)&pb->matrix_ViewProj)[0], (unsigned)((u32 *)&pb->matrix_ViewProj)[1], (unsigned)((u32 *)&pb->matrix_ViewProj)[2], "
      "(unsigned)((u32 *)&pb->matrix_ViewProj)[3], (unsigned)((u32 *)&pb->matrix_ViewProj)[4], "
      "(int)pb->matrix_ViewProj.t[0], (int)pb->matrix_ViewProj.t[1], (int)pb->matrix_ViewProj.t[2]); } }\r\n")
t2 = t2.replace(a2, n2)
io.open(P2, "w", encoding="utf-8", newline="").write(t2)
print("SetMatrixVP probe added")

# keep the tree's main frame probes minimal: nothing else
