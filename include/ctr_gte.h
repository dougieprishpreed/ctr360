#ifndef CTR_GTE_H
#define CTR_GTE_H

#include <ctr_math.h>
#include <psx/inline_c.h>
#include <psx/libgte.h>
#if defined(CTR_NATIVE)
#include <platform/native_precise.h>
#endif

static inline void CTR_GteLoadDelay(void)
{
#if !defined(CTR_NATIVE)
	__asm__ volatile("nop\n\t"
	                 "nop");
#endif
}

static inline void CTR_GteRegisterReadDelay(void)
{
#if !defined(CTR_NATIVE)
	__asm__ volatile("nop");
#endif
}

static inline void CTR_GteStoreU32(void *dst, u32 value)
{
	u8 *bytes = (u8 *)dst;

	bytes[0] = (u8)value;
	bytes[1] = (u8)(value >> 8);
	bytes[2] = (u8)(value >> 16);
	bytes[3] = (u8)(value >> 24);
}

static inline void CTR_GteLoadSV0(const SVECTOR *v)
{
	MTC2(CTR_PackS16Pair(v->vx, v->vy), 0);
	MTC2(CTR_PackS16Pair(v->vz, 0), 1);
}

static inline void CTR_GteLoadSV1(const SVECTOR *v)
{
	MTC2(CTR_PackS16Pair(v->vx, v->vy), 2);
	MTC2(CTR_PackS16Pair(v->vz, 0), 3);
}

static inline void CTR_GteLoadSV2(const SVECTOR *v)
{
	MTC2(CTR_PackS16Pair(v->vx, v->vy), 4);
	MTC2(CTR_PackS16Pair(v->vz, 0), 5);
}

static inline void CTR_GteLoadSV3(const SVECTOR *v0, const SVECTOR *v1, const SVECTOR *v2)
{
	CTR_GteLoadSV0(v0);
	CTR_GteLoadSV1(v1);
	CTR_GteLoadSV2(v2);
}

static inline void CTR_GteLoadSV3WithPad(const SVECTOR *v0, const SVECTOR *v1, const SVECTOR *v2)
{
	MTC2(CTR_PackS16Pair(v0->vx, v0->vy), 0);
	MTC2(CTR_PackS16Pair(v0->vz, v0->pad), 1);
	MTC2(CTR_PackS16Pair(v1->vx, v1->vy), 2);
	MTC2(CTR_PackS16Pair(v1->vz, v1->pad), 3);
	MTC2(CTR_PackS16Pair(v2->vx, v2->vy), 4);
	MTC2(CTR_PackS16Pair(v2->vz, v2->pad), 5);
}

static inline void CTR_GteLoadSVec3V0(const SVec3 *v)
{
#if defined(CTR_NATIVE)
	MTC2(CTR_PackS16Pair(v->x, v->y), 0);
	MTC2(CTR_PackS16Pair(v->z, 0), 1);
#else
	__asm__ volatile("lwc2 $0,0(%0)\n\t"
	                 "lwc2 $1,4(%0)"
	                 :
	                 : "r"(v));
#endif
}

static inline void CTR_GteLoadSVec3V1(const SVec3 *v)
{
	MTC2(CTR_PackS16Pair(v->x, v->y), 2);
	MTC2(CTR_PackS16Pair(v->z, 0), 3);
}

static inline void CTR_GteLoadSVec3V2(const SVec3 *v)
{
	MTC2(CTR_PackS16Pair(v->x, v->y), 4);
	MTC2(CTR_PackS16Pair(v->z, 0), 5);
}

static inline void CTR_GteLoadSVec3V3(const SVec3 *v0, const SVec3 *v1, const SVec3 *v2)
{
	CTR_GteLoadSVec3V0(v0);
	CTR_GteLoadSVec3V1(v1);
	CTR_GteLoadSVec3V2(v2);
}

static inline void CTR_GteLoadRotRow0SVec3(const SVec3 *v)
{
	u32 r13r21 = (CFC2(1) & 0xffff0000U) | (u16)v->z;

	CTC2(CTR_PackS16Pair(v->x, v->y), 0);
	CTC2(r13r21, 1);
}

static inline void CTR_GteLoadSVec4V0(const SVec4 *v)
{
	MTC2(CTR_PackS16Pair(v->x, v->y), 0);
	MTC2(CTR_PackS16Pair(v->z, v->w), 1);
}

static inline void CTR_GteLoadSVec3SlotV0(const SVec3Slot *v)
{
	MTC2(CTR_PackS16Pair(v->x, v->y), 0);
	MTC2(CTR_PackS16Pair(v->z, v->w), 1);
}

static inline void CTR_GteLoadS16TripletV0(const s16 *v)
{
	MTC2(CTR_PackS16Pair(v[0], v[1]), 0);
	MTC2(CTR_PackS16Pair(v[2], 0), 1);
}

static inline void CTR_GteLoadLVL(const s32 *v)
{
	MTC2((u32)v[0], 9);
	MTC2((u32)v[1], 10);
	MTC2((u32)v[2], 11);
}

/* NOTE(session 8/audit): SXY destinations are runtime primitive fields or
 * projected-vertex scratch read as native s16 pairs (MakeVertexTriangle reads
 * p0[0]/p0[1]; DrawLevelOvr1P rebuilds `(u16)posScreen[0] | posScreen[1] << 16`).
 * The old byte-wise LE store byte-swapped both coordinates on Xenon. The word
 * layout is x in the low half, y in the high half (C2_SX2/C2_SY2 and
 * CtrGpu_WritePackedXY agree). */
static __inline void CTR_GteStoreSXYWord(void *xy, u32 packed)
{
	s16 *half = (s16 *)xy;

	half[0] = (s16)packed;
	half[1] = (s16)(packed >> 16);
}

// Native SXY stores also record the sub-pixel position when the destination
// is a primitive field (platform/native_precise.c).
#if defined(CTR_NATIVE)
#define CTR_GtePreciseSXY(xy, slot) NativePrecise_StoreSXY((xy), (slot))
#else
#define CTR_GtePreciseSXY(xy, slot) ((void)0)
#endif

static __inline void CTR_GteStoreSXY(void *xy)
{
	CTR_GteStoreSXYWord(xy, MFC2(14));
	CTR_GtePreciseSXY(xy, 2);
}

static __inline void CTR_GteStoreSXY0(void *xy)
{
	CTR_GteStoreSXYWord(xy, MFC2(12));
	CTR_GtePreciseSXY(xy, 0);
}

static __inline void CTR_GteStoreSXY1(void *xy)
{
	CTR_GteStoreSXYWord(xy, MFC2(13));
	CTR_GtePreciseSXY(xy, 1);
}

static __inline void CTR_GteStoreSXY2(void *xy)
{
	CTR_GteStoreSXY(xy);
}

static __inline void CTR_GteStoreSXY3(void *xy0, void *xy1, void *xy2)
{
	CTR_GteStoreSXY0(xy0);
	CTR_GteStoreSXY1(xy1);
	CTR_GteStoreSXY(xy2);
}

static inline s32 CTR_GteReadMAC1(void)
{
	return MFC2_S(25);
}

#ifdef CTR_NATIVE
#define CTR_GteLoadLightMatrix(matrix) gte_SetLightMatrix(matrix)
#else
// NOTE(aalhendi): Preserve retail's paired loads and scratch-register
// clobbers when transferring the five lighting-matrix words to the GTE.
#define CTR_GteLoadLightMatrix(matrix)                               \
	({                                                               \
		const MATRIX *ctrLightMatrix = (matrix);                     \
		__asm__ volatile("lw $12,0(%0)\n\t"                          \
		                 "lw $13,4(%0)\n\t"                          \
		                 "ctc2 $12,$8\n\t"                           \
		                 "ctc2 $13,$9\n\t"                           \
		                 "lw $12,8(%0)\n\t"                          \
		                 "lw $13,12(%0)\n\t"                         \
		                 "lw $14,16(%0)\n\t"                         \
		                 "ctc2 $12,$10\n\t"                          \
		                 "ctc2 $13,$11\n\t"                          \
		                 "ctc2 $14,$12"                              \
		                 :                                           \
		                 : "r"(ctrLightMatrix), "m"(*ctrLightMatrix) \
		                 : "$12", "$13", "$14");                     \
	})
#endif

static __inline void CTR_GteStoreMAC(s32 *out)
{
#if defined(CTR_NATIVE)
	/* NOTE(session 7b): the destinations are PSX-model matrix translation
	 * fields that are read back with CTR_ReadU32LE - gte_SetTransMatrix in the
	 * render-bucket cull (RenderBucket_ProjectFrameBounds) and
	 * PushBuffer_SetMatrixVP's aspect scale on t[1]. Store little-endian like
	 * the PSX `sw` this replaces; a host-order store here byte-swapped the
	 * view-projection's Y translation every frame, every instance's projected
	 * bounds failed and no 3D was ever drawn (the screen stayed on the
	 * copyright page while the title ran in the log). */
	CTR_GteStoreU32(out + 0, (u32)MFC2(25));
	CTR_GteStoreU32(out + 1, (u32)MFC2(26));
	CTR_GteStoreU32(out + 2, (u32)MFC2(27));
#else
	register s32 value __asm__("$7");

	value = (s32)MFC2(25);
	__asm__ volatile("nop");
	out[0] = value;

	value = (s32)MFC2(26);
	__asm__ volatile("nop");
	out[1] = value;

	value = (s32)MFC2(27);
	__asm__ volatile("" : : "r"(value));
	out[2] = value;
#endif
}

/* World matrices and numeric vectors are native runtime state. Projection
 * matrices retain the PSX LE image expected by gte_SetTransMatrix/StoreMAC. */
static inline void CTR_GteSetRuntimeTransMatrix(const MATRIX *matrix)
{
#ifdef CTR_NATIVE
	CTC2((u32)matrix->t[0], 5);
	CTC2((u32)matrix->t[1], 6);
	CTC2((u32)matrix->t[2], 7);
#else
	gte_SetTransMatrix(matrix);
#endif
}

static inline void CTR_GteStoreRuntimeMAC(s32 *out)
{
#ifdef CTR_NATIVE
	out[0] = MFC2_S(25);
	out[1] = MFC2_S(26);
	out[2] = MFC2_S(27);
#else
	CTR_GteStoreMAC(out);
#endif
}

static inline void CTR_GteStoreIR(s32 *out)
{
	out[0] = (s32)MFC2(9);
	out[1] = (s32)MFC2(10);
	out[2] = (s32)MFC2(11);
}

static inline void CTR_GteStoreSV(SVECTOR *out)
{
	out->vx = (s16)MFC2(9);
	out->vy = (s16)MFC2(10);
	out->vz = (s16)MFC2(11);
}

static inline void CTR_GteStoreS16Triplet(s16 *out)
{
	out[0] = (s16)MFC2(9);
	out[1] = (s16)MFC2(10);
	out[2] = (s16)MFC2(11);
}

#endif
