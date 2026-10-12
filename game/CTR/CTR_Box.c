#include <common.h>

static inline void CTR_Box_SetLength(Tag *tag, u32 size)
{
	#ifdef CTR_NATIVE
	// PSX tag bitfields allocate from the low bit; Xenon allocates from the
	// high bit. AddPrimitive preserves the numeric high-byte packet length.
	tag->self = size << 24;
#else
	tag->bits.size = size;
#endif
}

void CTR_Box_DrawWirePrims(s16 x1, s16 y1, s16 x2, s16 y2, s32 r, s32 g, s32 b, u32 *ot, struct PrimMem *primMem)
{
	LineF2 *p = primMem->cursor;
	const PrimCode primCode = {.kind.line = {.renderCode = RenderCode_Line}};
	if (p == NULL || p > (LineF2 *)primMem->guardEnd)
	{
		return;
	}
	primMem->cursor = p + 1;

	CTR_Box_SetLength(&p->tag, (sizeof(*p) - sizeof(p->tag)) / sizeof(u32));
	p->colorCode = MakeColor(r, g, b);
#ifdef CTR_NATIVE
	p->colorCode.code.code = 0x40;
#else
	p->colorCode.code = primCode;
#endif
	p->v[0].pos = MakePoint(x1, y1);
	p->v[1].pos = MakePoint(x2, y2);

	AddPrimitive(p, ot);
}

void CTR_Box_DrawWireBox(RECT *r, const Color *color, void *ot, struct PrimMem *primMem)
{
	LineF3 *p = primMem->cursor;
	if (p > (LineF3 *)primMem->guardEnd)
	{
		return;
	}
	primMem->cursor = p + 1;

	const PrimCode primCode = {.kind.line = {.renderCode = RenderCode_Line, .polyline = 1}};
	CTR_Box_SetLength(&p->tag, (sizeof(*p) - sizeof(p->tag)) / sizeof(u32));
	p->colorCode = *color;
#ifdef CTR_NATIVE
	p->colorCode.code.code = 0x48;
#else
	p->colorCode.code = primCode;
#endif

	s16 topX = r->x;
	s16 topY = r->y;
	s16 bottomX = r->x + r->w;
	s16 bottomY = r->y + r->h;
	p->v[0].pos.x = topX;
	p->v[0].pos.y = topY;
	p->v[1].pos.x = bottomX;
	p->v[1].pos.y = topY;
	p->v[2].pos.x = bottomX;
	p->v[2].pos.y = bottomY;
	p->end = 0x55555555;

	AddPrimitive(p, ot);
	p = primMem->cursor;
	if (p > (LineF3 *)primMem->guardEnd)
	{
		return;
	}
	primMem->cursor = p + 1;

	CTR_Box_SetLength(&p->tag, (sizeof(*p) - sizeof(p->tag)) / sizeof(u32));
	p->colorCode = *color;
#ifdef CTR_NATIVE
	p->colorCode.code.code = 0x48;
#else
	p->colorCode.code = primCode;
#endif
	p->v[0].pos.x = topX;
	p->v[0].pos.y = topY;
	p->v[1].pos.x = topX;
	p->v[1].pos.y = bottomY;
	p->v[2].pos.x = bottomX;
	p->v[2].pos.y = bottomY;
	p->end = 0x55555555;

	AddPrimitive(p, ot);
}

void CTR_Box_DrawClearBox(const RECT *r, const Color *color, s32 transparency, u32 *ot, struct PrimMem *primMem)
{
	typedef struct TPage_PolyF4
	{
		TPage t;
		PolyF4 p;
	} TPage_PolyF4;

	TPage_PolyF4 *p = primMem->cursor;
	if (p > (TPage_PolyF4 *)primMem->guardEnd)
	{
		return;
	}
	primMem->cursor = p + 1;
	CTR_Box_SetLength(&p->t.tag, (sizeof(*p) - sizeof(p->t.tag)) / sizeof(u32));

#ifdef CTR_NATIVE
	// Control commands are LE byte images; primitive XY fields are native
	// halfwords. Keep the command independent of Texpage's host bitfields.
	CtrGpu_WriteControlWord(&p->t.texpage.self, 0xe1000e00u | ((transparency & 3) << 5));
#else
	p->t.texpage.self = 0xe1000a00u | ((transparency & 3) << 5);
#endif
	p->p.tag.self = 0;

	const PrimCode primCode = {.kind.poly = {.renderCode = RenderCode_Polygon, .quad = 1, .semiTransparency = 1}};
	Color primColor = *color;
#ifdef CTR_NATIVE
	primColor.code.code = 0x2a;
#else
	primColor.code = primCode;
#endif
	p->p.colorCode = primColor;

	s16 topX = r->x;
	s16 topY = r->y;
	s16 bottomX = r->x + r->w;
	s16 bottomY = r->y + r->h;
	p->p.v[0].pos.x = topX;
	p->p.v[0].pos.y = topY;
	p->p.v[1].pos.x = bottomX;
	p->p.v[1].pos.y = topY;
	p->p.v[2].pos.x = topX;
	p->p.v[2].pos.y = bottomY;
	p->p.v[3].pos.x = bottomX;
	p->p.v[3].pos.y = bottomY;

	AddPrimitive(p, ot);
}

void CTR_Box_DrawSolidBox(RECT *r, const Color *color, u32 *ot, struct PrimMem *primMem)
{
	PolyF4 *p = primMem->cursor;
	if (p > (PolyF4 *)primMem->guardEnd)
	{
		return;
	}
	primMem->cursor = p + 1;
	CTR_Box_SetLength(&p->tag, (sizeof(*p) - sizeof(p->tag)) / sizeof(u32));

	const PrimCode primCode = {.kind.poly = {.renderCode = RenderCode_Polygon, .quad = 1}};
	p->colorCode = *color;
#ifdef CTR_NATIVE
	p->colorCode.code.code = 0x28;
#else
	p->colorCode.code = primCode;
#endif

	s16 topX = r->x;
	s16 topY = r->y;
	s16 bottomX = r->x + r->w;
	s16 bottomY = r->y + r->h;
	p->v[0].pos.x = topX;
	p->v[0].pos.y = topY;
	p->v[1].pos.x = bottomX;
	p->v[1].pos.y = topY;
	p->v[2].pos.x = topX;
	p->v[2].pos.y = bottomY;
	p->v[3].pos.x = bottomX;
	p->v[3].pos.y = bottomY;

	AddPrimitive(p, ot);
}
