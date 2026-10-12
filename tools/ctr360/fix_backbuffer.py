"""ctr360 renderer fix: GL's 'bind framebuffer 0' means the window/backbuffer.
On the 360, SetRenderTarget(0, NULL) binds NOTHING, so every present/bars pass
went nowhere. Cache the swap-chain back buffer and bind it instead; also switch
rect-limited clears from scissor+full-clear to an explicit D3DRECT."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
NL = chr(13) + chr(10)
s = io.open(P, encoding='utf-8', newline='').read()

def sub(old, new, label):
    n = s.count(old)
    print('%-46s matches=%d' % (label, n))
    assert n == 1, (label, n)
    return s.replace(old, new)

# 1. globals for the swap chain surfaces
s = sub("global_variable int s_shaderCompileFailures;",
        "global_variable int s_shaderCompileFailures;" + NL +
        "global_variable D3DSurface *s_backBuffer;          /* swap chain back buffer (GL's framebuffer 0) */" + NL +
        "global_variable D3DSurface *s_backBufferDepth;",
        "globals: back buffer surfaces")

# 2. fetch them right after device creation
s = sub("\tPlatform_Log(\"[CTR Renderer] D3D9 device up: %dx%d backbuffer\\n\", g_windowWidth, g_windowHeight);",
        "\tPlatform_Log(\"[CTR Renderer] D3D9 device up: %dx%d backbuffer\\n\", g_windowWidth, g_windowHeight);" + NL + NL +
        "\t/* The 360 has no PC-style swap chain object: the back buffer surface is" + NL +
        "\t * fetched from the device and is what GL called framebuffer 0. */" + NL +
        "\tif (FAILED(IDirect3DDevice9_GetBackBuffer(s_device, 0, 0, 0, &s_backBuffer)))" + NL +
        "\t{" + NL +
        "\t\ts_backBuffer = NULL;" + NL +
        "\t\tNATIVE_RENDERER_ERROR(\"%s\\n\", \"GetBackBuffer failed\");" + NL +
        "\t}" + NL +
        "\tif (FAILED(IDirect3DDevice9_GetDepthStencilSurface(s_device, &s_backBufferDepth)))" + NL +
        "\t{" + NL +
        "\t\ts_backBufferDepth = NULL;" + NL +
        "\t}" + NL +
        "\tPlatform_Log(\"[CTR Renderer] back buffer surface: %s\\n\", (s_backBuffer != NULL) ? \"ok\" : \"missing\");",
        "fetch back buffer after CreateDevice")

# 3. SetRenderTarget(NULL) -> bind the back buffer (GL parity)
s = sub("\tif (target == NULL)" + NL +
        "\t{" + NL +
        "\t\tif (s_boundTarget != &s_nullTarget)" + NL +
        "\t\t{" + NL +
        "\t\t\tIDirect3DDevice9_SetRenderTarget(s_device, 0, NULL);" + NL +
        "\t\t\tIDirect3DDevice9_SetDepthStencilSurface(s_device, NULL);" + NL +
        "\t\t\ts_boundTarget = &s_nullTarget;" + NL +
        "\t\t\ts_lastBoundTexture = (TextureID)-1;" + NL +
        "\t\t}" + NL +
        "\t\treturn;" + NL +
        "\t}",
        "\tif (target == NULL)" + NL +
        "\t{" + NL +
        "\t\t/* GL framebuffer 0: the window, which on 360 is the swap chain's back" + NL +
        "\t\t * buffer. Binding NULL here would bind no target at all. */" + NL +
        "\t\tif (s_boundTarget != &s_nullTarget)" + NL +
        "\t\t{" + NL +
        "\t\t\tIDirect3DDevice9_SetRenderTarget(s_device, 0, s_backBuffer);" + NL +
        "\t\t\tIDirect3DDevice9_SetDepthStencilSurface(s_device, s_backBufferDepth);" + NL +
        "\t\t\ts_boundTarget = &s_nullTarget;" + NL +
        "\t\t\ts_lastBoundTexture = (TextureID)-1;" + NL +
        "\t\t}" + NL +
        "\t\treturn;" + NL +
        "\t}",
        "SetRenderTarget(NULL) -> back buffer")

# 4. present pass binds the back buffer through the same path
s = sub("\tIDirect3DDevice9_SetRenderTarget(s_device, 0, NULL);" + NL +
        "\tIDirect3DDevice9_SetDepthStencilSurface(s_device, NULL);" + NL +
        "\ts_boundTarget = NULL;" + NL,
        "\tNativeRenderer_SetRenderTarget(NULL);" + NL,
        "present pass binds back buffer")

# 5. rect-limited clear: explicit D3DRECT instead of scissor + full clear
s = sub("""internal void NativeRenderer_ClearHostRect(int x, int y, int width, int height)
{
	RECT rect;

	if ((width <= 0) || (height <= 0) || (s_device == NULL))
	{
		return;
	}

	rect.left = (LONG)x;
	rect.right = (LONG)(x + width);
	rect.top = (LONG)(g_windowHeight - y - height);
	rect.bottom = (LONG)(g_windowHeight - y);

	IDirect3DDevice9_SetScissorRect(s_device, &rect);
	IDirect3DDevice9_Clear(s_device, 0, NULL, D3DCLEAR_TARGET, 0xFF000000, 1.0f, 0);
}""".replace(chr(10), NL),
        """internal void NativeRenderer_ClearHostRect(int x, int y, int width, int height)
{
	D3DRECT rect;
	const int top = g_windowHeight - y - height;

	if ((width <= 0) || (height <= 0) || (s_device == NULL))
	{
		return;
	}

	/* D3DRECT is x1/y1/x2/y2 on this platform; a rect-limited clear keeps the
	 * presentation bars from depending on scissor behaviour. */
	rect.x1 = (LONG)x;
	rect.y1 = (LONG)top;
	rect.x2 = (LONG)(x + width);
	rect.y2 = (LONG)(top + height);

	IDirect3DDevice9_Clear(s_device, 1, &rect, D3DCLEAR_TARGET, 0xFF000000, 1.0f, 0);
}""".replace(chr(10), NL),
        "ClearHostRect uses D3DRECT")

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('back buffer fixes written')
