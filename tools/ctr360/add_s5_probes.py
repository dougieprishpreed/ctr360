"""Session-5 probes (tree only):

  qi   QueueDraw identity per offered instance (menu window): instance name,
       model id/name, flags -- answers "are the six title models 0x66..0x6b
       offered?".
  qc   same for the cutscene window (cap 60).
  qd6  right after the qd4 stage: instance identity + inst->matrix words as
       HOST reads and LE reads (verifies the writer fix in-guest).
  vpw  PushBuffer_SetMatrixVP right after the u-var reads: cameraMatrix words
       (host + LE), uVar3..uVar6, sVar7 (verifies the trig fix: cos must be
       0x1000-family again, not 0x0010).
  tim  MM_Title_Init right after the diagonal writes: inst->matrix host + LE
       (diagonal must be 0x5000 under LE reads).
  tcp  MM_Title_CameraMove after the pushbuffer writes: raw cameraPath s16s
       (host) + resulting pos/rot -- the camera-path data is uncooked; this
       shows the byte-swapped values item 2 must cook.

Also re-arms the bd*/pj/pk traces from "first 20/12 ever" to sparse-forever so
menu-phase culls and bounds are visible in the log.
"""
import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GEN = os.path.join(ROOT, "build-360", "gen")
NL = chr(92) + "n"
CRLF = "\r\n"


def load(rel):
    return io.open(os.path.join(GEN, rel), encoding="utf-8", newline="").read()


def save(rel, t):
    io.open(os.path.join(GEN, rel), "w", encoding="utf-8", newline="").write(t)


def sub(t, old, new, label, expect=1):
    c = t.count(old)
    if c != expect:
        o2 = old.replace("\n", CRLF)
        n2 = new.replace("\n", CRLF)
        c2 = t.count(o2)
        if c2 == expect:
            return t.replace(o2, n2)
        raise SystemExit("%s: anchor x%d (crlf x%d, want %d): %r" % (label, c, c2, expect, old[:70]))
    return t.replace(old, new)


# ---------------------------------------------------------------- QueueDraw qi
RB = "game/RenderBucket/RenderBucket_QueueExecute.c"
qi_menu = ('\t{ static int s_qi = 0; if ((gameMode1 & 0x2000) && !(gameMode1 & 0x40000000) && s_qi < 150) { s_qi++; Platform_Log("[trace] qi f=%d inst=%08x mid=%d mn=%08x,%08x in=%08x,%08x fl=%08x' + NL + '", '
           '(int)sdata->frameCounter, (unsigned)(u32)inst, (int)inst->model->id, (unsigned)ModelName_ReadWord(inst->model->name, 0), (unsigned)ModelName_ReadWord(inst->model->name, 1), (unsigned)ModelName_ReadWord(inst->name, 0), (unsigned)ModelName_ReadWord(inst->name, 1), (unsigned)inst->flags); } }')
qi_cut = ('\t{ static int s_qc = 0; if (!(gameMode1 & 0x2000) && s_qc < 60) { s_qc++; Platform_Log("[trace] qc f=%d inst=%08x mid=%d mn=%08x,%08x in=%08x,%08x fl=%08x' + NL + '", '
          '(int)sdata->frameCounter, (unsigned)(u32)inst, (int)inst->model->id, (unsigned)ModelName_ReadWord(inst->model->name, 0), (unsigned)ModelName_ReadWord(inst->model->name, 1), (unsigned)ModelName_ReadWord(inst->name, 0), (unsigned)ModelName_ReadWord(inst->name, 1), (unsigned)inst->flags); } }')
qd4_tail = '(unsigned)((u32 *)&projectionMvp)[4]); } }'
qd6 = ('\n\t{ static int s_qd6 = 0; if ((s_qd6++ % 30) == 0) { Platform_Log("[trace] qd6 f=%d mid=%d in=%08x,%08x H=%08x,%08x,%08x,%08x,%08x L=%08x,%08x,%08x,%08x,%08x' + NL + '", '
       '(int)sdata->frameCounter, (int)inst->model->id, (unsigned)ModelName_ReadWord(inst->name, 0), (unsigned)ModelName_ReadWord(inst->name, 1), '
       '(unsigned)((u32 *)&inst->matrix)[0], (unsigned)((u32 *)&inst->matrix)[1], (unsigned)((u32 *)&inst->matrix)[2], (unsigned)((u32 *)&inst->matrix)[3], (unsigned)((u32 *)&inst->matrix)[4], '
       '(unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 0), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 4), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 8), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 12), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 16)); } }')

t = load(RB)
t = sub(t, "\tqueuedFlags = inst->flags;" + CRLF,
        "\tqueuedFlags = inst->flags;" + CRLF + qi_menu + CRLF + qi_cut + CRLF, "queue entry")
t = sub(t, qd4_tail, qd4_tail + qd6, "qd6")
save(RB, t)
print("patched", RB)

# ------------------------------------------- PushBuffer vpw (camera matrix)
PB = "game/PushBuffer.c"
vpw = ('\n\t{ static int s_vpw = 0; if ((s_vpw++ % 30) == 0) { Platform_Log("[trace] vpw f=%d cmH=%08x,%08x,%08x,%08x,%08x cmL=%08x,%08x,%08x,%08x,%08x u=%08x,%08x,%08x,%08x,s7=%04x' + NL + '", '
       '(int)sdata->frameCounter, '
       '(unsigned)((const u32 *)matrixDST)[0], (unsigned)((const u32 *)matrixDST)[1], (unsigned)((const u32 *)matrixDST)[2], (unsigned)((const u32 *)matrixDST)[3], (unsigned)((const u32 *)matrixDST)[4], '
       '(unsigned)CTR_ReadU32LE((const u8 *)matrixDST + 0), (unsigned)CTR_ReadU32LE((const u8 *)matrixDST + 4), (unsigned)CTR_ReadU32LE((const u8 *)matrixDST + 8), (unsigned)CTR_ReadU32LE((const u8 *)matrixDST + 12), (unsigned)CTR_ReadU32LE((const u8 *)matrixDST + 16), '
       '(unsigned)uVar3, (unsigned)uVar4, (unsigned)uVar5, (unsigned)uVar6, (unsigned)(u16)sVar7); } }')
t = load(PB)
t = sub(t, "\tsVar7 = (s16)CTR_ReadU16LE(&matrixDST->m[2][2]);" + CRLF,
        "\tsVar7 = (s16)CTR_ReadU16LE(&matrixDST->m[2][2]);" + CRLF + vpw, "vpw")
save(PB, t)
print("patched", PB)

# ------------------------------------------------- MM_Title tim + tcp probes
TITLE = "game/230/MM_Title.c"
tim = ('\n\t\t\t{ static int s_tim = 0; if (s_tim < 8) { s_tim++; Platform_Log("[trace] tim i=%d H=%08x,%08x,%08x,%08x,%08x L=%08x,%08x,%08x,%08x,%08x' + NL + '", '
       '(int)instanceIndex, '
       '(unsigned)((u32 *)&inst->matrix)[0], (unsigned)((u32 *)&inst->matrix)[1], (unsigned)((u32 *)&inst->matrix)[2], (unsigned)((u32 *)&inst->matrix)[3], (unsigned)((u32 *)&inst->matrix)[4], '
       '(unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 0), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 4), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 8), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 12), (unsigned)CTR_ReadU32LE((const u8 *)&inst->matrix + 16)); } }')
tcp = ('\n\t{ static int s_tcp = 0; if ((s_tcp++ % 30) == 0) { Platform_Log("[trace] tcp f=%d fi=%d p=%d,%d,%d r=%d,%d,%d pbr=%d,%d,%d' + NL + '", '
       '(int)sdata->frameCounter, (int)frameIndex, (int)cameraPath[-3], (int)cameraPath[-2], (int)cameraPath[-1], (int)cameraPath[0], (int)cameraPath[1], (int)cameraPath[2], '
       '(int)pushBuffer->rot.x, (int)pushBuffer->rot.y, (int)pushBuffer->rot.z); } }')
t = load(TITLE)
t = sub(t, "\t\t\tCTR_WriteU16LE(&inst->matrix.m[0][0], TITLE_MATRIX_SCALE);" + CRLF,
        "\t\t\tCTR_WriteU16LE(&inst->matrix.m[0][0], TITLE_MATRIX_SCALE);" + CRLF + tim, "tim")
t = sub(t, "\tpushBuffer->rot.z = cameraPath[2] + (s16)((MM_TITLE_CAMERA_ROT.z * result) >> 0xc);" + CRLF,
        "\tpushBuffer->rot.z = cameraPath[2] + (s16)((MM_TITLE_CAMERA_ROT.z * result) >> 0xc);" + CRLF + tcp, "tcp")
save(TITLE, t)
print("patched", TITLE)

# ------------------------------------------- re-arm sparse-forever trace caps
REARMS = [
    ("if (s_bdx < 20) { s_bdx++; ", "if ((s_bdx++ % 60) == 0) { "),
    ("if (s_bdy < 20) { s_bdy++; ", "if ((s_bdy++ % 60) == 0) { "),
    ("if (s_bdz < 20) { s_bdz++; ", "if ((s_bdz++ % 60) == 0) { "),
    ("if (s_bdx2 < 20) { s_bdx2++; ", "if ((s_bdx2++ % 60) == 0) { "),
    ("if (s_bdy2 < 20) { s_bdy2++; ", "if ((s_bdy2++ % 60) == 0) { "),
    ("if (s_pj < 12) { s_pj++; ", "if ((s_pj++ % 120) == 0) { "),
    ("if (s_pk < 12) { s_pk++; ", "if ((s_pk++ % 120) == 0) { "),
]
t = load(RB)
for old, new in REARMS:
    t = sub(t, old, new, "rearm " + old.split("s_")[1].split(" ")[0])
save(RB, t)
print("re-armed bd*/pj/pk")

print("probes ok")
