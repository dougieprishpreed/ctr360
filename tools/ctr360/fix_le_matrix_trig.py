"""ctr360 session 5: make the trig-table readers and the runtime matrix writers
byte-order-correct on the big-endian 360.

Root cause hunted in session 5: the retail-vs-360 byte order split.
  * `data.trigApprox` is HOST-COMPILED (game/zGlobal_DATA.c) as { s16 sin, cos },
    but every retail reader loads the pair as one PSX-LE word (sin low, cos
    high). On the 360 the LE word read returns the byte-swapped pair, so
    ConvertRotToMatrix produced a garbage camera matrix (cos 0x0010 instead of
    0x1000 - matches `[trace] sm` and the derived sm values).
  * Runtime matrices that carry LE reader conventions (inst->matrix rot words,
    idpp->mvp.t via gte_SetTransMatrix, pb->matrix_ViewProj rot words) were
    written with plain host stores, which byte-swap on the 360.

Fixes are semantics-preserving on little-endian hosts (byte-wise helpers equal
host loads there), so ctr-native/host builds keep working.

Applied to BOTH the repo copy and the build-360/gen tree copy.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

changed_total = 0


def load(path):
    return io.open(path, encoding="utf-8", newline="").read()


def save(path, text):
    io.open(path, "w", encoding="utf-8", newline="").write(text)


def rep(text, old, new, label, expect=1):
    """Replace `old` (LF form; CRLF variant tried too). Assert exact count.
    Idempotent: if `new` is already applied (and `old` is gone), skip."""
    global changed_total
    variants = [(old, new)]
    if "\n" in old:
        variants.append((old.replace("\n", "\r\n"), new.replace("\n", "\r\n")))
        if "\r\n" in old:
            variants.append((old.replace("\r\n", "\n"), new.replace("\r\n", "\n")))
    n = -1
    for o, nw in variants:
        c = text.count(o)
        if c:
            if c != expect:
                raise SystemExit("%s: %r matches %d, expected %d" % (label, o[:60], c, expect))
            text = text.replace(o, nw)
            n = c
            break
    if n < 0:
        # already applied?
        for o, nw in variants:
            if text.count(nw) == expect and text.count(o) == 0:
                return text
        raise SystemExit("%s: anchor not found: %r" % (label, old[:80]))
    changed_total += n
    return text


def edit(base_label, base, rel, fn):
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        raise SystemExit("missing %s: %s" % (base_label, path))
    text = load(path)
    text = fn(base_label, text)
    save(path, text)
    print("%-4s %s" % (base_label, rel))


# ---------------------------------------------------------------- trig helper
HELPER_OLD = """struct TrigPair
{
\ts32 sin;
\ts32 cos;
};
"""

HELPER_NEW = """struct TrigPair
{
\ts32 sin;
\ts32 cos;
};

// ctr360: the trig table is host-compiled as { s16 sin, s16 cos }, but retail
// reads each entry as one PSX little-endian word (sin in the low half, cos in
// the high half). On a big-endian target a raw word load swaps the pair, so
// rebuild the word from the fields. Identical to the LE word read on
// little-endian hosts.
static inline u32 CTR_TrigApproxWord(const struct TrigTable *entry)
{
\treturn (u32)(u16)entry->sin | ((u32)(u16)entry->cos << 16);
}
"""


def f_ctr_math(label, t):
    if "CTR_TrigApproxWord" in t:
        return t
    return rep(t, HELPER_OLD, HELPER_NEW, label + " ctr_math helper")


# ------------------------------------------------------- trig reader rewrites
# (old, new, expected, label)
TRIG_SITES = {
    "game/MATH/MATH_0_Sin.c": [
        ("u32 trig = CTR_ReadU32LE(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);",
         "u32 trig = CTR_TrigApproxWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);", 1),
    ],
    "game/MATH/MATH_1_Cos.c": [
        ("u32 trig = CTR_ReadU32LE(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);",
         "u32 trig = CTR_TrigApproxWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);", 1),
    ],
    "game/MATH/MATH_7_MatrixStubs.c": [
        ("u32 trig = CTR_ReadU32LE(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);",
         "u32 trig = CTR_TrigApproxWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);", 1),
    ],
    "game/MATH/TRIG_AngleSinCos.c": [
        ("u32 trig = CTR_ReadU32LE(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);",
         "u32 trig = CTR_TrigApproxWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);", 2),
    ],
    "game/RenderLevel/AnimateWater.c": [
        ("u32 packed = CTR_ReadU32LE(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);",
         "u32 packed = CTR_TrigApproxWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);", 1),
    ],
    "game/231/RB_Banner.c": [
        ("u32 packed = CTR_ReadU32AlignedLE(&data.trigApprox[(phase * 128) & ANG_QUADRANT_MASK]);",
         "u32 packed = CTR_TrigApproxWord(&data.trigApprox[(phase * 128) & ANG_QUADRANT_MASK]);", 1),
    ],
    "game/230/MM_Characters.c": [
        ("trigApprox = (s32)CTR_ReadU32AlignedLE(&((struct TrigTable *)trigApprox)[trigApproximationIndex & MM_CHARACTER_SELECT_COLOR_TRIG_MASK]);",
         "trigApprox = (s32)CTR_TrigApproxWord(&((struct TrigTable *)trigApprox)[trigApproximationIndex & MM_CHARACTER_SELECT_COLOR_TRIG_MASK]);", 1),
    ],
    "game/230/MM_TrackSelect.c": [
        ("packedTrig = CTR_ReadU32AlignedLE((u32 *)(trigIndex + ((u32)trigTable)));",
         "packedTrig = CTR_TrigApproxWord((const struct TrigTable *)(trigIndex + ((u32)trigTable)));", 1),
    ],
    "game/233/CS_Podium.c": [
        ("sine1 = CTR_ReadU32AlignedLE((const u8 *)base + (angle & 0x3ff) * 4);",
         "sine1 = CTR_TrigApproxWord((const struct TrigTable *)((const u8 *)base + (angle & 0x3ff) * 4));", 1),
        ("sine2 = CTR_ReadU32AlignedLE((const u8 *)base + (angle & 0x3ff) * 4);",
         "sine2 = CTR_TrigApproxWord((const struct TrigTable *)((const u8 *)base + (angle & 0x3ff) * 4));", 1),
    ],
    "game/232/AH_Map.c": [
        ("CTR_ReadU32AlignedLE(&table[angle & 0x3ff])",
         "CTR_TrigApproxWord(&table[angle & 0x3ff])", 3),
    ],
    "game/232/AH_MaskHint.c": [
        ("CTR_ReadU32AlignedLE(&table[angle & 0x3ff])",
         "CTR_TrigApproxWord(&table[angle & 0x3ff])", 2),
    ],
    "game/RaceFlag.c": [
        ("(s32)CTR_ReadU32AlignedLE(&table[angle & RACE_FLAG_TRIG_TABLE_MASK])",
         "(s32)CTR_TrigApproxWord(&table[angle & RACE_FLAG_TRIG_TABLE_MASK])", 3),
        ("(s32)CTR_ReadU32AlignedLE(&RACE_FLAG_TRIG[rippleAngle & RACE_FLAG_TRIG_TABLE_MASK])",
         "(s32)CTR_TrigApproxWord(&RACE_FLAG_TRIG[rippleAngle & RACE_FLAG_TRIG_TABLE_MASK])", 2),
    ],
    "game/DecalHUD.c": [
        ("sine = CTR_ReadU32LE(&table[rot & 0x3ff]);",
         "sine = CTR_TrigApproxWord(&table[rot & 0x3ff]);", 1),
    ],
    "game/DrawConfetti.c": [
        ("u32 packed = DrawConfetti_ReadWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)], 0);",
         "u32 packed = CTR_TrigApproxWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);", 1),
    ],
    "game/RenderWeather/RenderWeather.c": [
        ("u32 packed = RenderWeather_ReadWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)], 0);",
         "u32 packed = CTR_TrigApproxWord(&data.trigApprox[ANG_MODULO_HALF_PI(angle)]);", 1),
    ],
    "game/Vehicle/VehCommon.h": [
        ("#define VEH_TRIG_APPROX(index) CTR_ReadU32AlignedLE(&data.trigApprox[(index)])",
         "#define VEH_TRIG_APPROX(index) CTR_TrigApproxWord(&data.trigApprox[(index)])", 1),
    ],
    "game/Vehicle/VehPhysForce.c": [
        ("\t\tsine = *yTrigPtr;",
         "\t\tsine = (s32)CTR_TrigApproxWord((const struct TrigTable *)yTrigPtr);", 1),
        ("\t\tsine = xTrigPtr[xTrigIndex];",
         "\t\tsine = (s32)CTR_TrigApproxWord(&((const struct TrigTable *)xTrigPtr)[xTrigIndex]);", 1),
    ],
    "game/GAMEPAD.c": [
        # gamepadMapBtn is HOST-COMPILED static data; its rawInput words are read
        # directly everywhere else, so the LE word read swaps the mask on BE.
        ("(buttonMapRawInput = CTR_ReadU32LE(&buttonMap->rawInput[0]))",
         "(buttonMapRawInput = buttonMap->rawInput)", 1),
    ],
}


def make_trig_editor(rel):
    sites = TRIG_SITES[rel]

    def ed(label, t):
        for old, new, expect in sites:
            t = rep(t, old, new, label + " " + rel, expect)
        return t
    return ed


# ------------------------------------------------- PushBuffer_SetMatrixVP LE
def f_pushbuffer(label, t):
    label = label + " PushBuffer.c"
    # 1) m22 must be read the way retail's halfword load sees it (LE bytes).
    t = rep(t,
            "\tsVar7 = matrixDST->m[2][2];",
            "\tsVar7 = (s16)CTR_ReadU16LE(&matrixDST->m[2][2]);",
            label + " sVar7")
    # 2) matrix_Camera m22 store.
    t = rep(t,
            "\tpb->matrix_Camera.m[2][2] = sVar7;",
            "\tCTR_WriteU16LE(&pb->matrix_Camera.m[2][2], (u16)sVar7);",
            label + " camera m22")
    # 3) CameraTranspose words + m22.
    t = rep(t,
            "\t*(int *)((int)&pb->matrix_CameraTranspose + 0x0) = view0;\n"
            "\t*(int *)((int)&pb->matrix_CameraTranspose + 0x4) = view4;\n"
            "\t*(int *)((int)&pb->matrix_CameraTranspose + 0x8) = view8;\n"
            "\t*(int *)((int)&pb->matrix_CameraTranspose + 0xC) = viewC;\n"
            "\t*(s16 *)((int)&pb->matrix_CameraTranspose + 0x10) = sVar7;",
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_CameraTranspose + 0x0), view0);\n"
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_CameraTranspose + 0x4), view4);\n"
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_CameraTranspose + 0x8), view8);\n"
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_CameraTranspose + 0xC), viewC);\n"
            "\tCTR_WriteU16LE((void *)((int)&pb->matrix_CameraTranspose + 0x10), (u16)sVar7);",
            label + " transpose stores")
    # 4) ViewProj words + m22.
    t = rep(t,
            "\t*(int *)((int)&pb->matrix_ViewProj + 0x0) = view0;\n"
            "\t*(int *)((int)&pb->matrix_ViewProj + 0x4) = view4;\n"
            "\t*(int *)((int)&pb->matrix_ViewProj + 0x8) = view8;\n"
            "\t*(int *)((int)&pb->matrix_ViewProj + 0xC) = viewC;\n"
            "\t*(s16 *)((int)&pb->matrix_ViewProj + 0x10) = sVar7;",
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_ViewProj + 0x0), view0);\n"
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_ViewProj + 0x4), view4);\n"
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_ViewProj + 0x8), view8);\n"
            "\tCTR_WriteU32LE((void *)((int)&pb->matrix_ViewProj + 0xC), viewC);\n"
            "\tCTR_WriteU16LE((void *)((int)&pb->matrix_ViewProj + 0x10), (u16)sVar7);",
            label + " viewproj stores")
    # 5) Y-scale: read-modify-write through the LE halfword/word layout.
    t = rep(t,
            "\tpb->matrix_ViewProj.t[1] = pb->matrix_ViewProj.t[1] * r360 / r600;",
            "\t{ s32 vpScale = (s32)CTR_ReadU32LE(&pb->matrix_ViewProj.t[1]); CTR_WriteU32LE(&pb->matrix_ViewProj.t[1], (u32)(vpScale * r360 / r600)); }",
            label + " yscale t1")
    t = rep(t,
            "\tpb->matrix_ViewProj.m[1][0] = pb->matrix_ViewProj.m[1][0] * r360 / r600;",
            "\t{ s16 vpScale = (s16)CTR_ReadU16LE(&pb->matrix_ViewProj.m[1][0]); CTR_WriteU16LE(&pb->matrix_ViewProj.m[1][0], (u16)(vpScale * r360 / r600)); }",
            label + " yscale m10")
    t = rep(t,
            "\tpb->matrix_ViewProj.m[1][1] = pb->matrix_ViewProj.m[1][1] * r360 / r600;",
            "\t{ s16 vpScale = (s16)CTR_ReadU16LE(&pb->matrix_ViewProj.m[1][1]); CTR_WriteU16LE(&pb->matrix_ViewProj.m[1][1], (u16)(vpScale * r360 / r600)); }",
            label + " yscale m11")
    t = rep(t,
            "\tpb->matrix_ViewProj.m[1][2] = pb->matrix_ViewProj.m[1][2] * r360 / r600;",
            "\t{ s16 vpScale = (s16)CTR_ReadU16LE(&pb->matrix_ViewProj.m[1][2]); CTR_WriteU16LE(&pb->matrix_ViewProj.m[1][2], (u16)(vpScale * r360 / r600)); }",
            label + " yscale m12")
    return t


# --------------------------------------------------------- MM_Title_Init diag
def f_title(label, t):
    label = label + " MM_Title.c"
    t = rep(t,
            "\t\t\tinst->matrix.m[2][2] = TITLE_MATRIX_SCALE;\n"
            "\t\t\tinst->matrix.m[1][1] = TITLE_MATRIX_SCALE;\n"
            "\t\t\tinst->matrix.m[0][0] = TITLE_MATRIX_SCALE;",
            "\t\t\tCTR_WriteU16LE(&inst->matrix.m[2][2], TITLE_MATRIX_SCALE);\n"
            "\t\t\tCTR_WriteU16LE(&inst->matrix.m[1][1], TITLE_MATRIX_SCALE);\n"
            "\t\t\tCTR_WriteU16LE(&inst->matrix.m[0][0], TITLE_MATRIX_SCALE);",
            label + " title diag")
    return t


# ------------------------------------------------- RenderBucket mvp.t + reads
def f_renderbucket(label, t):
    label = label + " RenderBucket_QueueExecute.c"
    t = rep(t,
            "\tidpp->mvp.t[0] = viewPos->vx;\n"
            "\tidpp->mvp.t[1] = viewPos->vy;\n"
            "\tidpp->mvp.t[2] = viewPos->vz;",
            "\tRenderBucket_WriteMatrixWord(&idpp->mvp, offsetof(MATRIX, t[0]), (u32)viewPos->vx);\n"
            "\tRenderBucket_WriteMatrixWord(&idpp->mvp, offsetof(MATRIX, t[1]), (u32)viewPos->vy);\n"
            "\tRenderBucket_WriteMatrixWord(&idpp->mvp, offsetof(MATRIX, t[2]), (u32)viewPos->vz);",
            label + " mvp t stores")
    t = rep(t,
            "\tint viewX = idpp->mvp.t[0];\n"
            "\tint viewZ = idpp->mvp.t[2];",
            "\tint viewX = (s32)RenderBucket_ReadMatrixWord(&idpp->mvp, offsetof(MATRIX, t[0]));\n"
            "\tint viewZ = (s32)RenderBucket_ReadMatrixWord(&idpp->mvp, offsetof(MATRIX, t[2]));",
            label + " custom matrix reads")
    return t


# --------------------------------------------------------------- libgte.h diag
def f_libgte(label, t):
    label = label + " libgte.h"
    t = rep(t,
            "\tCTR_WriteU32AlignedLE(&m->m[2][0], 0);\n"
            "\tm->m[2][2] = 0x1000;",
            "\tCTR_WriteU32AlignedLE(&m->m[2][0], 0);\n"
            "\tCTR_WriteU16LE(&m->m[2][2], 0x1000);",
            label + " setRotIdentity")
    t = rep(t,
            "\tdst->m[2][2] = src->m[2][2];",
            "\tCTR_WriteU16LE(&dst->m[2][2], CTR_ReadU16LE(&src->m[2][2]));",
            label + " copyRot m22")
    return t


FILE_EDITS = [("include/ctr_math.h", f_ctr_math)]
for rel in TRIG_SITES:
    FILE_EDITS.append((rel, make_trig_editor(rel)))
FILE_EDITS += [
    ("game/PushBuffer.c", f_pushbuffer),
    ("game/230/MM_Title.c", f_title),
    ("game/RenderBucket/RenderBucket_QueueExecute.c", f_renderbucket),
    ("include/psx/libgte.h", f_libgte),
]

BASES = [("repo", ROOT), ("tree", os.path.join(ROOT, "build-360", "gen"))]

for rel, fn in FILE_EDITS:
    for label, base in BASES:
        edit(label, base, rel.replace("/", os.sep), fn)

print("total replacements: %d" % changed_total)
