/* ctr360 host unit test: the GTE light/rot matrix multiply chain used by
 * RenderBucket_BuildM3x3 / BuildMvp, against hand-computed references.
 *
 * Runs the REAL helper functions (MATRIX_SET_r11r12r13r14r15,
 * Unknown_8006c600, Unknown_8006c558, Unknown_8006c49c) on the REAL scalar GTE
 * (platform/native_inline_c.c + platform/native_gte_core.c + the game TUs).
 *
 * The test executes on the little-endian host, i.e. it reproduces ctr-native's
 * reference behaviour. It also replays the same inputs with the bytes swapped
 * (what the 360 saw before the session-5 fixes) to document the collapse.
 *
 * Build: see tools/ctr360/run_gte_unit_test.sh
 */
#include <common.h>
#include <psx/gtereg.h>   /* CTR_GTE_BIG_ENDIAN + the PAIR layout under test */
#include <stdio.h>
#include <string.h>

/* the retail data section the trig helpers read (normally game/zGlobal_DATA.c) */
struct Data data;
struct sData sdata_static;

/* pull the real matrix-helper TU in once (the retail build's unity style); it
 * brings MATRIX_SET_*, Unknown_8006c49c, Unknown_8006c558 and
 * ConvertRotToMatrix without a second regionsEXE.h definition of sdata. */
#include "../../game/MATH/MATH_7_MatrixStubs.c"

static int failures = 0;

static void dump5(const char *tag, u32 *w)
{
	printf("%-22s %08x %08x %08x %08x %08x\n", tag, (unsigned)w[0], (unsigned)w[1], (unsigned)w[2], (unsigned)w[3], (unsigned)w[4]);
}

/* The five-word read used by RenderBucket_LoadMatrixWords (offsetof-based). */
static void load_matrix_words(const MATRIX *m, u32 *w)
{
	w[0] = CTR_ReadU32LE((const u8 *)m + offsetof(MATRIX, m[0][0]));
	w[1] = CTR_ReadU32LE((const u8 *)m + offsetof(MATRIX, m[0][2]));
	w[2] = CTR_ReadU32LE((const u8 *)m + offsetof(MATRIX, m[1][1]));
	w[3] = CTR_ReadU32LE((const u8 *)m + offsetof(MATRIX, m[2][0]));
	w[4] = CTR_ReadU32LE((const u8 *)m + offsetof(MATRIX, m[2][2]));
}

static void store_matrix_words(MATRIX *m, const u32 *w)
{
	CTR_WriteU32LE((u8 *)m + offsetof(MATRIX, m[0][0]), w[0]);
	CTR_WriteU32LE((u8 *)m + offsetof(MATRIX, m[0][2]), w[1]);
	CTR_WriteU32LE((u8 *)m + offsetof(MATRIX, m[1][1]), w[2]);
	CTR_WriteU32LE((u8 *)m + offsetof(MATRIX, m[2][0]), w[3]);
	CTR_WriteU32LE((u8 *)m + offsetof(MATRIX, m[2][2]), w[4]);
}

static u32 pack_xy(int x, int y)
{
	return ((u32)(u16)x) | ((u32)(u16)y << 16);
}

/* Replica of RenderBucket_BuildM3x3's register choreography (the function is
 * static inside RenderBucket_QueueExecute.c; the choreography is copied here
 * verbatim and documented against the helper calls it makes). */
static void build_m3x3(const MATRIX *instMatrix, const SVec3 *mhScale, int viewDepth, u32 *out)
{
	u32 m0, m1, m2, m3, m4;
	u32 packedScaleXY;
	int depthShift = (viewDepth < 0x1000) ? 2 : 0;
	int scaleXYShift = 0x12 - depthShift;
	int scaleZShift = 2 - depthShift;
	int scaleX = 0x1000, scaleY = 0x1000, scaleZ = 0x1000;
	u32 scaledX, scaledY, scaledZ;

	m0 = CTR_ReadU32LE((const u8 *)instMatrix + offsetof(MATRIX, m[0][0]));
	m1 = CTR_ReadU32LE((const u8 *)instMatrix + offsetof(MATRIX, m[0][2]));
	m2 = CTR_ReadU32LE((const u8 *)instMatrix + offsetof(MATRIX, m[1][1]));
	m3 = CTR_ReadU32LE((const u8 *)instMatrix + offsetof(MATRIX, m[2][0]));
	m4 = CTR_ReadU32LE((const u8 *)instMatrix + offsetof(MATRIX, m[2][2]));
	MATRIX_SET_r11r12r13r14r15(m0, m1, m2, m3, m4);

	packedScaleXY = CTR_ReadU32LE(&mhScale->x);

	CTC2((packedScaleXY << 16) >> scaleXYShift, 16);
	CTC2(0, 17);
	CTC2(packedScaleXY >> scaleXYShift, 18);
	CTC2(0, 19);
	/* session-6: the real BuildM3x3 reads scale.z little-endian too (the
	 * cooked image keeps the model scale LE); a plain struct read byte-swaps
	 * it on the big-endian 360 and fed the m3x3 a garbage z column. */
	CTC2((u32)CTR_ReadU16LE(&mhScale->z) >> scaleZShift, 20);

	MTC2(pack_xy(scaleX, scaleY), 0);
	MTC2(scaleZ, 1);
	doCOP2(0x04c6012); /* gte_lcv0 */

	scaledX = MFC2(9);
	scaledY = MFC2(10);
	scaledZ = MFC2(11);

	m0 = scaledX & 0xffff;
	m1 = 0;
	m2 = scaledY & 0xffff;
	m3 = 0;
	m4 = scaledZ & 0xffff;
	Unknown_8006c49c(&m0, &m1, &m2, &m3, &m4);
	out[0] = m0;
	out[1] = m1;
	out[2] = m2;
	out[3] = m3;
	out[4] = m4;
}

/* Replica of RenderBucket_BuildMvp. */
static void build_mvp(const MATRIX *m3x3, const MATRIX *viewProj, MATRIX *mvpOut, u32 *tupleOut)
{
	u32 m0, m1, m2, m3, m4;
	u32 w[5];

	load_matrix_words(m3x3, w);
	m0 = w[0]; m1 = w[1]; m2 = w[2]; m3 = w[3]; m4 = w[4];
	Unknown_8006c600(CTR_ReadU32LE((const u8 *)viewProj + offsetof(MATRIX, m[0][0])),
	                 CTR_ReadU32LE((const u8 *)viewProj + offsetof(MATRIX, m[0][2])),
	                 CTR_ReadU32LE((const u8 *)viewProj + offsetof(MATRIX, m[1][1])),
	                 CTR_ReadU32LE((const u8 *)viewProj + offsetof(MATRIX, m[2][0])),
	                 CTR_ReadU32LE((const u8 *)viewProj + offsetof(MATRIX, m[2][2])));
	Unknown_8006c558(&m0, &m1, &m2, &m3, &m4);
	w[0] = m0; w[1] = m1; w[2] = m2; w[3] = m3; w[4] = m4;
	store_matrix_words(mvpOut, w);
	if (tupleOut)
	{
		memcpy(tupleOut, w, sizeof(w));
	}
}

static u32 bswap32(u32 v)
{
	return ((v >> 24) & 0xff) | ((v >> 8) & 0xff00) | ((v << 8) & 0xff0000) | (v << 24);
}

static void make_diag(MATRIX *m, int d00, int d11, int d22)
{
	memset(m, 0, sizeof(*m));
	CTR_WriteU16LE(&m->m[0][0], (u16)d00);
	CTR_WriteU16LE(&m->m[1][1], (u16)d11);
	CTR_WriteU16LE(&m->m[2][2], (u16)d22);
}

static void make_matrix(MATRIX *m, const int v[9])
{
	int i, j;
	memset(m, 0, sizeof(*m));
	for (i = 0; i < 3; i++)
	{
		for (j = 0; j < 3; j++)
		{
			CTR_WriteU16LE((u8 *)&m->m[i][j], (u16)v[i * 3 + j]);
		}
	}
}

/* plain math reference: out = A x B over the unpacked s16 elements */
static void ref_mul(const int *a, const int *b, int *out)
{
	int i, j, k;
	for (i = 0; i < 3; i++)
	{
		for (j = 0; j < 3; j++)
		{
			int acc = 0;
			for (k = 0; k < 3; k++)
			{
				acc += a[i * 3 + k] * b[k * 3 + j];
			}
			out[i * 3 + j] = acc;
		}
	}
}

static void unpack_tuple(const u32 *w, int *m)
{
	m[0] = (s16)(w[0] & 0xffff);
	m[1] = (s16)(w[0] >> 16);
	m[2] = (s16)(w[1] & 0xffff);
	m[3] = (s16)(w[1] >> 16);
	m[4] = (s16)(w[2] & 0xffff);
	m[5] = (s16)(w[2] >> 16);
	m[6] = (s16)(w[3] & 0xffff);
	m[7] = (s16)(w[3] >> 16);
	m[8] = (s16)(w[4] & 0xffff);
}

static void check(const char *label, long got, long want)
{
	int ok = (got == want);
	if (!ok)
	{
		failures++;
	}
	printf("  [%s] %-46s got %ld want %ld\n", ok ? "PASS" : "FAIL", label, got, want);
}

int main(void)
{
	/* trig table entries the helpers read (retail values) */
	data.trigApprox[0].sin = 0x0000;
	data.trigApprox[0].cos = 0x1000;
	data.trigApprox[1].sin = 0x0006;
	data.trigApprox[1].cos = 0x0fff;

	printf("== CTR_GTE_BIG_ENDIAN=%d (%s) ==\n", (int)CTR_GTE_BIG_ENDIAN,
	       CTR_GTE_BIG_ENDIAN ? "360 register layout, emulated on the host" : "PSX/host little-endian layout");

	printf("== CTR_TrigApproxWord ==\n");
	check("trig word [0] == 0x10000000", (long)(u32)CTR_TrigApproxWord(&data.trigApprox[0]), 0x10000000L);
	check("trig word [1] == 0x0fff0006", (long)(u32)CTR_TrigApproxWord(&data.trigApprox[1]), 0x0fff0006L);

	printf("== ConvertRotToMatrix(0,0,0) -> identity ==\n");
	{
		SVec3 rot;
		MATRIX m;
		u32 w[5];
		rot.x = 0; rot.y = 0; rot.z = 0;
		ConvertRotToMatrix(&m, &rot);
		load_matrix_words(&m, w);
		dump5("identity tuple:", w);
		check("w0 low == 0x1000", (long)(s16)(w[0] & 0xffff), 0x1000);
		check("w2 low == 0x1000", (long)(s16)(w[2] & 0xffff), 0x1000);
		check("w4 low == 0x1000", (long)(s16)(w[4] & 0xffff), 0x1000);
		check("w1 == 0", (long)w[1], 0L);
		check("w3 == 0", (long)w[3], 0L);
	}

	printf("== build_m3x3: inst diag(0x5000) x mh.scale(0x1000,0x1000,0x1000) ==\n");
	{
		MATRIX inst;
		SVec3 scale;
		u32 tuple[5];
		int *unp;
		make_diag(&inst, 0x5000, 0x5000, 0x5000);
		scale.x = 0x1000; scale.y = 0x1000; scale.z = 0x1000;
		build_m3x3(&inst, &scale, 0x100, tuple);
		dump5("m3x3 tuple:", tuple);
		unp = (int *)tuple; /* only used via unpack below */
		{
			int m[9];
			unpack_tuple(tuple, m);
			printf("  unpacked: %d %d %d / %d %d %d / %d %d %d\n", m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
			check("m00 == 0x5000", m[0], 0x5000);
#if CTR_GTE_BIG_ENDIAN
			check("m11 == 0 (pre-fix 360 symptom)", m[4], 0);
			check("m22 == 0 (pre-fix 360 symptom)", m[8], 0);
#else
			check("m11 == 0x5000", m[4], 0x5000);
			check("m22 == 0x5000", m[8], 0x5000);
#endif
			check("off-diagonals zero", m[1] + m[2] + m[3] + m[5] + m[6] + m[7], 0L);
		}
		(void)unp;
	}

	printf("== build_m3x3: inst diag(0x5000) x mh.scale(0x1810,0x1000,0x1000) ==\n");
	{
		MATRIX inst;
		SVec3 scale;
		u32 tuple[5];
		int m[9];
		make_diag(&inst, 0x5000, 0x5000, 0x5000);
		scale.x = 0x1810; scale.y = 0x1000; scale.z = 0x1000;
		build_m3x3(&inst, &scale, 0x100, tuple);
		dump5("m3x3 tuple:", tuple);
		unpack_tuple(tuple, m);
		printf("  unpacked: %d %d %d / %d %d %d / %d %d %d\n", m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
		check("m00 == 5*0x1810", m[0], 5 * 0x1810);
#if CTR_GTE_BIG_ENDIAN
		check("m11 == 0 (pre-fix 360 symptom)", m[4], 0);
		check("m22 == 0 (pre-fix 360 symptom)", m[8], 0);
#else
		check("m11 == 5*0x1000", m[4], 5 * 0x1000);
		check("m22 == 5*0x1000", m[8], 5 * 0x1000);
#endif
	}

	printf("== build_m3x3: inst diag(0x5000) x cooked introcrash scale ==\n");
	printf("   (cooked bytes x=10 18 y=0b 3b z=06 c9 -> LE reads 0x1810 0x3b0b 0xc906)\n");
	{
		MATRIX inst;
		SVec3 scale;
		u32 tuple[5];
		int m[9];
		make_diag(&inst, 0x5000, 0x5000, 0x5000);
		scale.x = (s16)0x1810; scale.y = (s16)0x3b0b; scale.z = (s16)0xc906;
		build_m3x3(&inst, &scale, 0x100, tuple);
		dump5("m3x3 tuple:", tuple);
		unpack_tuple(tuple, m);
		printf("  unpacked: %d %d %d / %d %d %d / %d %d %d\n", m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
	}
	printf("== build_m3x3: inst diag(0x5000) x TRUE introcrash scale ==\n");
	printf("   (retail LE bytes 18 10 3b 0b c9 06 -> 0x1018 0x0b3b 0x06c9)\n");
	{
		MATRIX inst;
		SVec3 scale;
		u32 tuple[5];
		int m[9];
		make_diag(&inst, 0x5000, 0x5000, 0x5000);
		scale.x = (s16)0x1018; scale.y = (s16)0x0b3b; scale.z = (s16)0x06c9;
		build_m3x3(&inst, &scale, 0x100, tuple);
		dump5("m3x3 tuple:", tuple);
		unpack_tuple(tuple, m);
		printf("  unpacked: %d %d %d / %d %d %d / %d %d %d\n", m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
		/* session-6 regression: the m3x3 must be a full diagonal. The
		 * 360 used to lose the y/z columns because PAIR.sw.l/.sw.h read
		 * the wrong halfword of the CTC2-loaded matrix and the MTC2-packed
		 * vector; CTR_GTE_BIG_ENDIAN=1 on this little-endian host emulates
		 * exactly that pre-fix layout, so the symptom is asserted there. */
		check("m00 == 0x5078 (5*0x1018)", m[0], 0x5078);
#if CTR_GTE_BIG_ENDIAN
		check("m11 == 0 (pre-fix 360 symptom)", m[4], 0);
		check("m22 == 0 (pre-fix 360 symptom)", m[8], 0);
#else
		check("m11 == 0x3827 (5*0x0b3b)", m[4], 0x3827);
		check("m22 == 0x21ed (5*0x06c9)", m[8], 0x21ed);
		check("y/z columns nonzero", (m[4] != 0 && m[8] != 0), 1L);
#endif
	}

	printf("== build_mvp: title-instance m3x3 x known viewProj ==\n");
	{
		static const int v9[9] = {0x1000, 0x0800, 0x0400,
		                          0x0200, 0x1000, 0x0200,
		                          0x0100, 0x0100, 0x1000};
		/* mvp[i][j] = (viewProj[i][j] * m3x3[j][j]) >> 12 */
		static const int want[9] = {0x5078, 0x1c13, 0x087b,
		                            0x0a0f, 0x3827, 0x043d,
		                            0x0507, 0x0382, 0x21ed};
		MATRIX m3x3, vp, mvp;
		u32 tuple[5];
		u32 w[5];
		int m[9];
		int i, ok = 1;
		w[0] = 0x00005078; w[1] = 0; w[2] = 0x00003827; w[3] = 0; w[4] = 0x000021ed;
		store_matrix_words(&m3x3, w);
		make_matrix(&vp, v9);
		build_mvp(&m3x3, &vp, &mvp, tuple);
		dump5("mvp tuple:", tuple);
		unpack_tuple(tuple, m);
		printf("  got:      %d %d %d / %d %d %d / %d %d %d\n", m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
		printf("  expected: %d %d %d / %d %d %d / %d %d %d\n", want[0], want[1], want[2], want[3], want[4], want[5], want[6], want[7], want[8]);
		for (i = 0; i < 9; i++)
		{
			if (m[i] != want[i])
			{
				ok = 0;
			}
		}
#if CTR_GTE_BIG_ENDIAN
		/* pre-fix 360 layout: x columns survive, y/z are zeroed by the
		 * halfword mix-up (m[4] picks up a cross term instead of 0x3827) */
		check("mvp[0][0] == 0x5078", m[0], 0x5078);
		check("mvp[0][1] == 0x1c13", m[1], 0x1c13);
		check("mvp[1][1] != 0x3827 (pre-fix symptom)", (m[4] != 0x3827), 1L);
		check("mvp[2][2] == 0 (pre-fix symptom)", m[8], 0L);
#else
		check("mvp == viewProj x diag(m3x3)", ok, 1L);
		check("mvp[1][1] == 0x3827", m[4], 0x3827);
		check("mvp[2][2] == 0x21ed", m[8], 0x21ed);
#endif
	}

	printf("== build_mvp: (diag 0x5000) x identity viewProj ==\n");
	{
		MATRIX m3x3, vp, mvp;
		u32 tuple[5];
		int m[9];
		make_diag(&m3x3, 0x5000, 0x5000, 0x5000);
		make_diag(&vp, 0x1000, 0x1000, 0x1000);
		build_mvp(&m3x3, &vp, &mvp, tuple);
		dump5("mvp tuple:", tuple);
		unpack_tuple(tuple, m);
		printf("  unpacked: %d %d %d / %d %d %d / %d %d %d\n", m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
		/* ref: L x M with L = viewProj, M = m3x3 (see BuildMvp note in the port) */
#if CTR_GTE_BIG_ENDIAN
		check("mvp diag == 0x5000 (pre-fix symptom: y/z zeroed)", (m[0] == 0x5000 && m[4] == 0 && m[8] == 0), 1L);
#else
		check("mvp diag == 0x5000", (m[0] == 0x5000 && m[4] == 0x5000 && m[8] == 0x5000), 1L);
#endif
	}

	printf("== build_mvp semantics: diag(2,3,4) x known V ==\n");
	{
		static const int m3[9] = {0x2000, 0, 0, 0, 0x3000, 0, 0, 0, 0x4000};
		static const int v9[9] = {0x0100, 0x0200, 0x0300, 0x0400, 0x0500, 0x0600, 0x0700, 0x0800, 0x0900};
		int want_mv[9], want_vm[9], got[9];
		MATRIX M, V, MVP;
		u32 tuple[5];
		int i, mv_ok = 1, vm_ok = 1, exact;
		make_matrix(&M, m3);
		make_matrix(&V, v9);
		build_mvp(&M, &V, &MVP, tuple);
		unpack_tuple(tuple, got);
		/* A x V scales rows of V by (2,3,4); V x A scales columns; both exact
		 * for these values ((0x2000*v)>>12 == 2*v). */
		for (i = 0; i < 9; i++)
		{
			want_mv[i] = v9[i] * (i / 3 == 0 ? 2 : (i / 3 == 1 ? 3 : 4));
			want_vm[i] = v9[i] * (i % 3 == 0 ? 2 : (i % 3 == 1 ? 3 : 4));
			if (got[i] != want_mv[i]) mv_ok = 0;
			if (got[i] != want_vm[i]) vm_ok = 0;
		}
		printf("  got:      %d %d %d / %d %d %d / %d %d %d\n", got[0], got[1], got[2], got[3], got[4], got[5], got[6], got[7], got[8]);
		printf("  rows(2,3,4) scaled (M x V): %d %d %d / %d %d %d / %d %d %d\n", want_mv[0], want_mv[1], want_mv[2], want_mv[3], want_mv[4], want_mv[5], want_mv[6], want_mv[7], want_mv[8]);
		printf("  cols(2,3,4) scaled (V x M): %d %d %d / %d %d %d / %d %d %d\n", want_vm[0], want_vm[1], want_vm[2], want_vm[3], want_vm[4], want_vm[5], want_vm[6], want_vm[7], want_vm[8]);
		exact = mv_ok || vm_ok;
		printf("  result is %s\n", mv_ok ? "M x V (m3x3 x viewProj rows)" : (vm_ok ? "V x M (viewProj x m3x3)" : "NEITHER - helper packing is wrong"));
#if CTR_GTE_BIG_ENDIAN
		check("pre-fix symptom: neither clean scaling", exact, 0L);
#else
		check("mvp equals a clean row/col scaling", exact, 1L);
#endif
	}

	printf("== byteswapped inputs (what the 360 saw before the fixes) ==\n");
	{
		MATRIX inst;
		SVec3 scale;
		u32 tuple[5];
		int m[9];
		make_diag(&inst, 0x5000, 0x5000, 0x5000);
		/* simulate the old host-order write: bytes [50 00] instead of [00 50] */
		CTR_WriteU16LE(&inst.m[0][0], (u16)bswap32((u32)(u16)0x5000) >> 16);
		CTR_WriteU16LE(&inst.m[1][1], (u16)bswap32((u32)(u16)0x5000) >> 16);
		CTR_WriteU16LE(&inst.m[2][2], (u16)bswap32((u32)(u16)0x5000) >> 16);
		scale.x = 0x1000; scale.y = 0x1000; scale.z = 0x1000;
		build_m3x3(&inst, &scale, 0x100, tuple);
		dump5("swapped m3x3:", tuple);
		unpack_tuple(tuple, m);
		printf("  unpacked: %d %d %d / %d %d %d / %d %d %d\n", m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
	}

	printf("\n%s (%d failure(s))\n", failures ? "UNIT TEST FAILED" : "UNIT TEST PASSED", failures);
	return failures ? 1 : 0;
}
