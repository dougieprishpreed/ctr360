#include <common.h>

MATRIX *MATH_HitboxMatrix(MATRIX *output, MATRIX *input)
{
	u32 *in = (u32 *)input;
	u32 *out = (u32 *)output;

	u32 word0 = CTR_ReadU32LE(&in[0]);
	u32 word1 = CTR_ReadU32LE(&in[1]);
	u32 word2 = CTR_ReadU32LE(&in[2]);
	u32 word3 = CTR_ReadU32LE(&in[3]);
	u32 r11r12 = (word0 & 0xffff) | (word1 & 0xffff0000);
	u32 r13r21 = (word3 & 0xffff) | (word0 & 0xffff0000);
	u32 r22r23 = (word2 & 0xffff) | (word3 & 0xffff0000);
	u32 r31r32 = (word1 & 0xffff) | (word2 & 0xffff0000);
	s16 r33 = (s16)CTR_ReadU16LE(&in[4]);

	CTC2(r11r12, 0);
	CTC2(r13r21, 1);
	CTC2(r22r23, 2);
	CTC2(r31r32, 3);
	CTC2((s32)r33, 4);

	MTC2(((0u - (u32)input->t[0]) & 0xffff) | ((0u - (u32)input->t[1]) << 16), 0);
	MTC2(0u - (u32)input->t[2], 1);
	gte_rtv0();

	CTR_WriteU32LE(&out[0], r11r12);
	CTR_WriteU32LE(&out[1], r13r21);
	CTR_WriteU32LE(&out[2], r22r23);
	CTR_WriteU32LE(&out[3], r31r32);
	CTR_WriteU16LE(&out[4], (u16)r33);
	CTR_GteStoreMAC(output->t);

	return output;
}
