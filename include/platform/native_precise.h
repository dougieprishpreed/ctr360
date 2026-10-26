#ifndef NATIVE_PRECISE_H
#define NATIVE_PRECISE_H

#include <stdint.h>

// Offsets of GTE-projected vertices from their integer position, in 1/256
// PSX pixel. Vertices carry the fraction left after whole pixels move into
// the coordinate, within half a pixel, in their spare bytes.
#define NATIVE_PRECISE_UNITS 256
// Primitive memory covered per double buffer (retail needs at most 225 KB).
#define NATIVE_PRECISE_REGION_BYTES (512u * 1024u)

extern int g_nativePreciseVertices;

// The GTE core calls these as its SXY FIFO changes.
void NativePrecise_PushProjection(uint32_t sxy, int valid, int dx, int dy);
void NativePrecise_OnRegisterWrite(int slot, uint32_t sxy);
void NativePrecise_OnRegisterPush(uint32_t sxy);

// Primitive memory of the two draw buffers; reset once per game frame.
void NativePrecise_SetRegion(int index, const void *start, uint32_t bytes);
void NativePrecise_NewFrame(void);
// Instances whose writers copy positions through scratch stay integral.
void NativePrecise_Suspend(int suspended);

// Called after an integer SXY store of FIFO slot 0..2 into `xy`.
void NativePrecise_StoreSXY(const void *xy, int slot);
// Sub-pixel offset of a parsed packet coordinate; 0 when it has none.
int NativePrecise_Lookup(const void *xy, int16_t *dx, int16_t *dy);

#endif
