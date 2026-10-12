"""ctr360: make the PSX clear rect-limited (D3DRECT) instead of relying on the
scissor test, which the 360's Clear does not necessarily honour. Rows are
already in the shared convention, so no flip is needed."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
NL = chr(13) + chr(10)
s = io.open(P, encoding='utf-8', newline='').read()

old = """	{
		const int relX = overlapX - displayX;
		const int relBottom = overlapBottom - displayY;
		const int scissorX = relX;
		const int scissorY = displayH - relBottom;
		const int scissorW = overlapRight - overlapX;
		const int scissorH = overlapBottom - overlapY;

		if ((scissorW <= 0) || (scissorH <= 0))
		{
			return;
		}

		rect.left = scissorX;
		rect.top = scissorY;
		rect.right = scissorX + scissorW;
		rect.bottom = scissorY + scissorH;
	}

	/* GL scissor y comes from the bottom, D3D's from the top; for render
	 * targets both address the same rows, so the GL-computed rect carries. */
	color = D3DCOLOR_ARGB(0, NativeRenderer_PSXColorComponent(r), NativeRenderer_PSXColorComponent(g), NativeRenderer_PSXColorComponent(b));

	IDirect3DDevice9_SetScissorRect(s_device, &rect);
	IDirect3DDevice9_Clear(s_device, 0, NULL, D3DCLEAR_TARGET, color, 1.0f, 0);""".replace(chr(10), NL)

new = """	{
		const int relX = overlapX - displayX;
		const int relBottom = overlapBottom - displayY;
		const int clearX = relX;
		const int clearY = displayH - relBottom;
		const int clearW = overlapRight - overlapX;
		const int clearH = overlapBottom - overlapY;

		if ((clearW <= 0) || (clearH <= 0))
		{
			return;
		}

		/* GL scissor y comes from the bottom, D3D's from the top; for render
		 * targets both address the same rows, so the GL-computed rows carry. */
		rect.x1 = (LONG)clearX;
		rect.y1 = (LONG)clearY;
		rect.x2 = (LONG)(clearX + clearW);
		rect.y2 = (LONG)(clearY + clearH);
	}

	color = D3DCOLOR_ARGB(0, NativeRenderer_PSXColorComponent(r), NativeRenderer_PSXColorComponent(g), NativeRenderer_PSXColorComponent(b));

	IDirect3DDevice9_Clear(s_device, 1, &rect, D3DCLEAR_TARGET, color, 1.0f, 0);""".replace(chr(10), NL)

n = s.count(old)
print('PSX clear block matches:', n)
assert n == 1, n
s = s.replace(old, new)

# RECT rect; -> D3DRECT rect; in this function only
old2 = """void NativeRenderer_Clear(int x, int y, int w, int h, u8 r, u8 g, u8 b)
{
	int displayX, displayY, displayW, displayH;
	int clearRight, clearBottom, displayRight, displayBottom;
	int overlapX, overlapY, overlapRight, overlapBottom;
	RECT rect;
	D3DCOLOR color;""".replace(chr(10), NL)
new2 = """void NativeRenderer_Clear(int x, int y, int w, int h, u8 r, u8 g, u8 b)
{
	int displayX, displayY, displayW, displayH;
	int clearRight, clearBottom, displayRight, displayBottom;
	int overlapX, overlapY, overlapRight, overlapBottom;
	D3DRECT rect;
	D3DCOLOR color;""".replace(chr(10), NL)
n2 = s.count(old2)
print('PSX clear signature matches:', n2)
assert n2 == 1, n2
s = s.replace(old2, new2)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('PSX clear is now rect-limited')
