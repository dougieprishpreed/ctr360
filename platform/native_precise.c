#include <platform/native_precise.h>

#include <macros.h>

#include <string.h>

/*
 * The GTE keeps only the integer part of each projected X/Y, truncating by up
 * to a whole PSX pixel. Where a model vertex should lie on a neighbouring
 * triangle's edge, that leaves a sliver covering no pixel centre at 320x240
 * but several at 1280x720, so the background shows through the model as small
 * flecks. The GTE core keeps each SXY FIFO entry's exact projection; stores of
 * it into this frame's primitive memory are recorded here, and the GPU parser
 * adds the offset back. A field keeps its integer position when its value has
 * changed, when it was written before the previous frame, or when recording
 * was suspended or unavailable while it was stored.
 */

int g_nativePreciseVertices = 0;

typedef struct
{
	uint32_t sxy;
	int16_t dx, dy;
	uint8_t valid;
} NativePreciseSlot;

typedef struct
{
	int16_t x, y;
	uint16_t generation;
	int16_t dx, dy;
} NativePreciseEntry;

global_variable NativePreciseSlot s_nativePreciseFifo[3];
global_variable NativePreciseEntry s_nativePreciseTable[2][NATIVE_PRECISE_REGION_BYTES / 4];
global_variable uintptr_t s_nativePreciseStart[2];
global_variable uint32_t s_nativePreciseBytes[2];
// Generation 0 marks a never-written entry; it is skipped on wrap.
global_variable uint16_t s_nativePreciseGeneration = 1;
global_variable int s_nativePreciseSuspended;

void NativePrecise_PushProjection(uint32_t sxy, int valid, int dx, int dy)
{
	s_nativePreciseFifo[0] = s_nativePreciseFifo[1];
	s_nativePreciseFifo[1] = s_nativePreciseFifo[2];
	s_nativePreciseFifo[2].sxy = sxy;
	s_nativePreciseFifo[2].dx = (int16_t)dx;
	s_nativePreciseFifo[2].dy = (int16_t)dy;
	s_nativePreciseFifo[2].valid = (uint8_t)(valid != 0);
}

static NativePreciseSlot NativePrecise_SlotFor(uint32_t sxy)
{
	// A register written from another FIFO entry (the RTPS strip reuse copy)
	// keeps that entry's projection; any other value has none.
	for (int i = 0; i < 3; i++)
	{
		if (s_nativePreciseFifo[i].valid && s_nativePreciseFifo[i].sxy == sxy)
		{
			return s_nativePreciseFifo[i];
		}
	}

	NativePreciseSlot none = {sxy, 0, 0, 0};
	return none;
}

void NativePrecise_OnRegisterWrite(int slot, uint32_t sxy)
{
	if (slot >= 0 && slot < 3)
	{
		s_nativePreciseFifo[slot] = NativePrecise_SlotFor(sxy);
	}
}

void NativePrecise_OnRegisterPush(uint32_t sxy)
{
	NativePreciseSlot pushed = NativePrecise_SlotFor(sxy);
	NativePrecise_PushProjection(sxy, pushed.valid, pushed.dx, pushed.dy);
}

void NativePrecise_SetRegion(int index, const void *start, uint32_t bytes)
{
	if (index < 0 || index > 1)
	{
		return;
	}

	s_nativePreciseStart[index] = (uintptr_t)start;
	s_nativePreciseBytes[index] = bytes < NATIVE_PRECISE_REGION_BYTES ? bytes : NATIVE_PRECISE_REGION_BYTES;
}

void NativePrecise_NewFrame(void)
{
	if (++s_nativePreciseGeneration == 0)
	{
		memset(s_nativePreciseTable, 0, sizeof(s_nativePreciseTable));
		s_nativePreciseGeneration = 1;
	}
	s_nativePreciseSuspended = 0;
}

void NativePrecise_Suspend(int suspended)
{
	s_nativePreciseSuspended = suspended != 0;
}

static NativePreciseEntry *NativePrecise_Entry(const void *xy)
{
	uintptr_t address = (uintptr_t)xy;

	for (int i = 0; i < 2; i++)
	{
		uintptr_t offset = address - s_nativePreciseStart[i];
		if (s_nativePreciseStart[i] != 0 && address >= s_nativePreciseStart[i] && offset < s_nativePreciseBytes[i] && (offset & 3) == 0)
		{
			return &s_nativePreciseTable[i][offset >> 2];
		}
	}

	return NULL;
}

void NativePrecise_StoreSXY(const void *xy, int slot)
{
	NativePreciseEntry *entry = NativePrecise_Entry(xy);
	if (entry == NULL || slot < 0 || slot > 2)
	{
		return;
	}

	const int16_t *field = (const int16_t *)xy;
	NativePreciseSlot source = s_nativePreciseFifo[slot];
	uint32_t stored = (uint16_t)field[0] | ((uint32_t)(uint16_t)field[1] << 16);
	if (!g_nativePreciseVertices || s_nativePreciseSuspended || !source.valid || source.sxy != stored)
	{
		// Overwrite rather than skip, so an older frame's offset cannot apply.
		entry->generation = 0;
		return;
	}

	entry->x = field[0];
	entry->y = field[1];
	entry->dx = source.dx;
	entry->dy = source.dy;
	entry->generation = s_nativePreciseGeneration;
}

int NativePrecise_Lookup(const void *xy, int16_t *dx, int16_t *dy)
{
	NativePreciseEntry *entry = g_nativePreciseVertices ? NativePrecise_Entry(xy) : NULL;
	const int16_t *field = (const int16_t *)xy;

	*dx = 0;
	*dy = 0;
	// Packets are parsed in the frame that wrote them or the next one.
	if (entry == NULL || entry->generation == 0 || (uint16_t)(s_nativePreciseGeneration - entry->generation) > 1 || entry->x != field[0] ||
	    entry->y != field[1])
	{
		return 0;
	}

	*dx = entry->dx;
	*dy = entry->dy;
	return 1;
}
