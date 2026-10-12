/* ctr360: Xbox 360 D3D9 renderer.
 *
 * Mirrors platform/native_renderer.c (the OpenGL backend) function for
 * function, same state machine, same call contract, so the game code above it
 * is untouched. The translation rules that matter:
 *
 * - VRAM is a persistent 1024x512 linear A8R8G8B8 texture with the low PSX
 *   byte in R and high byte in G. The CPU mirror remains 16-bit; uploads and
 *   readbacks convert those two channels. Shaders still sample RG bytes.
 * - PSX draws render into an offscreen RGBA render target like GL, then get
 *   packed into the VRAM texture with the pack shader.
 * - GL NDC has y=+1 at the top of a texture-attached framebuffer while D3D9
 *   render targets have y=0 as the first row, so all texture-destination
 *   passes flip y in the vertex shader / ortho matrix. This keeps the VRAM
 *   data rows identical to the GL backend, which is the property the game
 *   depends on (shaders address VRAM by PSX coordinates).
 * - The final present pass does NOT flip: the D3D9 backbuffer row 0 is the
 *   visual top row, matching the present shader's "source rect top row ends
 *   up at the top" contract, with the viewport y converted from GL
 *   (bottom-left) to D3D9 (top-left) coordinates.
 * - GPU pack draws use EDRAM, then Resolve into the VRAM texture. CPU readers
 *   lock that resolved texture at the renderer's tracked tile boundaries.
 *
 * XDK notes this file is written against:
 * - The 360 D3D9 API is C: every call goes through the IDirect3DDevice9_* /
 *   IDirect3DTexture9_* inline wrappers, which take the device explicitly (the
 *   bare D3DDevice_* internal forms have no device parameter).
 *   the IDirect3DDevice9_* / IDirect3DTexture9_* inline wrappers, release with
 *   the per-type _Release wrappers.
 * - No texture stage states and no fixed-function lighting exist on Xenos;
 *   everything is shader driven.
 * - The shader compiler rejects `discard` (use clip()) and dynamic integer
 *   math, and integer uniform registers, so flags are float constants and the
 *   pack/present unpacking is float math.
 * - Shader uniforms are bound to explicit registers; there is no constant
 *   table reflection in the C API.
 *
 * C89-clean on purpose: the XDK compiler builds this directly (it lives
 * outside the build-360 mirror, so the mirror transforms do not touch it).
 */

#include <xtl.h>
#include <d3d9.h>
#include <d3dx9.h>

#include <macros.h>
#include <common.h>
#include <string.h>
#include <stdio.h>

#include "platform/native_gpu.h"
#include "platform/native_log.h"
#include "platform/native_renderer.h"

#define NATIVE_RENDERER_LOG(fmt, ...)   Platform_Log("[CTR Renderer] " fmt, __VA_ARGS__)
#define NATIVE_RENDERER_ERROR(fmt, ...) Platform_LogError("[CTR Renderer] [%s] - " fmt, __func__, __VA_ARGS__)

#define MAX_NUM_VERTEX_BUFFERS          (4)
#define PSX_SCREEN_ASPECT               (240.0f / 320.0f)

/* Same tile split as the GL backend - it is what the resolve API wants too. */
#define NATIVE_VRAM_DIRTY_RECT_CAP 128
#define NATIVE_VRAM_TILE_SIZE      8
#define NATIVE_VRAM_TILE_COLS      (VRAM_WIDTH / NATIVE_VRAM_TILE_SIZE)
#define NATIVE_VRAM_TILE_ROWS      (VRAM_HEIGHT / NATIVE_VRAM_TILE_SIZE)
#define NATIVE_VRAM_TILE_COUNT     (NATIVE_VRAM_TILE_COLS * NATIVE_VRAM_TILE_ROWS)
#define NATIVE_VRAM_TILE_WORDS     (NATIVE_VRAM_TILE_COUNT / 32)

/* Shader constant registers (must match the : register() bindings below). */
#define X360_PSX_VS_PROJECTION_C0 0
#define X360_PSX_PS_BILINEAR_C0   0
#define X360_PSX_PS_SEMITRANS_C1  1
#define X360_PSX_PS_MASKSET_C2    2
#define X360_PSX_PS_OUTPUTSTP_C3  3
#define X360_PSX_PS_DITHER_C4     4
#define X360_PSX_PS_TEXELSIZE_C16 16
#define X360_QUAD_VS_FLIP_C16     16
#define X360_PACK_PS_FLIPY_C0     0
#define X360_PRESENT_VS_RECT_C17  17

/* EDRAM contents survive a render-target switch only when the surfaces use
 * distinct ranges. Leave room for the largest PSX display and offscreen page. */
#define X360_MAIN_EDRAM_MAX_W     1280
#define X360_MAIN_EDRAM_MAX_H     720
#define X360_OFFSCREEN_EDRAM_MAX_W 1024
#define X360_OFFSCREEN_EDRAM_MAX_H 512

/* 16 floats per vertex after expansion from the 20-byte packed GrVertex. */
typedef struct X360Vertex
{
	f32 x, y, page, clut;
	f32 u, v, bright, dither;
	f32 r, g, b, a;
	f32 tcx, tcy, p0, p1;
} X360Vertex;

struct X360RenderTarget
{
	D3DTexture *texture;
	D3DSurface *surface;
	D3DSurface *depthStencil;
	s32 width;
	s32 height;
};

struct NativeVramState
{
	D3DTexture *texture;
	D3DSurface *surface;
	u16 cpuPixels[VRAM_WIDTH * VRAM_HEIGHT];
	RECT16 cpuDirtyRects[NATIVE_VRAM_DIRTY_RECT_CAP];
	u32 gpuNewerTiles[NATIVE_VRAM_TILE_WORDS];
	s32 cpuDirtyRectCount;
};

global_variable struct NativeVramState s_vram;
/* XGTileSurface and XGUntileSurface bridge the CPU's row-major PSX VRAM
 * mirror and the tiled texture required by Xbox 360 Resolve. */
global_variable u32 s_vramLinearScratch[X360_MAIN_EDRAM_MAX_W * X360_MAIN_EDRAM_MAX_H];
global_variable struct X360RenderTarget s_mainRenderTarget;
global_variable struct X360RenderTarget s_offscreenRenderTarget;
global_variable struct X360RenderTarget s_nullTarget;


global_variable Direct3D *s_d3d;
global_variable D3DDevice *s_device;
global_variable int s_presentedFrames;
global_variable int s_shaderCompileFailures;
global_variable D3DSurface *s_backBuffer;          /* swap chain back buffer (GL's framebuffer 0) */
global_variable D3DSurface *s_backBufferDepth;
global_variable struct X360RenderTarget *s_boundTarget;

global_variable D3DTexture *s_whiteTexture;
global_variable TextureID s_whiteTextureId = (TextureID)-1;
global_variable TextureID s_lastBoundTexture = (TextureID)-1;
global_variable TexFormat s_debugTextureFormat;

global_variable D3DTexture *s_lutTexture;

global_variable D3DVertexShader *s_gteVertexShader;
global_variable D3DVertexDeclaration *s_gteVertexDecl;
global_variable D3DVertexDeclaration *s_quadVertexDecl;
global_variable struct X360GteShader
{
	D3DPixelShader *shader;
} s_gteShader4, s_gteShader8, s_gteShader16, s_gteShader32Rgba;

global_variable D3DVertexShader *s_packVertexShader;
global_variable D3DPixelShader *s_packPixelShader;
global_variable D3DPixelShader *s_solidDiagnosticPixelShader;
global_variable D3DPixelShader *s_vramCopyPixelShader;
global_variable D3DVertexShader *s_presentVertexShader;
global_variable D3DPixelShader *s_presentPixelShader;
global_variable D3DPixelShader *s_hdPresentPixelShader;
global_variable int s_hdCaptureDiagnostics;
global_variable int s_hdEdgeAA = 1;

global_variable D3DVertexBuffer *s_vertexBuffer[MAX_NUM_VERTEX_BUFFERS];
global_variable s32 s_curVertexBuffer = 0;
global_variable s32 s_boundVertexBuffer = -1;

global_variable BlendMode s_previousBlendMode = BM_NONE;
global_variable int s_previousDepthMode = 0;
global_variable int s_previousStencilMode = 0;
global_variable int s_previousScissorState = 0;
global_variable int s_previousOffscreenState = 0;
global_variable RECT16 s_previousOffscreen = {0, 0, 0, 0};
global_variable ShaderID s_previousShader = (ShaderID)-1;

global_variable int s_swapInterval = 0;

/* Presentation, same math as the GL backend. */
global_variable int s_presentAspectW = 4;
global_variable int s_presentAspectH = 3;
global_variable struct X360Rect
{
	int x, y, w, h;
} s_presentViewport = {0, 0, 0, 0};

int g_windowWidth = 0;
int g_windowHeight = 0;

int g_dbg_wireframeMode = 0;
int g_dbg_texturelessMode = 0;
int g_cfg_bilinearFiltering = 1;
global_variable int s_uiPass;
global_variable int s_mainResolved;

void NativeRenderer_SetUIPass(int enabled)
{
    s_uiPass = enabled != 0;
}

/* Dither offsets are in 8-bit color steps, while the shader uses 0..1 RGB.
 * Flat index is [x][y], matching GLSL's c_dither[dc.x][dc.y]. */
global_variable f32 s_ditherTable[16] = {
	-4.0f / 255.0f, 0.0f, -3.0f / 255.0f, 1.0f / 255.0f,
	2.0f / 255.0f, -2.0f / 255.0f, 3.0f / 255.0f, -1.0f / 255.0f,
	-3.0f / 255.0f, 1.0f / 255.0f, -4.0f / 255.0f, 0.0f,
	3.0f / 255.0f, -1.0f / 255.0f, 2.0f / 255.0f, -2.0f / 255.0f
};

internal void NativeRenderer_SetScissorState(int enable);
internal void NativeRenderer_EnableDepth(int enable);
internal void NativeRenderer_SetViewPort(int x, int y, int width, int height);
internal void NativeRenderer_SetPresentationAspect(int width, int height);
internal void NativeRenderer_UpdatePresentationViewport(void);
internal void NativeRenderer_ClearPresentationBars(void);
internal void NativeRenderer_SetWireframe(int enable);
internal void NativeRenderer_EnsureRenderTarget(struct X360RenderTarget *target, int width, int height);
internal void NativeRenderer_BindMainRenderTarget(void);
internal void NativeRenderer_DrawVRAMRegion(int x, int y, int width, int height);
internal void NativeRenderer_LoadRenderTargetFromVRAM(struct X360RenderTarget *target, int x, int y);
internal void NativeRenderer_Ortho2D(float left, float right, float bottom, float top, float znear, float zfar);
internal void NativeRenderer_SyncGpuVRAMToCPU(int x, int y, int w, int h);
internal void NativeRenderer_ResolveVRAMRead(int x, int y, int w, int h);
internal void NativeRenderer_FlushOffscreenToVRAM(void);
internal void NativeRenderer_GpuPackTextureToVRAM(D3DTexture *sourceTexture, int x, int y, int w, int h, b32 flipY);
internal void NativeRenderer_MarkVRAMDirty(int x, int y, int w, int h);
internal void NativeRenderer_AppendCpuDirtyRect(const RECT16 *rect);
internal s32 NativeRenderer_ClipVRAMRect(RECT16 *out, int x, int y, int w, int h);
internal void NativeRenderer_MarkGpuVRAMNewer(int x, int y, int w, int h);
internal int NativeRenderer_RectEquals16(const RECT16 *a, const RECT16 *b);
internal void NativeRenderer_SetShader(const ShaderID shader);
internal void NativeRenderer_SetRenderTarget(struct X360RenderTarget *target);
internal void NativeRenderer_UploadDitherTable(void);
internal void NativeRenderer_UploadPSXFlags(void);

TextureID NativeRenderer_GetVRAMTexture(void)
{
	return (TextureID)(DWORD_PTR)s_vram.texture;
}

TextureID NativeRenderer_GetWhiteTexture(void)
{
	return s_whiteTextureId;
}

internal D3DTexture *NativeRenderer_TextureFromId(TextureID id)
{
	return (D3DTexture *)(DWORD_PTR)id;
}

internal TextureID NativeRenderer_IdFromTexture(D3DTexture *texture)
{
	return (TextureID)(DWORD_PTR)texture;
}

/* ---------------------------------------------------------------------------------------
 * Shaders: HLSL ports of the GLSL in platform/native_renderer.c.
 * All sources validated with the XDK's fxc (vs_3_0 / ps_3_0).
 * --------------------------------------------------------------------------------------- */

/* Shared PSX pixel-shader prelude (VRAM fetch, CLUT LUT, STP clip, dither). */
global_variable const char *x360_psx_common =
	"sampler2D s_texture : register(s0);\n"
	"sampler2D s_rgLut : register(s1);\n"
	"static const float2 c_VRAMTexel = float2(1.0 / 1024.0, 1.0 / 512.0);\n"
	"static const float2 c_LUTTexel = float2(1.0 / 256.0, 1.0 / 256.0);\n"
	"float bilinearFilter : register(c0);\n"
	"float psxSemiTransPass : register(c1);\n"
	"float psxDrawMaskSet : register(c2);\n"
	"float psxTextureOutputStp : register(c3);\n"
	"row_major float4x4 c_dither : register(c4);\n"
	"struct VS_OUT\n"
	"{\n"
	"	float4 pos : POSITION;\n"
	"	float4 texcoord : TEXCOORD0;\n"
	"	float4 color : COLOR0;\n"
	"	float4 page_clut : TEXCOORD1;\n"
	"	float2 ditherCoord : TEXCOORD2;\n"
	"	float z : TEXCOORD3;\n"
	"};\n"
	"float2 VRAM(float2 uv) { return tex2D(s_texture, uv).rg; }\n"
	"float _idx2(float2 array, int idx) { return (idx == 0) ? array.x : array.y; }\n"
	"float texelVisible(float2 rg) { return (rg.x + rg.y > 0.0) ? 1.0 : 0.0; }\n"
	"float stpWeight(float2 rg) { return (rg.y >= 0.5) ? 1.0 : 0.0; }\n"
	"float semiTransClip(float visible, float stpVisible, float nonStpVisible)\n"
	"{\n"
	"	if (visible < 0.5) { return -1.0; }\n"
	"	if (psxSemiTransPass == 1.0 && nonStpVisible < 0.5) { return -1.0; }\n"
	"	if (psxSemiTransPass == 2.0 && stpVisible < 0.5) { return -1.0; }\n"
	"	return 1.0;\n"
	"}\n"
	"float4 lut(float2 rg) { return tex2D(s_rgLut, rg - c_LUTTexel * 0.0001); }\n"
	"float4 dither(float4 color, float2 ditherCoord, float ditherAmount)\n"
	"{\n"
	"	float2 dc = floor(fmod(floor(ditherCoord), 4.0));\n"
	"	float d = c_dither[(int)dc.x][(int)dc.y];\n"
	"	color.xyz += d * ditherAmount;\n"
	"	return color;\n"
	"}\n";

global_variable const char *x360_psx_sample4 =
	"float2 samplePSX(float2 tc, float4 page_clut)\n"
	"{\n"
	"	float2 uv = (tc * float2(0.25, 1.0) + page_clut.xy) * c_VRAMTexel;\n"
	"	float2 comp = VRAM(uv);\n"
	"	float index = floor(frac(tc.x / 4.0 + 0.0001) * 4.0);\n"
	"	float v = _idx2(comp, (int)floor(index / 2.0)) * (255.0 / 16.0);\n"
	"	float f = floor(v + 0.001);\n"
	"	float2 c = float2((v - f) * 16.0, f);\n"
	"	float2 clut_pos = page_clut.zw;\n"
	"	float fracIndex = index - floor(index / 2.0) * 2.0;\n"
	"	clut_pos.x += lerp(c[0], c[1], fracIndex) * c_VRAMTexel.x;\n"
	"	return VRAM(clut_pos);\n"
	"}\n";

global_variable const char *x360_psx_sample8 =
	"float2 samplePSX(float2 tc, float4 page_clut)\n"
	"{\n"
	"	float2 uv = (tc * float2(0.5, 1.0) + page_clut.xy) * c_VRAMTexel;\n"
	"	float2 comp = VRAM(uv);\n"
	"	float2 clut_pos = page_clut.zw;\n"
	"	float index = tc.x - floor(tc.x / 2.0) * 2.0;\n"
	"	clut_pos.x += _idx2(comp, (int)index) * 255.0 * c_VRAMTexel.x;\n"
	"	return VRAM(clut_pos);\n"
	"}\n";

global_variable const char *x360_psx_sample16 =
	"float2 samplePSX(float2 tc, float4 page_clut)\n"
	"{\n"
	"	float2 uv = (tc + page_clut.xy) * c_VRAMTexel;\n"
	"	return VRAM(uv);\n"
	"}\n";

global_variable const char *x360_psx_main =
	"float4 main(VS_OUT i) : COLOR0\n"
	"{\n"
	"	float sampledStp = 0.0;\n"
	"	float4 color;\n"
	"	if (bilinearFilter > 0.0) {\n"
	"		float2 P = i.texcoord.xy;\n"
	"		float2 fracPart = frac(P);\n"
	"		float2 pixel = floor(P);\n"
	"		float2 C11 = samplePSX(pixel, i.page_clut);\n"
	"		float2 C21 = samplePSX(pixel + float2(1.0, 0.0), i.page_clut);\n"
	"		float2 C12 = samplePSX(pixel + float2(0.0, 1.0), i.page_clut);\n"
	"		float2 C22 = samplePSX(pixel + float2(1.0, 1.0), i.page_clut);\n"
	"		float v11 = texelVisible(C11);\n"
	"		float v21 = texelVisible(C21);\n"
	"		float v12 = texelVisible(C12);\n"
	"		float v22 = texelVisible(C22);\n"
	"		float s11 = v11 * stpWeight(C11);\n"
	"		float s21 = v21 * stpWeight(C21);\n"
	"		float s12 = v12 * stpWeight(C12);\n"
	"		float s22 = v22 * stpWeight(C22);\n"
	"		float n11 = v11 - s11;\n"
	"		float n21 = v21 - s21;\n"
	"		float n12 = v12 - s12;\n"
	"		float n22 = v22 - s22;\n"
	"		float ax1 = lerp(v11, v21, fracPart.x);\n"
	"		float ax2 = lerp(v12, v22, fracPart.x);\n"
	"		float axm = lerp(ax1, ax2, fracPart.y);\n"
	"		float sx1 = lerp(s11, s21, fracPart.x);\n"
	"		float sx2 = lerp(s12, s22, fracPart.x);\n"
	"		float stp = lerp(sx1, sx2, fracPart.y);\n"
	"		float nx1 = lerp(n11, n21, fracPart.x);\n"
	"		float nx2 = lerp(n12, n22, fracPart.x);\n"
	"		float nonStp = lerp(nx1, nx2, fracPart.y);\n"
	"		float2 nearest = samplePSX(P, i.page_clut);\n"
	"		float visible = texelVisible(nearest);\n"
	"		sampledStp = visible * stpWeight(nearest);\n"
	"		clip(semiTransClip(visible, sampledStp, visible - sampledStp));\n"
	"		float4 w = float4((1.0-fracPart.x)*(1.0-fracPart.y),fracPart.x*(1.0-fracPart.y),(1.0-fracPart.x)*fracPart.y,fracPart.x*fracPart.y);\n"
	"		w *= float4(v11,v21,v12,v22);\n"
	"		color = (lut(C11)*w.x + lut(C21)*w.y + lut(C12)*w.z + lut(C22)*w.w) / max(dot(w,float4(1,1,1,1)),0.0001);\n"
	"	} else {\n"
	"		float2 rg = samplePSX(i.texcoord.xy, i.page_clut);\n"
	"		float visible = texelVisible(rg);\n"
	"		sampledStp = visible * stpWeight(rg);\n"
	"		clip(semiTransClip(visible, sampledStp, visible - sampledStp));\n"
	"		float4 t = lut(rg);\n"
	"		t.w = 1.0 - t.w;\n"
	"		color = t;\n"
	"	}\n"
	"	color = dither(color * i.color, i.ditherCoord, i.texcoord.w);\n"
	"	color.a = (psxDrawMaskSet != 0.0 || (psxTextureOutputStp != 0.0 && sampledStp >= 0.5)) ? 1.0 : 0.0;\n"
	"	return color;\n"
	"}\n";

global_variable const char *x360_psx32_main =
	"float2 texelSize : register(c16);\n"
	"float4 main(VS_OUT i) : COLOR0\n"
	"{\n"
	"	float2 tc = i.texcoord.xy * texelSize + texelSize * 0.5;\n"
	"	float4 color = tex2D(s_texture, tc);\n"
	"	color = dither(color * i.color, i.ditherCoord, i.texcoord.w);\n"
	"	color.a = (psxDrawMaskSet != 0.0) ? 1.0 : 0.0;\n"
	"	return color;\n"
	"}\n";

global_variable const char *x360_psx_vs =
	"row_major float4x4 Projection : register(c0);\n"
	"float4 DrawScale : register(c18);\n"
	"struct VS_OUT\n"
	"{\n"
	"	float4 pos : POSITION;\n"
	"	float4 texcoord : TEXCOORD0;\n"
	"	float4 color : COLOR0;\n"
	"	float4 page_clut : TEXCOORD1;\n"
	"	float2 ditherCoord : TEXCOORD2;\n"
	"	float z : TEXCOORD3;\n"
	"};\n"
	"VS_OUT main(float4 a_position : POSITION, float4 a_texcoord : TEXCOORD0, float4 a_color : COLOR0, float4 a_extra : TEXCOORD1)\n"
	"{\n"
	"	VS_OUT o;\n"
	"	float2 xy = a_position.xy;\n"
	"	xy.x = (xy.x - DrawScale.y) * DrawScale.x + DrawScale.y;\n"
	"	float4 clip = mul(float4(xy, 0.0, 1.0), Projection);\n"
	"	o.ditherCoord = a_position.xy;\n"
	"	o.texcoord = a_texcoord;\n"
	"	o.texcoord.w *= DrawScale.z;\n"
	"	o.texcoord.xy += a_extra.xy * 0.5;\n"
	"	o.color = a_color;\n"
	"	o.color.xyz *= a_texcoord.z;\n"
	"	o.page_clut.x = frac(a_position.z / 16.0) * 1024.0;\n"
	"	o.page_clut.y = floor(a_position.z / 16.0) * 256.0;\n"
	"	o.page_clut.z = frac(a_position.w / 64.0);\n"
	"	o.page_clut.w = floor(a_position.w / 64.0) / 512.0;\n"
	"	o.page_clut.xy += 0.00025;\n"
	"	o.page_clut.zw += 0.00025;\n"
	"	o.pos = float4(clip.x, -clip.y, 0.0, 1.0);\n"
	"	o.z = (clip.z - 40.0) * 0.005;\n"
	"	return o;\n"
	"}\n";

global_variable const char *x360_quad_vs =
	"float posFlipY : register(c16);\n"
	"struct QUAD_OUT\n"
	"{\n"
	"	float4 pos : POSITION;\n"
	"	float2 uv : TEXCOORD0;\n"
	"};\n"
	"QUAD_OUT main(float2 a_position : POSITION)\n"
	"{\n"
	"	QUAD_OUT o;\n"
	"	o.uv = a_position * 0.5 + 0.5;\n"
	"	o.pos = float4(a_position.x, a_position.y * posFlipY, 0.0, 1.0);\n"
	"	return o;\n"
	"}\n";

global_variable const char *x360_pack_ps =
	"sampler2D s_src : register(s0);\n"
	"float flipY : register(c0);\n"
	"float diagnosticSolid : register(c1);\n"
	"struct QUAD_OUT\n"
	"{\n"
	"	float4 pos : POSITION;\n"
	"	float2 uv : TEXCOORD0;\n"
	"};\n"
	"float4 main(QUAD_OUT i) : COLOR0\n"
	"{\n"
	"\tif (diagnosticSolid > 0.5) { return float4(31.0 / 255.0, 252.0 / 255.0, 0.0, 1.0); }\n"
	"	float2 uv = i.uv;\n"
	"	if (flipY != 0.0) { uv.y = 1.0 - uv.y; }\n"
	"	float4 c = floor(tex2D(s_src, uv) * 255.0 + 0.5);\n"
	"	float r3 = floor(c.r / 8.0);\n"
	"	float g3 = floor(c.g / 8.0);\n"
	"	float b3 = floor(c.b / 8.0);\n"
	"	float a1 = floor(c.a / 128.0);\n"
	"	float px16 = r3 + g3 * 32.0 + b3 * 1024.0 + a1 * 32768.0;\n"
	"	float lo = px16 - floor(px16 / 256.0) * 256.0;\n"
	"	float hi = floor(px16 / 256.0);\n"
	"	return float4(lo / 255.0, hi / 255.0, 0.0, 0.0);\n"
	"}\n";

/* Preserve untouched VRAM bytes in EDRAM before each partial pack draw. */
global_variable const char *x360_vram_copy_ps =
	"sampler2D s_src : register(s0);\n"
	"struct QUAD_OUT { float4 pos : POSITION; float2 uv : TEXCOORD0; };\n"
	"float4 main(QUAD_OUT i) : COLOR0 { return tex2D(s_src, i.uv); }\n";

/* Directional edge AA on the full-color 720p raster. Single-sample color/
 * stencil fit EDRAM; this avoids the extra surfaces and repeated geometry
 * submission required by 720p MSAA. Hardware filters only decoded RGBA. */
global_variable const char *x360_hd_present_ps =
    "sampler2D s_src : register(s0);\n"
    "struct QUAD_OUT { float4 pos : POSITION; float2 uv : TEXCOORD0; };\n"
    "float4 main(QUAD_OUT i) : COLOR0 {\n"
    " float2 p = float2(1.0 / 1280.0, 1.0 / 720.0);\n"
    " float3 M = tex2D(s_src, i.uv).rgb;\n"
    " float3 NW = tex2D(s_src, i.uv + float2(-p.x,-p.y)).rgb;\n"
    " float3 NE = tex2D(s_src, i.uv + float2(p.x,-p.y)).rgb;\n"
    " float3 SW = tex2D(s_src, i.uv + float2(-p.x,p.y)).rgb;\n"
    " float3 SE = tex2D(s_src, i.uv + float2(p.x,p.y)).rgb;\n"
    " float3 L = float3(0.299,0.587,0.114);\n"
    " float m=dot(M,L), nw=dot(NW,L), ne=dot(NE,L), sw=dot(SW,L), se=dot(SE,L);\n"
    " float lo=min(m,min(min(nw,ne),min(sw,se)));\n"
    " float hi=max(m,max(max(nw,ne),max(sw,se)));\n"
    " if(hi-lo < max(0.03125,hi*0.125)) return float4(M,1.0);\n"
    " float2 dir=float2(-((nw+ne)-(sw+se)),(nw+sw)-(ne+se));\n"
    " float reduce=max((nw+ne+sw+se)*0.03125,0.0078125);\n"
    " dir=clamp(dir/(min(abs(dir.x),abs(dir.y))+reduce),-8.0,8.0)*p;\n"
    " float3 A=0.5*(tex2D(s_src,i.uv-dir/6.0).rgb+tex2D(s_src,i.uv+dir/6.0).rgb);\n"
    " float3 B=A*0.5+0.25*(tex2D(s_src,i.uv-dir*0.5).rgb+tex2D(s_src,i.uv+dir*0.5).rgb);\n"
    " float b=dot(B,L); return float4((b<lo || b>hi)?A:B,1.0);\n"
    "}\n";

global_variable const char *x360_solid_diagnostic_ps =
	"float4 main() : COLOR0 { return float4(31.0 / 255.0, 252.0 / 255.0, 0.0, 1.0); }\n";

global_variable const char *x360_present_vs =
	"float4 sourceRect : register(c17);\n"
	"struct PRESENT_OUT\n"
	"{\n"
	"	float4 pos : POSITION;\n"
	"	float2 uv : TEXCOORD0;\n"
	"};\n"
	"PRESENT_OUT main(float2 a_position : POSITION)\n"
	"{\n"
	"	PRESENT_OUT o;\n"
	"	float2 screenUV = a_position * 0.5 + 0.5;\n"
	"	float2 sourcePixel = sourceRect.xy + float2(screenUV.x, 1.0 - screenUV.y) * sourceRect.zw;\n"
	"	o.uv = sourcePixel / float2(1024.0, 512.0);\n"
	"	o.pos = float4(a_position.x, a_position.y, 0.0, 1.0);\n"
	"	return o;\n"
	"}\n";

global_variable const char *x360_present_ps =
	"sampler2D s_texture : register(s0);\n"
	"struct PRESENT_OUT\n"
	"{\n"
	"	float4 pos : POSITION;\n"
	"	float2 uv : TEXCOORD0;\n"
	"};\n"
	"float4 main(PRESENT_OUT i) : COLOR0\n"
	"{\n"
	"	float2 bytes = floor(tex2D(s_texture, i.uv).rg * 255.0 + 0.5);\n"
	"	float pixel = bytes.r + bytes.g * 256.0;\n"
	"	float c5r = pixel - floor(pixel / 32.0) * 32.0;\n"
	"	float c5g = floor(pixel / 32.0) - floor(pixel / 1024.0) * 32.0;\n"
	"	float c5b = floor(pixel / 1024.0) - floor(pixel / 32768.0) * 32.0;\n"
	"	float stp = floor(pixel / 32768.0);\n"
	"	float3 color5 = float3(c5r, c5g, c5b);\n"
	"	float3 color8 = (color5 * 8.0 + floor(color5 / 4.0)) / 255.0;\n"
	"	return float4(color8, stp);\n"
	"}\n";

/* ---------------------------------------------------------------------------------------
 * Shader compilation helpers
 * --------------------------------------------------------------------------------------- */

internal int NativeRenderer_CompileStage(const char *source, const char *entry, const char *profile, void **outShader)
{
	ID3DXBuffer *code = NULL;
	ID3DXBuffer *errors = NULL;
	HRESULT hr;
	int isVertex = (profile[0] == 'v');

	hr = D3DXCompileShader(source, (UINT)strlen(source), NULL, NULL, entry, profile, 0, &code, &errors, NULL);
	if (errors != NULL)
	{
		NATIVE_RENDERER_ERROR("%s\n", (const char *)errors->lpVtbl->GetBufferPointer(errors));
		errors->lpVtbl->Release(errors);
		errors = NULL;
	}

	if (FAILED(hr) || (code == NULL))
	{
		NATIVE_RENDERER_ERROR("%s\n", "shader compilation failed");
		if (code != NULL)
		{
			code->lpVtbl->Release(code);
		}
		return 0;
	}

	if (isVertex)
	{
		hr = IDirect3DDevice9_CreateVertexShader(s_device, (CONST DWORD *)code->lpVtbl->GetBufferPointer(code), (D3DVertexShader **)outShader);
	}
	else
	{
		hr = IDirect3DDevice9_CreatePixelShader(s_device, (CONST DWORD *)code->lpVtbl->GetBufferPointer(code), (D3DPixelShader **)outShader);
	}

	code->lpVtbl->Release(code);

	if (*outShader == NULL)
	{
		s_shaderCompileFailures++;
		NATIVE_RENDERER_ERROR("%s (%s / %s)\n", "device shader creation failed", entry, profile);
		return 0;
	}

	return 1;
}

/* Concatenates up to three shader fragments into one source buffer. */
internal const char *NativeRenderer_BuildShader(char *buffer, size_t bufferSize, const char *a, const char *b, const char *c)
{
	buffer[0] = '\0';

	if (a != NULL)
	{
		strncat(buffer, a, bufferSize - strlen(buffer) - 1);
	}
	if (b != NULL)
	{
		strncat(buffer, b, bufferSize - strlen(buffer) - 1);
	}
	if (c != NULL)
	{
		strncat(buffer, c, bufferSize - strlen(buffer) - 1);
	}

	return buffer;
}

/* ---------------------------------------------------------------------------------------
 * Device and render targets
 * --------------------------------------------------------------------------------------- */

int NativeRenderer_InitialiseRender(char *windowName, int width, int height, int fullscreen)
{
	D3DPRESENT_PARAMETERS pp;
	HRESULT hr;
    FILE *captureSettings;
    FILE *graphicsSettings;
    char graphicsKey[32];
    int graphicsValue;
    extern int g_nativeHDEnableInterpolation;

    captureSettings = fopen("game:\\assets\\ctr360_capture.txt", "r");
    if (captureSettings != NULL)
    {
        fscanf(captureSettings, "%d", &s_hdCaptureDiagnostics);
        fclose(captureSettings);
    }
    graphicsSettings = fopen("game:\\assets\\ctr360_graphics.txt", "r");
    if (graphicsSettings != NULL)
    {
        while (fscanf(graphicsSettings, "%31s %d", graphicsKey, &graphicsValue) == 2)
        {
            graphicsValue = graphicsValue != 0;
            if (strcmp(graphicsKey, "interpolation") == 0) g_nativeHDEnableInterpolation = graphicsValue;
            else if (strcmp(graphicsKey, "texture_filter") == 0) g_cfg_bilinearFiltering = graphicsValue;
            else if (strcmp(graphicsKey, "edge_aa") == 0) s_hdEdgeAA = graphicsValue;
        }
        fclose(graphicsSettings);
    }
    Platform_Log("[HD] 1280x720 expanded 16:9; interpolation=%d filter=%d edgeAA=%d diagnostics=%d\n",g_nativeHDEnableInterpolation,g_cfg_bilinearFiltering,s_hdEdgeAA,s_hdCaptureDiagnostics);

	(void)windowName;
	(void)fullscreen;
	(void)width;
	(void)height;

	ZeroMemory(&pp, sizeof(pp));
	pp.BackBufferWidth = 1280;
	pp.BackBufferHeight = 720;
	pp.BackBufferFormat = D3DFMT_A8R8G8B8;
	pp.BackBufferCount = 1;
	pp.MultiSampleType = D3DMULTISAMPLE_NONE;
	pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
	pp.EnableAutoDepthStencil = TRUE;
	pp.AutoDepthStencilFormat = D3DFMT_D24S8;
	pp.PresentationInterval = D3DPRESENT_INTERVAL_ONE;

	s_d3d = Direct3DCreate9(D3D_SDK_VERSION);
	if (s_d3d == NULL)
	{
		NATIVE_RENDERER_ERROR("%s\n", "Direct3DCreate9 failed");
		return 0;
	}

	hr = Direct3D_CreateDevice(0, D3DDEVTYPE_HAL, NULL, D3DCREATE_HARDWARE_VERTEXPROCESSING, &pp, &s_device);
	if (FAILED(hr) || (s_device == NULL))
	{
		NATIVE_RENDERER_ERROR("%s (hr=0x%08X)\n", "CreateDevice failed", (unsigned)hr);
		return 0;
	}

	g_windowWidth = (int)pp.BackBufferWidth;
	g_windowHeight = (int)pp.BackBufferHeight;

	Platform_Log("[CTR Renderer] D3D9 device up: %dx%d backbuffer\n", g_windowWidth, g_windowHeight);

	/* The 360 has no PC-style swap chain object: the back buffer surface is
	 * fetched from the device and is what GL called framebuffer 0. */
	if (FAILED(IDirect3DDevice9_GetBackBuffer(s_device, 0, 0, 0, &s_backBuffer)))
	{
		s_backBuffer = NULL;
		NATIVE_RENDERER_ERROR("%s\n", "GetBackBuffer failed");
	}
	if (FAILED(IDirect3DDevice9_GetDepthStencilSurface(s_device, &s_backBufferDepth)))
	{
		s_backBufferDepth = NULL;
	}
	Platform_Log("[CTR Renderer] back buffer surface: %s\n", (s_backBuffer != NULL) ? "ok" : "missing");

	IDirect3DDevice9_SetRenderState(s_device, D3DRS_ZENABLE, FALSE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_CULLMODE, D3DCULL_NONE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_FILLMODE, D3DFILL_SOLID);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_ALPHABLENDENABLE, FALSE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILENABLE, TRUE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_SCISSORTESTENABLE, FALSE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_COLORWRITEENABLE, D3DCOLORWRITEENABLE_ALL);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_SEPARATEALPHABLENDENABLE, TRUE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_SRCBLENDALPHA, D3DBLEND_ONE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_DESTBLENDALPHA, D3DBLEND_ZERO);

	IDirect3DDevice9_SetSamplerState(s_device, 0, D3DSAMP_MINFILTER, D3DTEXF_POINT);
	IDirect3DDevice9_SetSamplerState(s_device, 0, D3DSAMP_MAGFILTER, D3DTEXF_POINT);
	IDirect3DDevice9_SetSamplerState(s_device, 0, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
	IDirect3DDevice9_SetSamplerState(s_device, 1, D3DSAMP_MINFILTER, D3DTEXF_POINT);
	IDirect3DDevice9_SetSamplerState(s_device, 1, D3DSAMP_MAGFILTER, D3DTEXF_POINT);
	IDirect3DDevice9_SetSamplerState(s_device, 1, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
	IDirect3DDevice9_SetSamplerState(s_device, 1, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP);
	IDirect3DDevice9_SetSamplerState(s_device, 1, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);

	/* The 360 backbuffer is the fixed 720p surface created above; the caller's
	 * requested window size is a host-window concept that does not apply.
	 * World projection expands horizontally for 16:9; authored UI is centered
	 * at its original 4:3 aspect by the per-draw shader scale. */
	NativeRenderer_SetPresentationAspect(16, 9);

	return 1;
}

void NativeRenderer_ResetDevice(void)
{
	NativeRenderer_UpdatePresentationViewport();
	NativeRenderer_UpdateSwapIntervalState(0);
}

void NativeRenderer_UpdateSwapIntervalState(int swapInterval)
{
	s_swapInterval = swapInterval;
}

void NativeRenderer_Shutdown(void)
{
	if (s_device != NULL)
	{
		IDirect3DDevice9_Release(s_device);
		s_device = NULL;
	}
	if (s_d3d != NULL)
	{
		IDirect3D9_Release(s_d3d);
		s_d3d = NULL;
	}
}

D3DDevice *X360Render_GetDevice(void)
{
	return s_device;
}

internal void NativeRenderer_SetViewPort(int x, int y, int width, int height)
{
	D3DVIEWPORT9 viewport;

	ZeroMemory(&viewport, sizeof(viewport));
	viewport.X = (DWORD)x;
	viewport.Y = (DWORD)y;
	viewport.Width = (DWORD)width;
	viewport.Height = (DWORD)height;
	viewport.MinZ = 0.0f;
	viewport.MaxZ = 1.0f;

	if (s_device != NULL)
	{
		IDirect3DDevice9_SetViewport(s_device, &viewport);
	}
}

/* GL-style viewport: y is measured from the bottom of the target, so D3D gets
 * Height - y - h. Only the backbuffer pass needs this (texture targets use
 * GL-identical coordinates directly). */
internal void NativeRenderer_SetViewPortGL(int x, int y, int width, int height, int targetHeight)
{
	NativeRenderer_SetViewPort(x, targetHeight - y - height, width, height);
}

internal void NativeRenderer_DestroyRenderTarget(struct X360RenderTarget *target)
{
	if (target->depthStencil != NULL)
	{
		IDirect3DSurface9_Release(target->depthStencil);
	}
	if (target->surface != NULL)
	{
		IDirect3DSurface9_Release(target->surface);
	}
	if (target->texture != NULL)
	{
		IDirect3DTexture9_Release(target->texture);
	}
	ZeroMemory(target, sizeof(*target));
}

internal void NativeRenderer_EnsureRenderTarget(struct X360RenderTarget *target, int width, int height)
{
	D3DSURFACE_PARAMETERS colorParams = {0};
	D3DSURFACE_PARAMETERS depthParams = {0};
	DWORD vramBytes = XGSurfaceSize(VRAM_WIDTH, VRAM_HEIGHT, D3DFMT_A8R8G8B8, D3DMULTISAMPLE_NONE);
	DWORD mainColorBytes = XGSurfaceSize(X360_MAIN_EDRAM_MAX_W, X360_MAIN_EDRAM_MAX_H, D3DFMT_A8R8G8B8, D3DMULTISAMPLE_NONE);
	DWORD mainDepthBytes = XGSurfaceSize(X360_MAIN_EDRAM_MAX_W, X360_MAIN_EDRAM_MAX_H, D3DFMT_D24S8, D3DMULTISAMPLE_NONE);
	DWORD offscreenColorBytes = XGSurfaceSize(X360_OFFSCREEN_EDRAM_MAX_W, X360_OFFSCREEN_EDRAM_MAX_H, D3DFMT_A8R8G8B8, D3DMULTISAMPLE_NONE);
    if (vramBytes + mainColorBytes + mainDepthBytes > 2048)
    {
        NATIVE_RENDERER_ERROR("%s\n", "HD color/stencil layout exceeds Xbox 360 EDRAM");
        return;
    }
	Platform_Log("[trace] EnsureRT enter\n");
	if (width < 1)
	{
		width = 1;
	}
	if (height < 1)
	{
		height = 1;
	}
	if (target == &s_mainRenderTarget)
	{
		if (width > X360_MAIN_EDRAM_MAX_W || height > X360_MAIN_EDRAM_MAX_H)
		{
			NATIVE_RENDERER_ERROR("main target exceeds EDRAM reservation: %dx%d\n", width, height);
			return;
		}
		colorParams.Base = vramBytes;
		depthParams.Base = vramBytes + mainColorBytes;
	}
	else
	{
		if (width > X360_OFFSCREEN_EDRAM_MAX_W || height > X360_OFFSCREEN_EDRAM_MAX_H)
		{
			NATIVE_RENDERER_ERROR("offscreen target exceeds EDRAM reservation: %dx%d\n", width, height);
			return;
		}
        /* XGSurfaceSize returns EDRAM tiles, not bytes. Offscreen color and
         * stencil share the VRAM bridge's reservation, never the live main
         * color/stencil. Flush resolves offscreen before that bridge writes. */
        offscreenColorBytes = XGSurfaceSize(width, height, D3DFMT_A8R8G8B8, D3DMULTISAMPLE_NONE);
        if (offscreenColorBytes * 2 > vramBytes)
        {
            NATIVE_RENDERER_ERROR("offscreen color/stencil exceeds bridge reservation: %dx%d\n", width, height);
            return;
        }
        colorParams.Base = 0;
        depthParams.Base = offscreenColorBytes;
	}

	if ((target->width == width) && (target->height == height) && (target->texture != NULL))
	{
		return;
	}

	Platform_Log("[trace] EnsureRT: (re)create %dx%d -> %dx%d\n", target->width, target->height, width, height);

	NativeRenderer_DestroyRenderTarget(target);
	Platform_Log("[trace] EnsureRT: destroy done\n");

	if (s_device == NULL)
	{
		return;
	}

	if (FAILED(IDirect3DDevice9_CreateTexture(s_device, (UINT)width, (UINT)height, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_DEFAULT, &target->texture, NULL)))
	{
		NATIVE_RENDERER_ERROR("%s\n", "render target texture creation failed");
		return;
	}
	Platform_Log("[trace] EnsureRT: CreateTexture ok\n");

	if (FAILED(IDirect3DDevice9_CreateRenderTarget(s_device, (UINT)width, (UINT)height,
	                                           D3DFMT_A8R8G8B8, D3DMULTISAMPLE_NONE,
	                                           0, FALSE, &target->surface, &colorParams)))
	{
		NATIVE_RENDERER_ERROR("%s\n", "EDRAM render target creation failed");
		NativeRenderer_DestroyRenderTarget(target);
		return;
	}
	Platform_Log("[trace] EnsureRT: GetSurfaceLevel ok\n");

	if (FAILED(IDirect3DDevice9_CreateDepthStencilSurface(s_device, (UINT)width, (UINT)height, D3DFMT_D24S8, D3DMULTISAMPLE_NONE, 0, TRUE, &target->depthStencil, &depthParams)))
	{
		NATIVE_RENDERER_ERROR("%s\n", "stencil surface creation failed");
		NativeRenderer_DestroyRenderTarget(target);
		return;
	}
	Platform_Log("[trace] EnsureRT: CreateDepthStencilSurface ok\n");

	target->width = width;
	target->height = height;
	s_lastBoundTexture = (TextureID)-1;
	Platform_Log("[trace] EnsureRT: done %dx%d EDRAM color=%lu depth=%lu\n", width, height, (unsigned long)colorParams.Base, (unsigned long)depthParams.Base);
}

internal void NativeRenderer_SetRenderTarget(struct X360RenderTarget *target)
{
	if (s_device == NULL)
	{
		return;
	}

	if (target == NULL)
	{
		/* GL framebuffer 0: the window, which on 360 is the swap chain's back
		 * buffer. Binding NULL here would bind no target at all. */
		if (s_boundTarget != &s_nullTarget)
		{
			IDirect3DDevice9_SetRenderTarget(s_device, 0, s_backBuffer);
			IDirect3DDevice9_SetDepthStencilSurface(s_device, s_backBufferDepth);
			s_boundTarget = &s_nullTarget;
			s_lastBoundTexture = (TextureID)-1;
		}
		return;
	}

	if (s_boundTarget == target)
	{
		return;
	}

	IDirect3DDevice9_SetRenderTarget(s_device, 0, target->surface);
	IDirect3DDevice9_SetDepthStencilSurface(s_device, target->depthStencil);
	s_boundTarget = target;
	s_lastBoundTexture = (TextureID)-1;
}

internal void NativeRenderer_BindMainRenderTarget(void)
{
	int width = activeDispEnv.disp.w;
	int height = activeDispEnv.disp.h;
	if ((width <= 0) || (height <= 0))
	{
		width = activeDrawEnv.clip.w;
		height = activeDrawEnv.clip.h;
	}

	NativeRenderer_EnsureRenderTarget(&s_mainRenderTarget, 1280, 720);
	NativeRenderer_SetRenderTarget(&s_mainRenderTarget);
}

/* ---------------------------------------------------------------------------------------
 * PSX textures and pipelines
 * --------------------------------------------------------------------------------------- */

/* PSX 16-bit color -> RGBA lookup table, same layout as NativeRenderer_InitRG8LUT
 * (R/G/B expanded 5->8, bit15 in alpha's top bit). Stored as D3DCOLOR words so
 * the A8R8G8B8 texture returns the same channels the GL RGBA8 texture did. */
global_variable u32 rgLUT[LUT_WIDTH * LUT_HEIGHT];

internal void NativeRenderer_InitRG8LUT(void)
{
	u16 y;
	u16 x;

	for (y = 0; y < LUT_HEIGHT; y++)
	{
		for (x = 0; x < LUT_WIDTH; x++)
		{
			const u16 c = (u16)((y << 8) | x);
			u8 r = (u8)((c & 31) << 3);
			u8 g = (u8)(((c >> 5) & 31) << 3);
			u8 b = (u8)(((c >> 10) & 31) << 3);
			u8 a = (u8)(((c >> 15) & 1) << 7);
			rgLUT[(y * LUT_WIDTH) + x] = ((u32)a << 24) | ((u32)r << 16) | ((u32)g << 8) | (u32)b;
		}
	}
}

internal void NativeRenderer_GenerateCommonTextures(void)
{
	D3DLOCKED_RECT lock;

	/* 1x1 white texture, same role as the GL white texture. */
	if (FAILED(IDirect3DDevice9_CreateTexture(s_device, 1, 1, 1, 0, D3DFMT_LIN_A8R8G8B8, D3DPOOL_DEFAULT, &s_whiteTexture, NULL)))
	{
		NATIVE_RENDERER_ERROR("%s\n", "white texture creation failed");
		return;
	}
	if (SUCCEEDED(IDirect3DTexture9_LockRect(s_whiteTexture, 0, &lock, NULL, 0)))
	{
		*(u32 *)lock.pBits = 0xFFFFFFFF;
		IDirect3DTexture9_UnlockRect(s_whiteTexture, 0);
	}
	s_whiteTextureId = NativeRenderer_IdFromTexture(s_whiteTexture);

	/* 256x256 CLUT lookup table on sampler 1, immutable. */
	if (FAILED(IDirect3DDevice9_CreateTexture(s_device, LUT_WIDTH, LUT_HEIGHT, 1, 0, D3DFMT_LIN_A8R8G8B8, D3DPOOL_DEFAULT, &s_lutTexture, NULL)))
	{
		NATIVE_RENDERER_ERROR("%s\n", "LUT texture creation failed");
		return;
	}
	if (SUCCEEDED(IDirect3DTexture9_LockRect(s_lutTexture, 0, &lock, NULL, 0)))
	{
		int row;
		for (row = 0; row < LUT_HEIGHT; row++)
		{
			memcpy((u8 *)lock.pBits + (row * lock.Pitch), &rgLUT[row * LUT_WIDTH], LUT_WIDTH * sizeof(u32));
		}
		IDirect3DTexture9_UnlockRect(s_lutTexture, 0);
	}
	IDirect3DDevice9_SetTexture(s_device, 1, (D3DBaseTexture *)s_lutTexture);
}

global_variable char s_shaderSourceBuffer[24576];

internal void NativeRenderer_InitialisePSXShaders(void)
{
	(void)NativeRenderer_BuildShader(s_shaderSourceBuffer, sizeof(s_shaderSourceBuffer), x360_psx_common, x360_psx_sample4, x360_psx_main);
	NativeRenderer_CompileStage(s_shaderSourceBuffer, "main", "ps_3_0", (void **)&s_gteShader4.shader);

	(void)NativeRenderer_BuildShader(s_shaderSourceBuffer, sizeof(s_shaderSourceBuffer), x360_psx_common, x360_psx_sample8, x360_psx_main);
	NativeRenderer_CompileStage(s_shaderSourceBuffer, "main", "ps_3_0", (void **)&s_gteShader8.shader);

	(void)NativeRenderer_BuildShader(s_shaderSourceBuffer, sizeof(s_shaderSourceBuffer), x360_psx_common, x360_psx_sample16, x360_psx_main);
	NativeRenderer_CompileStage(s_shaderSourceBuffer, "main", "ps_3_0", (void **)&s_gteShader16.shader);

	(void)NativeRenderer_BuildShader(s_shaderSourceBuffer, sizeof(s_shaderSourceBuffer), x360_psx_common, x360_psx32_main, NULL);
	NativeRenderer_CompileStage(s_shaderSourceBuffer, "main", "ps_3_0", (void **)&s_gteShader32Rgba.shader);

	NativeRenderer_CompileStage(x360_psx_vs, "main", "vs_3_0", (void **)&s_gteVertexShader);
}

internal void NativeRenderer_InitVRAMPipelines(void)
{
	D3DVERTEXELEMENT9 elements[5];
	D3DVERTEXELEMENT9 quadElements[2];
	HRESULT hr2;
	int i;

	for (i = 0; i < MAX_NUM_VERTEX_BUFFERS; i++)
	{
		hr2 = IDirect3DDevice9_CreateVertexBuffer(s_device, MAX_VERTEX_BUFFER_SIZE * sizeof(X360Vertex), D3DUSAGE_WRITEONLY, 0, D3DPOOL_DEFAULT, &s_vertexBuffer[i], NULL);
		if (FAILED(hr2))
		{
			s_vertexBuffer[i] = NULL;
		}
		if (s_vertexBuffer[i] == NULL)
		{
			NATIVE_RENDERER_ERROR("%s\n", "vertex buffer creation failed");
			return;
		}
	}

	elements[0].Stream = 0;
	elements[0].Offset = 0;
	elements[0].Type = D3DDECLTYPE_FLOAT4;
	elements[0].Method = D3DDECLMETHOD_DEFAULT;
	elements[0].Usage = D3DDECLUSAGE_POSITION;
	elements[0].UsageIndex = 0;
	elements[1].Stream = 0;
	elements[1].Offset = 16;
	elements[1].Type = D3DDECLTYPE_FLOAT4;
	elements[1].Method = D3DDECLMETHOD_DEFAULT;
	elements[1].Usage = D3DDECLUSAGE_TEXCOORD;
	elements[1].UsageIndex = 0;
	elements[2].Stream = 0;
	elements[2].Offset = 32;
	elements[2].Type = D3DDECLTYPE_FLOAT4;
	elements[2].Method = D3DDECLMETHOD_DEFAULT;
	elements[2].Usage = D3DDECLUSAGE_COLOR;
	elements[2].UsageIndex = 0;
	elements[3].Stream = 0;
	elements[3].Offset = 48;
	elements[3].Type = D3DDECLTYPE_FLOAT4;
	elements[3].Method = D3DDECLMETHOD_DEFAULT;
	elements[3].Usage = D3DDECLUSAGE_TEXCOORD;
	elements[3].UsageIndex = 1;
	{
		const D3DVERTEXELEMENT9 endElement = D3DDECL_END();
		elements[4] = endElement;
	}

	hr2 = IDirect3DDevice9_CreateVertexDeclaration(s_device, elements, &s_gteVertexDecl);
	if (FAILED(hr2))
	{
		s_gteVertexDecl = NULL;
	}
	if (s_gteVertexDecl == NULL)
	{
		NATIVE_RENDERER_ERROR("%s\n", "vertex declaration creation failed");
	}

	quadElements[0].Stream = 0;
	quadElements[0].Offset = 0;
	quadElements[0].Type = D3DDECLTYPE_FLOAT2;
	quadElements[0].Method = D3DDECLMETHOD_DEFAULT;
	quadElements[0].Usage = D3DDECLUSAGE_POSITION;
	quadElements[0].UsageIndex = 0;
	{
		const D3DVERTEXELEMENT9 endElement = D3DDECL_END();
		quadElements[1] = endElement;
	}
	hr2 = IDirect3DDevice9_CreateVertexDeclaration(s_device, quadElements, &s_quadVertexDecl);
	if (FAILED(hr2) || s_quadVertexDecl == NULL)
	{
		NATIVE_RENDERER_ERROR("%s\n", "quad vertex declaration creation failed");
	}

	NativeRenderer_CompileStage(x360_quad_vs, "main", "vs_3_0", (void **)&s_packVertexShader);
	NativeRenderer_CompileStage(x360_pack_ps, "main", "ps_3_0", (void **)&s_packPixelShader);
	NativeRenderer_CompileStage(x360_vram_copy_ps, "main", "ps_3_0", (void **)&s_vramCopyPixelShader);
	NativeRenderer_CompileStage(x360_solid_diagnostic_ps, "main", "ps_3_0", (void **)&s_solidDiagnosticPixelShader);
	NativeRenderer_CompileStage(x360_present_vs, "main", "vs_3_0", (void **)&s_presentVertexShader);
	NativeRenderer_CompileStage(x360_present_ps, "main", "ps_3_0", (void **)&s_presentPixelShader);
    NativeRenderer_CompileStage(x360_hd_present_ps, "main", "ps_3_0", (void **)&s_hdPresentPixelShader);
}

int NativeRenderer_InitialisePSX(void)
{
	D3DSURFACE_PARAMETERS vramSurfaceParams = {0};
	memset(s_vram.cpuPixels, 0, sizeof(s_vram.cpuPixels));
	s_vram.cpuDirtyRects[0].x = 0;
	s_vram.cpuDirtyRects[0].y = 0;
	s_vram.cpuDirtyRects[0].w = VRAM_WIDTH;
	s_vram.cpuDirtyRects[0].h = VRAM_HEIGHT;
	s_vram.cpuDirtyRectCount = 1;
	memset(s_vram.gpuNewerTiles, 0, sizeof(s_vram.gpuNewerTiles));

	NativeRenderer_InitRG8LUT();
	NativeRenderer_GenerateCommonTextures();
	NativeRenderer_InitialisePSXShaders();
	NativeRenderer_InitVRAMPipelines();

	/* Store each PSX 16-bit pixel as two 8-bit channels in a supported 32-bit
	 * color target. The CPU mirror keeps its original u16 representation. */
	if (FAILED(IDirect3DDevice9_CreateTexture(s_device, VRAM_WIDTH, VRAM_HEIGHT, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_DEFAULT, &s_vram.texture, NULL)))
	{
		NATIVE_RENDERER_ERROR("%s\n", "VRAM texture creation failed");
		return 0;
	}
	vramSurfaceParams.Base = 0;
	if (FAILED(IDirect3DDevice9_CreateRenderTarget(s_device, VRAM_WIDTH, VRAM_HEIGHT,
	                                           D3DFMT_A8R8G8B8, D3DMULTISAMPLE_NONE,
	                                           0, FALSE, &s_vram.surface, &vramSurfaceParams)))
	{
		NATIVE_RENDERER_ERROR("%s\n", "VRAM EDRAM surface creation failed");
		return 0;
	}

	ZeroMemory(&s_mainRenderTarget, sizeof(s_mainRenderTarget));
	s_mainRenderTarget.width = 1;
	s_mainRenderTarget.height = 1;
	ZeroMemory(&s_offscreenRenderTarget, sizeof(s_offscreenRenderTarget));
	s_offscreenRenderTarget.width = 1;
	s_offscreenRenderTarget.height = 1;
	ZeroMemory(&s_nullTarget, sizeof(s_nullTarget));

	NativeRenderer_SetRenderTarget(NULL);

	s_curVertexBuffer = 0;
	s_boundVertexBuffer = -1;

	s_previousBlendMode = BM_NONE;
	s_previousDepthMode = 0;
	s_previousStencilMode = 0;
	s_previousScissorState = 0;
	s_previousOffscreenState = 0;
	s_previousOffscreen.x = 0;
	s_previousOffscreen.y = 0;
	s_previousOffscreen.w = 0;
	s_previousOffscreen.h = 0;
	s_previousShader = (ShaderID)-1;
	s_lastBoundTexture = (TextureID)-1;

	NativeRenderer_ResetDevice();

	Platform_Log("[CTR Renderer] PSX pipeline ready (shader failures: %d, vertex buffer: %s)\n",
		s_shaderCompileFailures, (s_vertexBuffer[0] != NULL) ? "ok" : "failed");

	return 1;
}

/* ---------------------------------------------------------------------------------------
 * Presentation helpers
 * --------------------------------------------------------------------------------------- */

internal int NativeRenderer_IntAbs(int value)
{
	return value < 0 ? -value : value;
}

internal int NativeRenderer_GCD(int a, int b)
{
	a = NativeRenderer_IntAbs(a);
	b = NativeRenderer_IntAbs(b);

	while (b != 0)
	{
		int t = a % b;
		a = b;
		b = t;
	}

	return a;
}

internal void NativeRenderer_SetPresentationAspect(int width, int height)
{
	const int divisor = NativeRenderer_GCD(width, height);

	if ((width <= 0) || (height <= 0) || (divisor <= 0))
	{
		return;
	}

	s_presentAspectW = width / divisor;
	s_presentAspectH = height / divisor;
}

internal void NativeRenderer_UpdatePresentationViewport(void)
{
	int viewportW;
	int viewportH;

	if ((g_windowWidth <= 0) || (g_windowHeight <= 0) || (s_presentAspectW <= 0) || (s_presentAspectH <= 0))
	{
		s_presentViewport.x = 0;
		s_presentViewport.y = 0;
		s_presentViewport.w = g_windowWidth;
		s_presentViewport.h = g_windowHeight;
		return;
	}

	viewportW = g_windowWidth;
	viewportH = (viewportW * s_presentAspectH) / s_presentAspectW;

	if (viewportH > g_windowHeight)
	{
		viewportH = g_windowHeight;
		viewportW = (viewportH * s_presentAspectW) / s_presentAspectH;
	}

	if (viewportW < 1)
	{
		viewportW = 1;
	}
	if (viewportH < 1)
	{
		viewportH = 1;
	}

	s_presentViewport.w = viewportW;
	s_presentViewport.h = viewportH;
	s_presentViewport.x = (g_windowWidth - viewportW) / 2;
	s_presentViewport.y = (g_windowHeight - viewportH) / 2;
}

/* Bars are cleared on the backbuffer, whose row 0 is the visual top row, so
 * the GL (bottom-left) rect y is converted here. */
internal void NativeRenderer_ClearHostRect(int x, int y, int width, int height)
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
}

internal void NativeRenderer_ClearPresentationBars(void)
{
	const int viewportRight = s_presentViewport.x + s_presentViewport.w;
	const int viewportTop = s_presentViewport.y + s_presentViewport.h;

	if ((g_windowWidth <= 0) || (g_windowHeight <= 0))
	{
		return;
	}

	if ((s_presentViewport.x == 0) && (s_presentViewport.y == 0) && (s_presentViewport.w == g_windowWidth) && (s_presentViewport.h == g_windowHeight))
	{
		return;
	}

	NativeRenderer_SetRenderTarget(NULL);

	NativeRenderer_ClearHostRect(0, 0, s_presentViewport.x, g_windowHeight);
	NativeRenderer_ClearHostRect(viewportRight, 0, g_windowWidth - viewportRight, g_windowHeight);
	NativeRenderer_ClearHostRect(s_presentViewport.x, 0, s_presentViewport.w, s_presentViewport.y);
	NativeRenderer_ClearHostRect(s_presentViewport.x, viewportTop, s_presentViewport.w, g_windowHeight - viewportTop);
}

/* ---------------------------------------------------------------------------------------
 * VRAM management
 * --------------------------------------------------------------------------------------- */

internal int NativeRenderer_RectEquals16(const RECT16 *a, const RECT16 *b)
{
	return a->x == b->x && a->y == b->y && a->w == b->w && a->h == b->h;
}

internal s32 NativeRenderer_ClipVRAMRect(RECT16 *out, int x, int y, int w, int h)
{
	if ((w <= 0) || (h <= 0))
	{
		return 0;
	}

	if (x < 0)
	{
		w += x;
		x = 0;
	}
	if (y < 0)
	{
		h += y;
		y = 0;
	}
	if ((x + w) > VRAM_WIDTH)
	{
		w = VRAM_WIDTH - x;
	}
	if ((y + h) > VRAM_HEIGHT)
	{
		h = VRAM_HEIGHT - y;
	}

	if ((w <= 0) || (h <= 0))
	{
		return 0;
	}

	out->x = (s16)x;
	out->y = (s16)y;
	out->w = (s16)w;
	out->h = (s16)h;
	return 1;
}

internal int NativeRenderer_DirtyRectContains(const RECT16 *outer, const RECT16 *inner)
{
	return (inner->x >= outer->x) && (inner->y >= outer->y) && ((inner->x + inner->w) <= (outer->x + outer->w)) &&
	       ((inner->y + inner->h) <= (outer->y + outer->h));
}

internal void NativeRenderer_AppendCpuDirtyRect(const RECT16 *rect)
{
	s32 i;
	s32 writeIndex;

	if ((s_vram.cpuDirtyRectCount > 0) && NativeRenderer_DirtyRectContains(&s_vram.cpuDirtyRects[0], rect))
	{
		return;
	}

	writeIndex = 0;
	for (i = 0; i < s_vram.cpuDirtyRectCount; i++)
	{
		if (NativeRenderer_DirtyRectContains(rect, &s_vram.cpuDirtyRects[i]))
		{
			continue;
		}
		s_vram.cpuDirtyRects[writeIndex++] = s_vram.cpuDirtyRects[i];
	}
	s_vram.cpuDirtyRectCount = writeIndex;

	if (s_vram.cpuDirtyRectCount >= NATIVE_VRAM_DIRTY_RECT_CAP)
	{
		s_vram.cpuDirtyRects[0].x = 0;
		s_vram.cpuDirtyRects[0].y = 0;
		s_vram.cpuDirtyRects[0].w = VRAM_WIDTH;
		s_vram.cpuDirtyRects[0].h = VRAM_HEIGHT;
		s_vram.cpuDirtyRectCount = 1;
		return;
	}

	s_vram.cpuDirtyRects[s_vram.cpuDirtyRectCount++] = *rect;
}

internal void NativeRenderer_MarkVRAMDirty(int x, int y, int w, int h)
{
	RECT16 rect;

	if (!NativeRenderer_ClipVRAMRect(&rect, x, y, w, h))
	{
		return;
	}

	NativeRenderer_AppendCpuDirtyRect(&rect);
}

internal void NativeRenderer_MarkGpuVRAMNewer(int x, int y, int w, int h)
{
	RECT16 rect;
	int tileX0, tileY0, tileX1, tileY1;

	if (!NativeRenderer_ClipVRAMRect(&rect, x, y, w, h))
	{
		return;
	}

	tileX0 = rect.x / NATIVE_VRAM_TILE_SIZE;
	tileY0 = rect.y / NATIVE_VRAM_TILE_SIZE;
	tileX1 = (rect.x + rect.w - 1) / NATIVE_VRAM_TILE_SIZE;
	tileY1 = (rect.y + rect.h - 1) / NATIVE_VRAM_TILE_SIZE;

	{
		int tileY;
		for (tileY = tileY0; tileY <= tileY1; tileY++)
		{
			int tileX;
			for (tileX = tileX0; tileX <= tileX1; tileX++)
			{
				const int tileIndex = tileY * NATIVE_VRAM_TILE_COLS + tileX;
				s_vram.gpuNewerTiles[tileIndex >> 5] |= 1u << (tileIndex & 31);
			}
		}
	}
}

void NativeRenderer_UpdateVRAM(void)
{
	s32 rectCount;
	s32 i;
	D3DLOCKED_RECT lock;
	RECT region;

	if (s_vram.cpuDirtyRectCount == 0)
	{
		return;
	}

	if (s_vram.texture == NULL)
	{
		s_vram.cpuDirtyRectCount = 0;
		return;
	}

	rectCount = s_vram.cpuDirtyRectCount;
	s_vram.cpuDirtyRectCount = 0;

	/* Coalesce this batch to its bounding box, then upload once. The GL
	 * backend issues one glTexSubImage2D per rect; the 360 equivalent is a
	 * single lock of the covered region. */
	region.left = s_vram.cpuDirtyRects[0].x;
	region.top = s_vram.cpuDirtyRects[0].y;
	region.right = s_vram.cpuDirtyRects[0].x + s_vram.cpuDirtyRects[0].w;
	region.bottom = s_vram.cpuDirtyRects[0].y + s_vram.cpuDirtyRects[0].h;

	for (i = 1; i < rectCount; i++)
	{
		if (s_vram.cpuDirtyRects[i].x < region.left)
		{
			region.left = s_vram.cpuDirtyRects[i].x;
		}
		if (s_vram.cpuDirtyRects[i].y < region.top)
		{
			region.top = s_vram.cpuDirtyRects[i].y;
		}
		if ((s_vram.cpuDirtyRects[i].x + s_vram.cpuDirtyRects[i].w) > region.right)
		{
			region.right = s_vram.cpuDirtyRects[i].x + s_vram.cpuDirtyRects[i].w;
		}
		if ((s_vram.cpuDirtyRects[i].y + s_vram.cpuDirtyRects[i].h) > region.bottom)
		{
			region.bottom = s_vram.cpuDirtyRects[i].y + s_vram.cpuDirtyRects[i].h;
		}
	}

	/* No render-target query/refcount traffic just to print a diagnostic.
	 * Count was reset above; report the batch we actually upload. */
	if (Platform_TraceEnabled(CTR_TRACE_VRAM))
		Platform_Log("[trace] UpdateVRAM: rects=%d bounds=%d,%d,%d,%d\n", (int)rectCount,
		             (int)region.left, (int)region.top, (int)region.right, (int)region.bottom);
	if (SUCCEEDED(IDirect3DTexture9_LockRect(s_vram.texture, 0, &lock, NULL, 0)))
	{
		int row;
		POINT destinationPoint;
		for (row = region.top; row < region.bottom; row++)
		{
			int column;
			u32 *dst = s_vramLinearScratch + row * VRAM_WIDTH;
			for (column = region.left; column < region.right; column++)
			{
				const u16 pixel = s_vram.cpuPixels[row * VRAM_WIDTH + column];
				dst[column] = 0xFF000000u | ((u32)(pixel & 0xFFu) << 16) |
				                            ((u32)(pixel >> 8) << 8);
			}
		}
		destinationPoint.x = region.left;
		destinationPoint.y = region.top;
		XGTileSurface(lock.pBits, VRAM_WIDTH, VRAM_HEIGHT, &destinationPoint,
		              s_vramLinearScratch, VRAM_WIDTH * sizeof(u32), &region, sizeof(u32));
		IDirect3DTexture9_UnlockRect(s_vram.texture, 0);
	}
	else
	{
		NATIVE_RENDERER_ERROR("%s\n", "VRAM update lock failed");
	}

	s_lastBoundTexture = (TextureID)-1;
}

/* The pack pass already resolves EDRAM into the linear VRAM texture. CPU
 * readers lock that resolved texture, so another EDRAM bind cannot overwrite
 * the image with unrelated draws that reused the same EDRAM base. */
internal void NativeRenderer_SyncGpuVRAMToCPU(int x, int y, int w, int h)
{
	RECT16 readRect;
	int tileX0, tileY0, tileX1, tileY1;
	b32 needsReadback = 0;
	D3DLOCKED_RECT lock;
	int tileY;

	Platform_Log("[trace] SyncGpuVRAMToCPU enter x=%d y=%d w=%d h=%d\n", x, y, w, h);
	if (!NativeRenderer_ClipVRAMRect(&readRect, x, y, w, h))
	{
		return;
	}

	tileX0 = readRect.x / NATIVE_VRAM_TILE_SIZE;
	tileY0 = readRect.y / NATIVE_VRAM_TILE_SIZE;
	tileX1 = (readRect.x + readRect.w - 1) / NATIVE_VRAM_TILE_SIZE;
	tileY1 = (readRect.y + readRect.h - 1) / NATIVE_VRAM_TILE_SIZE;

	for (tileY = tileY0; (tileY <= tileY1) && !needsReadback; tileY++)
	{
		int tileX;
		for (tileX = tileX0; tileX <= tileX1; tileX++)
		{
			const int tileIndex = tileY * NATIVE_VRAM_TILE_COLS + tileX;
			if ((s_vram.gpuNewerTiles[tileIndex >> 5] & (1u << (tileIndex & 31))) != 0)
			{
				needsReadback = 1;
				break;
			}
		}
	}

	if (!needsReadback)
	{
		return;
	}

	readRect.x = (s16)(tileX0 * NATIVE_VRAM_TILE_SIZE);
	readRect.y = (s16)(tileY0 * NATIVE_VRAM_TILE_SIZE);
	readRect.w = (s16)((tileX1 - tileX0 + 1) * NATIVE_VRAM_TILE_SIZE);
	readRect.h = (s16)((tileY1 - tileY0 + 1) * NATIVE_VRAM_TILE_SIZE);

	/* Pending CPU writes must reach the texture first, same ordering rule as GL. */
	Platform_Log("[trace] -> UpdateVRAM from SyncGpuVRAMToCPU\n");
	NativeRenderer_UpdateVRAM();

	{
		HRESULT lockResult = E_FAIL;

		Platform_Log("[trace] readback: rect=%d,%d,%d,%d\n", (int)readRect.x, (int)readRect.y, (int)readRect.w, (int)readRect.h);
		lockResult = IDirect3DTexture9_LockRect(s_vram.texture, 0, &lock, NULL, D3DLOCK_READONLY);
		if (SUCCEEDED(lockResult))
		{
			int row;
			XGUntileSurface(s_vramLinearScratch, VRAM_WIDTH * sizeof(u32), NULL,
			                lock.pBits, VRAM_WIDTH, VRAM_HEIGHT, NULL, sizeof(u32));
			for (row = 0; row < readRect.h; row++)
			{
				int column;
				const u32 *src = s_vramLinearScratch + (readRect.y + row) * VRAM_WIDTH;
				for (column = 0; column < readRect.w; column++)
				{
					const u32 packed = src[readRect.x + column];
					s_vram.cpuPixels[(readRect.y + row) * VRAM_WIDTH + readRect.x + column] =
					    (u16)(((packed >> 16) & 0xFFu) | (packed & 0x0000FF00u));
				}
			}
			IDirect3DTexture9_UnlockRect(s_vram.texture, 0);
			Platform_Log("[trace] readback: copy done\n");
		}
		else
		{
			Platform_LogError("[CTR Renderer] VRAM readback lock failed hr=%08x\n", (unsigned)lockResult);
		}

		if (SUCCEEDED(lockResult))
		{
			for (tileY = tileY0; tileY <= tileY1; tileY++)
			{
				int tileX;
				for (tileX = tileX0; tileX <= tileX1; tileX++)
				{
					const int tileIndex = tileY * NATIVE_VRAM_TILE_COLS + tileX;
					s_vram.gpuNewerTiles[tileIndex >> 5] &= ~(1u << (tileIndex & 31));
				}
			}
		}

	}
}

internal void NativeRenderer_ResolveVRAMRead(int x, int y, int w, int h)
{
	NativeRenderer_SyncGpuVRAMToCPU(x, y, w, h);
}

/* TEMPORARY diagnostic: sample the CPU-side VRAM mirror WITHOUT a GPU sync
 * (no readback), so "content never reached VRAM" can be told apart from
 * "content is in the mirror but the GPU texture upload lost it". */
void NativeRenderer_DebugDumpVRAMRaw(const char *tag)
{
	int x;
	int y;
	int nonzero = 0;
	int nonzeroTopLeft = 0;

    if (s_hdCaptureDiagnostics != 1) return;

	for (y = 0; y < VRAM_HEIGHT; y++)
	{
		for (x = 0; x < VRAM_WIDTH; x++)
		{
			if (s_vram.cpuPixels[(y * VRAM_WIDTH) + x] != 0)
			{
				nonzero++;
				if ((x < 512) && (y < 512))
				{
					nonzeroTopLeft++;
				}
			}
		}
	}

	Platform_Log("[dbg] VRAM %s cpu-mirror nonzero=%d/%d topleft512=%d/%d at0,0=%04x,%04x at200,10c=%04x,%04x\n", tag,
	             nonzero, VRAM_WIDTH * VRAM_HEIGHT, nonzeroTopLeft, 512 * 512,
	             (unsigned)s_vram.cpuPixels[0], (unsigned)s_vram.cpuPixels[1],
	             (unsigned)s_vram.cpuPixels[(0x10c * VRAM_WIDTH) + 0x200], (unsigned)s_vram.cpuPixels[(0x10c * VRAM_WIDTH) + 0x201]);
}

#define NATIVE_VRAM_MAP_COLS 48
#define NATIVE_VRAM_MAP_ROWS 14

/* TEMPORARY diagnostic: sample a VRAM rect (after a GPU->CPU sync) so a black
 * screen can be told apart from an empty/garbage VRAM texture. */
void NativeRenderer_DebugDumpVRAM(int x, int y, int w, int h, const char *tag)
{
	int row;
	int col;
	int nonzero = 0;
	int clippedW = w;
	int clippedH = h;

    if (s_hdCaptureDiagnostics != 1) return;

	if (x < 0) { x = 0; }
	if (y < 0) { y = 0; }
	if ((x + clippedW) > VRAM_WIDTH) { clippedW = VRAM_WIDTH - x; }
	if ((y + clippedH) > VRAM_HEIGHT) { clippedH = VRAM_HEIGHT - y; }
	if ((clippedW <= 0) || (clippedH <= 0))
	{
		return;
	}

	NativeRenderer_SyncGpuVRAMToCPU(x, y, clippedW, clippedH);

	for (row = y; row < (y + clippedH); row++)
	{
		for (col = x; col < (x + clippedW); col++)
		{
			if (s_vram.cpuPixels[(row * VRAM_WIDTH) + col] != 0)
			{
				nonzero++;
			}
		}
	}

	Platform_Log("[dbg] VRAM %s rect=%d,%d %dx%d nonzero=%d/%d words=%04x %04x %04x %04x %04x %04x\n", tag, x, y, clippedW, clippedH,
	             nonzero, clippedW * clippedH,
	             (unsigned)s_vram.cpuPixels[(y * VRAM_WIDTH) + x], (unsigned)s_vram.cpuPixels[(y * VRAM_WIDTH) + x + 1],
	             (unsigned)s_vram.cpuPixels[((y + 1) * VRAM_WIDTH) + x], (unsigned)s_vram.cpuPixels[((y + 1) * VRAM_WIDTH) + x + 1],
	             (unsigned)s_vram.cpuPixels[((y + 2) * VRAM_WIDTH) + x], (unsigned)s_vram.cpuPixels[((y + 2) * VRAM_WIDTH) + x + 1]);

	/* Histogram of the rect (top 6 values) + a coarse brightness map, so the
	 * log alone can show what the displayed image contains. */
	{
		u16 topVal[6];
		int topCnt[6];
		int i;
		int row;
		int col;

		for (i = 0; i < 6; i++)
		{
			topVal[i] = 0;
			topCnt[i] = 0;
		}

		for (row = y; row < (y + clippedH); row++)
		{
			for (col = x; col < (x + clippedW); col++)
			{
				const u16 v = s_vram.cpuPixels[(row * VRAM_WIDTH) + col];

				for (i = 0; i < 6; i++)
				{
					if (topVal[i] == v)
					{
						topCnt[i]++;
						break;
					}
				}
				if (i == 6)
				{
					for (i = 0; i < 6; i++)
					{
						if (topCnt[i] == 0)
						{
							topVal[i] = v;
							topCnt[i] = 1;
							break;
						}
					}
					if (i == 6)
					{
						int smallest = 0;
						for (i = 1; i < 6; i++)
						{
							if (topCnt[i] < topCnt[smallest])
							{
								smallest = i;
							}
						}
						if (topCnt[smallest] == 1)
						{
							topVal[smallest] = v;
						}
					}
				}
			}
		}

		Platform_Log("[dbg] VRAM %s hist: %04x:%d %04x:%d %04x:%d %04x:%d %04x:%d %04x:%d\n", tag,
		             (unsigned)topVal[0], topCnt[0], (unsigned)topVal[1], topCnt[1], (unsigned)topVal[2], topCnt[2],
		             (unsigned)topVal[3], topCnt[3], (unsigned)topVal[4], topCnt[4], (unsigned)topVal[5], topCnt[5]);
	}

	{
		char line[NATIVE_VRAM_MAP_COLS + 1];
		int row;
		int col;

		for (row = 0; row < NATIVE_VRAM_MAP_ROWS; row++)
		{
			for (col = 0; col < NATIVE_VRAM_MAP_COLS; col++)
			{
				const int sx = x + ((col * clippedW) / NATIVE_VRAM_MAP_COLS);
				const int sy = y + ((row * clippedH) / NATIVE_VRAM_MAP_ROWS);
				const u16 v = s_vram.cpuPixels[(sy * VRAM_WIDTH) + sx];
				const int r = v & 0x1f;
				const int g = (v >> 5) & 0x1f;
				const int b = (v >> 10) & 0x1f;
				int lum = ((r * 3) + (g * 6) + b) / 10;
				const char *ramp = " .:-=+*#%@";

				if (lum > 31)
				{
					lum = 31;
				}
				line[col] = ramp[(lum * 10) / 32];
			}
			line[NATIVE_VRAM_MAP_COLS] = 0;
			Platform_Log("[dbg] |%s|\n", line);
		}
	}
}

void NativeRenderer_CopyVRAM(u16 *src, int x, int y, int w, int h, int dst_x, int dst_y)
{
	int stride = w;
	int i;
	u16 *dst;

	if (!src)
	{
		NativeRenderer_ResolveVRAMRead(x, y, w, h);
		src = s_vram.cpuPixels;
		stride = VRAM_WIDTH;
	}

	src += x + y * stride;
	dst = s_vram.cpuPixels + dst_x + dst_y * VRAM_WIDTH;

	for (i = 0; i < h; i++)
	{
		memcpy(dst, src, w * sizeof(u16));
		dst += VRAM_WIDTH;
		src += stride;
	}

	NativeRenderer_MarkVRAMDirty(dst_x, dst_y, w, h);
}

void NativeRenderer_ReadVRAM(u16 *dst, int x, int y, int dst_w, int dst_h)
{
	u16 *src;
	int i;

	NativeRenderer_ResolveVRAMRead(x, y, dst_w, dst_h);

	src = s_vram.cpuPixels + x + VRAM_WIDTH * y;

	for (i = 0; i < dst_h; i++)
	{
		memcpy(dst, src, dst_w * sizeof(u16));
		dst += dst_w;
		src += VRAM_WIDTH;
	}
}

int NativeRenderer_GetVRAMStateSize(void)
{
	return (int)sizeof(s_vram.cpuPixels);
}

int NativeRenderer_CaptureVRAMState(void *dst, int dstSize)
{
	if ((dst == NULL) || (dstSize < (int)sizeof(s_vram.cpuPixels)))
	{
		return 0;
	}

	NativeRenderer_SyncGpuVRAMToCPU(0, 0, VRAM_WIDTH, VRAM_HEIGHT);
	memcpy(dst, s_vram.cpuPixels, sizeof(s_vram.cpuPixels));
	return 1;
}

int NativeRenderer_RestoreVRAMState(const void *src, int srcSize)
{
	if ((src == NULL) || (srcSize < (int)sizeof(s_vram.cpuPixels)))
	{
		return 0;
	}

	memcpy(s_vram.cpuPixels, src, sizeof(s_vram.cpuPixels));
	s_vram.cpuDirtyRectCount = 0;
	memset(s_vram.gpuNewerTiles, 0, sizeof(s_vram.gpuNewerTiles));
	NativeRenderer_MarkVRAMDirty(0, 0, VRAM_WIDTH, VRAM_HEIGHT);
	s_mainRenderTarget.width = 0;
	s_mainRenderTarget.height = 0;
	s_offscreenRenderTarget.width = 0;
	s_offscreenRenderTarget.height = 0;
	s_previousOffscreen.x = 0;
	s_previousOffscreen.y = 0;
	s_previousOffscreen.w = 0;
	s_previousOffscreen.h = 0;
	s_previousOffscreenState = 0;
	s_previousShader = (ShaderID)-1;
	s_lastBoundTexture = (TextureID)-1;
	return 1;
}

void NativeRenderer_ClearVRAM(int x, int y, int w, int h, u8 r, u8 g, u8 b)
{
	u16 *dst = s_vram.cpuPixels + x + y * VRAM_WIDTH;
	const u16 color = (u16)(((r >> 3) & 0x1f) | (((g >> 3) & 0x1f) << 5) | (((b >> 3) & 0x1f) << 10));
	int i;

	if (x + w > VRAM_WIDTH)
	{
		w = VRAM_WIDTH - x;
	}

	if (y + h > VRAM_HEIGHT)
	{
		h = VRAM_HEIGHT - y;
	}

	for (i = 0; i < h; i++)
	{
		u16 *tmp = dst;
		int j;
		for (j = 0; j < w; j++)
		{
			*tmp++ = color;
		}
		dst += VRAM_WIDTH;
	}

	NativeRenderer_MarkVRAMDirty(x, y, w, h);
}

internal u8 NativeRenderer_PSXColorComponent(u8 value)
{
	return (u8)((value >> 3) << 3);
}

void NativeRenderer_Clear(int x, int y, int w, int h, u8 r, u8 g, u8 b)
{
	int displayX, displayY, displayW, displayH;
	int clearRight, clearBottom, displayRight, displayBottom;
	int overlapX, overlapY, overlapRight, overlapBottom;
	D3DRECT rect;
	D3DCOLOR color;

	if ((w <= 0) || (h <= 0) || (s_device == NULL))
	{
		return;
	}

	displayX = activeDispEnv.disp.x;
	displayY = activeDispEnv.disp.y;
	displayW = activeDispEnv.disp.w;
	displayH = activeDispEnv.disp.h;

	if ((displayW <= 0) || (displayH <= 0))
	{
		displayX = activeDrawEnv.clip.x;
		displayY = activeDrawEnv.clip.y;
		displayW = activeDrawEnv.clip.w;
		displayH = activeDrawEnv.clip.h;
	}

	if ((displayW <= 0) || (displayH <= 0))
	{
		return;
	}

	clearRight = x + w;
	clearBottom = y + h;
	displayRight = displayX + displayW;
	displayBottom = displayY + displayH;

	overlapX = x > displayX ? x : displayX;
	overlapY = y > displayY ? y : displayY;
	overlapRight = clearRight < displayRight ? clearRight : displayRight;
	overlapBottom = clearBottom < displayBottom ? clearBottom : displayBottom;

	if ((overlapRight <= overlapX) || (overlapBottom <= overlapY))
	{
		return;
	}

	{
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
		rect.x1 = (LONG)(clearX * s_mainRenderTarget.width / displayW);
		rect.y1 = (LONG)(clearY * s_mainRenderTarget.height / displayH);
		rect.x2 = (LONG)(((clearX + clearW) * s_mainRenderTarget.width + displayW - 1) / displayW);
		rect.y2 = (LONG)(((clearY + clearH) * s_mainRenderTarget.height + displayH - 1) / displayH);
	}

	color = D3DCOLOR_ARGB(0, NativeRenderer_PSXColorComponent(r), NativeRenderer_PSXColorComponent(g), NativeRenderer_PSXColorComponent(b));

	IDirect3DDevice9_Clear(s_device, 1, &rect, D3DCLEAR_TARGET, color, 1.0f, 0);
}

void NativeRenderer_SaveVRAM(const char *outputFileName, int x, int y, int width, int height, int bReadFromFrameBuffer)
{
	FILE *fp;
	u8 tgaHeader[12] = {0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0};
	u8 header[6];
	int i;

	(void)bReadFromFrameBuffer;

	/* NOTE(session 8/audit): honor the requested rectangle; the old body wrote
	 * VRAM_WIDTH x VRAM_HEIGHT rows regardless of the header. */
	if (x < 0 || y < 0 || width <= 0 || height <= 0 ||
	    (x + width) > VRAM_WIDTH || (y + height) > VRAM_HEIGHT)
	{
		Platform_LogWarn("[CTR Native] SaveVRAM: rect %d,%d %dx%d out of range\n", x, y, width, height);
		return;
	}

	NativeRenderer_SyncGpuVRAMToCPU(0, 0, VRAM_WIDTH, VRAM_HEIGHT);

	fp = fopen(outputFileName, "wb");
	if (fp == NULL)
	{
		Platform_LogWarn("[CTR Native] SaveVRAM: cannot open %s\n", outputFileName);
		return;
	}

	header[0] = (u8)(width % 256);
	header[1] = (u8)(width / 256);
	header[2] = (u8)(height % 256);
	header[3] = (u8)(height / 256);
	header[4] = 16;
	header[5] = 0;

	fwrite(tgaHeader, sizeof(u8), 12, fp);
	fwrite(header, sizeof(u8), 6, fp);

	for (i = 0; i < height; i++)
	{
		fwrite(s_vram.cpuPixels + VRAM_WIDTH * (VRAM_HEIGHT - (y + i) - 1) + x, sizeof(u16), width, fp);
	}

	fclose(fp);
}

/* ---------------------------------------------------------------------------------------
 * Scene flow
 * --------------------------------------------------------------------------------------- */

void NativeRenderer_BeginScene(void)
{
	s_lastBoundTexture = (TextureID)-1;
	Platform_Log("[trace] BeginScene enter\n");

	NativeRenderer_UpdatePresentationViewport();
	NativeRenderer_ClearPresentationBars();
	Platform_Log("[trace] BeginScene after viewport+bars\n");

	NativeRenderer_BindMainRenderTarget();
    s_mainResolved = 0;
	Platform_Log("[trace] BeginScene after bind main RT\n");

	Platform_Log("[trace] -> UpdateVRAM from BeginScene\n");
	NativeRenderer_UpdateVRAM();
	Platform_Log("[trace] BeginScene after UpdateVRAM\n");
	if (!activeDrawEnv.isbg)
	{
		NativeRenderer_LoadRenderTargetFromVRAM(&s_mainRenderTarget, activeDispEnv.disp.x, activeDispEnv.disp.y);
	}
	else
	{
		/* Like the GL backend, reset primitive overlap masks every frame even
		 * when the draw environment supplies its own background clear. */
		NativeRenderer_SetViewPort(0, 0, s_mainRenderTarget.width, s_mainRenderTarget.height);
		NativeRenderer_SetScissorState(0);
		IDirect3DDevice9_Clear(s_device, 0, NULL, D3DCLEAR_STENCIL, 0, 1.0f, 0);
	}
	Platform_Log("[trace] BeginScene after load RT from VRAM\n");

	NativeRenderer_SetViewPort(0, 0, s_mainRenderTarget.width, s_mainRenderTarget.height);

	if (g_dbg_wireframeMode)
	{
		NativeRenderer_SetWireframe(1);
		IDirect3DDevice9_Clear(s_device, 0, NULL, D3DCLEAR_TARGET, D3DCOLOR_ARGB(255, 26, 26, 26), 1.0f, 0);
	}
}

internal void NativeRenderer_TraceLateIntro(const char *step)
{
	if (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722)
		Platform_Log("[probe] hb present f=%d step=%s\n", (int)sdata->frameCounter, step);
}

void NativeRenderer_EndGpuFrame(void)
{
	NativeRenderer_TraceLateIntro("end-gpu");
}

void NativeRenderer_FinishGpuMeasurements(void)
{
}

void NativeRenderer_EndScene(void)
{
	NativeRenderer_TraceLateIntro("end-scene-enter");
	if (s_previousOffscreenState)
	{
		NativeRenderer_SetOffscreenState(&s_previousOffscreen, 0);
	}

	if (g_dbg_wireframeMode)
	{
		NativeRenderer_SetWireframe(0);
	}
	NativeRenderer_TraceLateIntro("end-scene-exit");
}

internal void NativeRenderer_SetWireframe(int enable)
{
	if (s_device != NULL)
	{
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_FILLMODE, enable ? D3DFILL_WIREFRAME : D3DFILL_SOLID);
	}
}

internal void NativeRenderer_Ortho2D(float left, float right, float bottom, float top, float znear, float zfar)
{
	float a = 2.0f / (right - left);
	float b = 2.0f / (top - bottom);
	float c = 2.0f / (znear - zfar);

	float x = (left + right) / (left - right);
	float y = (bottom + top) / (bottom - top);
	float z = (znear + zfar) / (znear - zfar);

	float ortho[16] = {a, 0, 0, 0, 0, b, 0, 0, 0, 0, c, 0, x, y, z, 1};

	if ((s_device != NULL) && (s_previousShader != (ShaderID)-1))
	{
		IDirect3DDevice9_SetVertexShaderConstantF(s_device, X360_PSX_VS_PROJECTION_C0, ortho, 4);
	}
}

void NativeRenderer_SetProjection(const RECT16 *drawRect, const DISPENV *displayEnv, int offscreen)
{
	if (offscreen)
	{
		/* bottom/top swapped vs the GL call: see the y-flip note at the top. */
		NativeRenderer_Ortho2D(0, drawRect->w, 0, drawRect->h, -1.0f, 1.0f);
		return;
	}

	{
		const int displayW = displayEnv->disp.w > 0 ? displayEnv->disp.w : 1;
		const int displayH = displayEnv->disp.h > 0 ? displayEnv->disp.h : 1;
		NativeRenderer_Ortho2D(0, displayW, 0, displayH, -1.0f, 1.0f);
	}
}

void NativeRenderer_SetupClipMode(const RECT16 *rect, const DISPENV *displayEnv, int enable)
{
	if ((displayEnv->disp.w <= 0) || (displayEnv->disp.h <= 0))
	{
		NativeRenderer_SetScissorState(0);
		return;
	}

	if ((rect->w <= 0) || (rect->h <= 0))
	{
		RECT zeroRect;
		NativeRenderer_SetScissorState(enable != 0);
		if (enable && (s_device != NULL))
		{
			zeroRect.left = 0;
			zeroRect.top = 0;
			zeroRect.right = 0;
			zeroRect.bottom = 0;
			IDirect3DDevice9_SetScissorRect(s_device, &zeroRect);
		}
		return;
	}

	{
		const bool scissorOn = enable && (displayEnv->isinter || (rect->x - displayEnv->disp.x > 0 || rect->y - displayEnv->disp.y > 0 ||
		                                                         rect->w < displayEnv->disp.w || rect->h < displayEnv->disp.h));

		NativeRenderer_SetScissorState(scissorOn);

		if (!scissorOn)
		{
			return;
		}
	}

	{
		const float psxScreenWInv = 1.0f / (float)displayEnv->disp.w;
		const float psxScreenHInv = 1.0f / (float)displayEnv->disp.h;

		float clipRectX = (float)(rect->x - displayEnv->disp.x) * psxScreenWInv;
		float clipRectY = (float)(rect->y - displayEnv->disp.y) * psxScreenHInv;
		float clipRectW = (float)(rect->w) * psxScreenWInv;
		float clipRectH = (float)(rect->h) * psxScreenHInv;

		const float viewportW = (float)s_mainRenderTarget.width;
		const float viewportH = (float)s_mainRenderTarget.height;
		float crx, cry, crw, crh;
		RECT scissorRect;

		clipRectX -= 0.5f;
		clipRectX *= s_uiPass ? 0.75f : 1.0f;
		clipRectW *= s_uiPass ? 0.75f : 1.0f;
		clipRectX += 0.5f;

		crx = clipRectX * viewportW;
		cry = clipRectY * viewportH;
		crw = clipRectW * viewportW;
		crh = clipRectH * viewportH;

		scissorRect.left = (LONG)crx;
		scissorRect.top = (LONG)cry;
		scissorRect.right = (LONG)(crx + crw);
		scissorRect.bottom = (LONG)(cry + crh);

		if (s_device != NULL)
		{
			IDirect3DDevice9_SetScissorRect(s_device, &scissorRect);
		}
	}
}

internal void NativeRenderer_SetScissorState(int enable)
{
	if (s_previousScissorState == enable)
	{
		return;
	}

	s_previousScissorState = enable;

	if (s_device != NULL)
	{
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_SCISSORTESTENABLE, enable ? TRUE : FALSE);
	}
}

internal void NativeRenderer_EnableDepth(int enable)
{
	if (s_previousDepthMode == enable)
	{
		return;
	}

	s_previousDepthMode = enable;

	if (s_device != NULL)
	{
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_ZENABLE, FALSE);
	}
}

void NativeRenderer_SetStencilMode(int drawPrim)
{
	if (s_previousStencilMode == drawPrim)
	{
		return;
	}

	s_previousStencilMode = drawPrim;

	if (s_device == NULL)
	{
		return;
	}

	if (drawPrim)
	{
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILFUNC, D3DCMP_ALWAYS);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILREF, 1);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILMASK, 0x10);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILWRITEMASK, 0xFF);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILFAIL, D3DSTENCILOP_REPLACE);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILZFAIL, D3DSTENCILOP_REPLACE);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILPASS, D3DSTENCILOP_REPLACE);
	}
	else
	{
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILFUNC, D3DCMP_NOTEQUAL);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILREF, 1);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILMASK, 0xFF);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILWRITEMASK, 0xFF);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILFAIL, D3DSTENCILOP_REPLACE);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILZFAIL, D3DSTENCILOP_KEEP);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILPASS, D3DSTENCILOP_KEEP);
	}
}

void NativeRenderer_SetBlendMode(BlendMode blendMode)
{
	if (s_previousBlendMode == blendMode)
	{
		return;
	}

	if (s_device == NULL)
	{
		s_previousBlendMode = blendMode;
		return;
	}

	if (blendMode != BM_NONE)
	{
		if (s_previousBlendMode == BM_NONE)
		{
			/* GL sets blendColor(0.25,0.25,0.25,0.5) on this transition. */
			IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDFACTOR, D3DCOLOR_ARGB(128, 64, 64, 64));
			IDirect3DDevice9_SetRenderState(s_device, D3DRS_ALPHABLENDENABLE, TRUE);
		}

		NativeRenderer_EnableDepth(0);
	}

	switch (blendMode)
	{
	case BM_NONE:
		if (s_previousBlendMode != BM_NONE)
		{
			IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDFACTOR, D3DCOLOR_ARGB(255, 255, 255, 255));
			IDirect3DDevice9_SetRenderState(s_device, D3DRS_ALPHABLENDENABLE, FALSE);
		}

		NativeRenderer_EnableDepth(1);
		break;
	case BM_AVERAGE:
		/* D3D uses BLENDFACTOR RGB; GL used CONSTANT_ALPHA = 0.5. */
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDFACTOR, D3DCOLOR_ARGB(128, 128, 128, 128));
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOP, D3DBLENDOP_ADD);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOPALPHA, D3DBLENDOP_ADD);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_SRCBLEND, D3DBLEND_BLENDFACTOR);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_DESTBLEND, D3DBLEND_INVBLENDFACTOR);
		break;
	case BM_ADD:
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOP, D3DBLENDOP_ADD);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOPALPHA, D3DBLENDOP_ADD);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_SRCBLEND, D3DBLEND_ONE);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_DESTBLEND, D3DBLEND_ONE);
		break;
	case BM_SUBTRACT:
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOP, D3DBLENDOP_REVSUBTRACT);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOPALPHA, D3DBLENDOP_ADD);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_SRCBLEND, D3DBLEND_ONE);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_DESTBLEND, D3DBLEND_ONE);
		break;
	case BM_ADD_QUATER_SOURCE:
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDFACTOR, D3DCOLOR_ARGB(128, 64, 64, 64));
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOP, D3DBLENDOP_ADD);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_BLENDOPALPHA, D3DBLENDOP_ADD);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_SRCBLEND, D3DBLEND_BLENDFACTOR);
		IDirect3DDevice9_SetRenderState(s_device, D3DRS_DESTBLEND, D3DBLEND_ONE);
		break;
	}

	s_previousBlendMode = blendMode;
}

/* ---------------------------------------------------------------------------------------
 * Draw path
 * --------------------------------------------------------------------------------------- */

internal void NativeRenderer_SetShader(const ShaderID shader)
{
	s_previousShader = shader;
}

internal void NativeRenderer_UploadPSXFlags(void)
{
	float flags[4];

	if (s_device == NULL)
	{
		return;
	}

	flags[0] = (g_cfg_bilinearFiltering != 0 && !s_uiPass && !s_previousOffscreenState) ? 1.0f : 0.0f;
	flags[1] = 0.0f; /* psxSemiTransPass, set by the caller below */
	flags[2] = 0.0f; /* psxDrawMaskSet */
	flags[3] = 0.0f; /* psxTextureOutputStp */
	IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PSX_PS_BILINEAR_C0, &flags[0], 1);
}

internal void NativeRenderer_UploadDitherTable(void)
{
	if (s_device != NULL)
	{
		IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PSX_PS_DITHER_C4, s_ditherTable, 4);
	}
}

void NativeRenderer_SetTexture(TextureID texture, TexFormat texFormat)
{
	D3DTexture *d3dTexture;
	static int textureProbeCount = 0;
	s_debugTextureFormat = texFormat;
	if ((int)sdata->frameCounter >= 60 && (int)sdata->frameCounter <= 61 && textureProbeCount < 20)
	{
		textureProbeCount++;
		Platform_Log("[probe] texture f=%d format=%d id=%08x vram=%08x\n",
		             (int)sdata->frameCounter, (int)texFormat, (unsigned)texture,
		             (unsigned)NativeRenderer_GetVRAMTexture());
	}

	switch (texFormat)
	{
	case TF_4_BIT:
		NativeRenderer_SetShader((ShaderID)(DWORD_PTR)s_gteShader4.shader);
		if ((s_device != NULL) && (s_gteShader4.shader != NULL))
		{
			IDirect3DDevice9_SetPixelShader(s_device, s_gteShader4.shader);
		}
		break;
	case TF_8_BIT:
		NativeRenderer_SetShader((ShaderID)(DWORD_PTR)s_gteShader8.shader);
		if ((s_device != NULL) && (s_gteShader8.shader != NULL))
		{
			IDirect3DDevice9_SetPixelShader(s_device, s_gteShader8.shader);
		}
		break;
	case TF_16_BIT:
		NativeRenderer_SetShader((ShaderID)(DWORD_PTR)s_gteShader16.shader);
		if ((s_device != NULL) && (s_gteShader16.shader != NULL))
		{
			IDirect3DDevice9_SetPixelShader(s_device, s_gteShader16.shader);
		}
		break;
	case TF_32_BIT_RGBA:
		NativeRenderer_SetShader((ShaderID)(DWORD_PTR)s_gteShader32Rgba.shader);
		if ((s_device != NULL) && (s_gteShader32Rgba.shader != NULL))
		{
			IDirect3DDevice9_SetPixelShader(s_device, s_gteShader32Rgba.shader);
		}
		break;
	}

	if (g_dbg_texturelessMode)
	{
		texture = s_whiteTextureId;
	}

	if (s_device != NULL)
	{
		float bilinear[4] = {(g_cfg_bilinearFiltering != 0 && !s_uiPass && !s_previousOffscreenState) ? 1.0f : 0.0f, 0.0f, 0.0f, 0.0f};
		IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PSX_PS_BILINEAR_C0, bilinear, 1);
	}
	NativeRenderer_SetPSXTextureSemiTransPass(0);

	if (s_lastBoundTexture == texture)
	{
		return;
	}

	d3dTexture = NativeRenderer_TextureFromId(texture);
	if (s_device != NULL)
	{
		IDirect3DDevice9_SetTexture(s_device, 0, (D3DBaseTexture *)d3dTexture);
	}

	s_lastBoundTexture = texture;
}

void NativeRenderer_SetOverrideTextureSize(int width, int height)
{
	float vec[4];

	if (s_device == NULL)
	{
		return;
	}

	vec[0] = 1.0f / (float)width;
	vec[1] = 1.0f / (float)height;
	vec[2] = 0.0f;
	vec[3] = 0.0f;
	IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PSX_PS_TEXELSIZE_C16, vec, 1);
}

void NativeRenderer_SetPSXTextureSemiTransPass(int pass)
{
	if (s_device != NULL)
	{
		float value[4] = {(float)pass, 0.0f, 0.0f, 0.0f};
		IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PSX_PS_SEMITRANS_C1, value, 1);
	}
}

void NativeRenderer_SetPSXTextureOutputSTP(int enabled)
{
	if (s_device != NULL)
	{
		float value[4] = {(float)enabled, 0.0f, 0.0f, 0.0f};
		IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PSX_PS_OUTPUTSTP_C3, value, 1);
	}
}

void NativeRenderer_SetPSXDrawMaskSet(int maskSet)
{
	if (s_device != NULL)
	{
		float value[4] = {(float)maskSet, 0.0f, 0.0f, 0.0f};
		IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PSX_PS_MASKSET_C2, value, 1);
	}
}

internal void NativeRenderer_DestroyTexture(TextureID texture)
{
	if (texture == (TextureID)-1)
	{
		return;
	}
}

void NativeRenderer_UpdateVertexBuffer(const GrVertex *vertices, int num_vertices)
{
	X360Vertex *out;
	s32 bufferIndex;
	static int s_vbTrace = 0;
	if (s_hdCaptureDiagnostics == 1 && (int)sdata->frameCounter == 60)
	{
		static int vertexProbeDone = 0;
		if (!vertexProbeDone)
		{
			int probeIndex;
			FILE *vertexDump = fopen("cache:\\ctr360_vertices60.bin", "wb");
			vertexProbeDone = 1;
			if (vertexDump != NULL)
			{
				fwrite(vertices, sizeof(GrVertex), num_vertices, vertexDump);
				fclose(vertexDump);
			}
			Platform_Log("[probe] vertices f=60 count=%d\n", num_vertices);
			for (probeIndex = 0; probeIndex < num_vertices && probeIndex < 18; probeIndex++)
			{
				const GrVertex *v = &vertices[probeIndex];
				Platform_Log("[probe] vertex %d xy=%d,%d page=%d clut=%d uv=%u,%u rgb=%u,%u,%u\n",
				             probeIndex, (int)v->x, (int)v->y, (int)v->page, (int)v->clut,
				             (unsigned)v->u, (unsigned)v->v,
				             (unsigned)v->r, (unsigned)v->g, (unsigned)v->b);
			}
		}
	}

	if (s_device == NULL)
	{
		return;
	}

	if ((u32)num_vertices >= MAX_VERTEX_BUFFER_SIZE)
	{
		NATIVE_RENDERER_ERROR("%s\n", "MAX_VERTEX_BUFFER_SIZE reached, expect rendering errors");
		num_vertices = MAX_VERTEX_BUFFER_SIZE;
	}

	bufferIndex = s_curVertexBuffer;
	s_curVertexBuffer = (s_curVertexBuffer + 1) % MAX_NUM_VERTEX_BUFFERS;
	s_boundVertexBuffer = bufferIndex;

	if (s_vbTrace < 12)
	{
		s_vbTrace++;
		Platform_Log("[trace] vb#%d verts=%d bytes=%d buffer=%d\n", s_vbTrace, num_vertices, (int)(num_vertices * (int)sizeof(X360Vertex)), (int)bufferIndex);
	}

	if (num_vertices <= 0)
	{
		/* NOTE(ctr360): D3D9 SizeToLock 0 means "lock the whole buffer"; for an
		 * empty upload that lock is pure overhead and it stalled the d3d9
		 * resource path in Xenia at the first post-TIM-lock call. Skip it. */
		return;
	}

	/* IDirect3DVertexBuffer9_Lock expands the packed GrVertex into the float
	 * vertex format the shaders consume. GL fed the packed struct straight to
	 * the vertex fetcher with per-attribute types; the 360 path declares four
	 * FLOAT4 attributes, so the expansion happens here, once per upload, and
	 * keeps every value bit-identical to what GLSL saw. */
	if (s_vbTrace <= 12) { Platform_Log("[trace] vb: locking bytes=%d\n", (int)(num_vertices * (int)sizeof(X360Vertex))); }
    /* These buffers are reused from offset zero. Let XDK synchronize a busy
     * resource; NOOVERWRITE would promise not to overwrite in-flight data. */
	out = (X360Vertex *)D3DVertexBuffer_Lock(s_vertexBuffer[bufferIndex], 0, num_vertices * sizeof(X360Vertex), 0);
	if (s_vbTrace <= 12) { Platform_Log("[trace] vb: lock returned %p\n", (void *)out); }
	if (out == NULL)
	{
		NATIVE_RENDERER_ERROR("%s\n", "vertex buffer lock failed");
		return;
	}

	{
		int i;
		for (i = 0; i < num_vertices; i++)
		{
			const GrVertex *v = &vertices[i];
			out[i].x = (f32)v->x;
			out[i].y = (f32)v->y;
			out[i].page = (f32)v->page;
			out[i].clut = (f32)v->clut;
			out[i].u = (f32)v->u;
			out[i].v = (f32)v->v;
			out[i].bright = (f32)v->bright;
			out[i].dither = (f32)v->dither;
			out[i].r = (f32)v->r / 255.0f;
			out[i].g = (f32)v->g / 255.0f;
			out[i].b = (f32)v->b / 255.0f;
			out[i].a = (f32)v->a / 255.0f;
			out[i].tcx = (f32)v->tcx;
			out[i].tcy = (f32)v->tcy;
			out[i].p0 = (f32)v->_p0;
			out[i].p1 = (f32)v->_p1;
		}
	}

	IDirect3DVertexBuffer9_Unlock(s_vertexBuffer[bufferIndex]);
	if (s_vbTrace <= 12) { Platform_Log("[trace] vb: unlocked\n"); }
}

void NativeRenderer_DrawTriangles(int start_vertex, int triangles)
{
	static int s_drawLogCount = 0;
	if (s_hdCaptureDiagnostics == 1 && (int)sdata->frameCounter == 60)
	{
		Platform_Log("[probe] draw f=60 start=%d triangles=%d fmt=%d\n",
		             start_vertex, triangles, (int)s_debugTextureFormat);
	}

	if (s_drawLogCount < 24)
	{
		s_drawLogCount++;
		Platform_Log("[trace] DrawTriangles start=%d count=%d\n", start_vertex, triangles);
	}

	if ((s_device == NULL) || (s_boundVertexBuffer < 0))
	{
		return;
	}

	IDirect3DDevice9_SetVertexShader(s_device, s_gteVertexShader);
	IDirect3DDevice9_SetVertexDeclaration(s_device, s_gteVertexDecl);
	IDirect3DDevice9_SetStreamSource(s_device, 0, s_vertexBuffer[s_boundVertexBuffer], 0, sizeof(X360Vertex));

    {
        float drawScale[4] = {s_uiPass ? 0.75f : 1.0f, (float)activeDispEnv.disp.w * 0.5f, s_previousOffscreenState ? 1.0f : 0.0f, 0.0f};
        IDirect3DDevice9_SetVertexShaderConstantF(s_device, 18, drawScale, 1);
    }
	NativeRenderer_UploadDitherTable();

	IDirect3DDevice9_DrawPrimitive(s_device, D3DPT_TRIANGLELIST, (UINT)start_vertex, (UINT)triangles);
}

void NativeRenderer_PushDebugLabel(const char *label)
{
	(void)label;
}

void NativeRenderer_PopDebugLabel(void)
{
}

/* ---------------------------------------------------------------------------------------
 * Offscreen / VRAM bridges
 * --------------------------------------------------------------------------------------- */

internal void NativeRenderer_DrawFullscreenQuad(float posFlipY)
{
	const float quad[12] = {-1.f, -1.f, -1.f, 1.f, 1.f, 1.f, -1.f, -1.f, 1.f, 1.f, 1.f, -1.f};
	float flipConst[4];

	flipConst[0] = posFlipY;
	flipConst[1] = 0.0f;
	flipConst[2] = 0.0f;
	flipConst[3] = 0.0f;

	IDirect3DDevice9_SetVertexShaderConstantF(s_device, X360_QUAD_VS_FLIP_C16, flipConst, 1);
	IDirect3DDevice9_SetVertexDeclaration(s_device, s_quadVertexDecl);
	Platform_Log("[trace] dfq: flip const set\n");
	IDirect3DDevice9_DrawPrimitiveUP(s_device, D3DPT_TRIANGLELIST, 2, quad, 2 * sizeof(float));
	Platform_Log("[trace] dfq: primitive up done\n");
}

internal void NativeRenderer_DrawVRAMRegion(int x, int y, int width, int height)
{
	float sourceRect[4];
	const float flip = 1.0f; /* top VRAM row maps to top render-target row */

	if (s_device == NULL)
	{
		return;
	}

	sourceRect[0] = (float)x;
	sourceRect[1] = (float)y;
	sourceRect[2] = (float)width;
	sourceRect[3] = (float)height;

	IDirect3DDevice9_SetVertexShader(s_device, s_presentVertexShader);
	IDirect3DDevice9_SetPixelShader(s_device, s_presentPixelShader);
	IDirect3DDevice9_SetTexture(s_device, 0, (D3DBaseTexture *)s_vram.texture);
	IDirect3DDevice9_SetVertexShaderConstantF(s_device, X360_PRESENT_VS_RECT_C17, sourceRect, 1);
	NativeRenderer_DrawFullscreenQuad(flip);

	s_previousShader = (ShaderID)-1;
	s_lastBoundTexture = (s_vram.texture != NULL) ? NativeRenderer_IdFromTexture(s_vram.texture) : (TextureID)-1;
}

internal void NativeRenderer_LoadRenderTargetFromVRAM(struct X360RenderTarget *target, int x, int y)
{
	const ShaderID previousShader = s_previousShader;
	const BlendMode previousBlendMode = s_previousBlendMode;
	const int previousScissorState = s_previousScissorState;

	Platform_Log("[trace] LoadRenderTargetFromVRAM enter\n");

	Platform_Log("[trace] -> UpdateVRAM from LoadRenderTargetFromVRAM\n");
	NativeRenderer_UpdateVRAM();
	NativeRenderer_SetRenderTarget(target);
	NativeRenderer_SetScissorState(0);
	NativeRenderer_SetViewPort(0, 0, target->width, target->height);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILENABLE, FALSE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_ALPHABLENDENABLE, FALSE);
	NativeRenderer_DrawVRAMRegion(x, y,
        target == &s_mainRenderTarget ? activeDispEnv.disp.w : target->width,
        target == &s_mainRenderTarget ? activeDispEnv.disp.h : target->height);
	if (s_device != NULL)
	{
		IDirect3DDevice9_Clear(s_device, 0, NULL, D3DCLEAR_STENCIL, 0, 1.0f, 0);
	}

	if (s_boundVertexBuffer >= 0)
	{
		IDirect3DDevice9_SetStreamSource(s_device, 0, s_vertexBuffer[s_boundVertexBuffer], 0, sizeof(X360Vertex));
	}
	s_previousShader = previousShader;
	s_lastBoundTexture = (TextureID)-1;
	s_previousBlendMode = BM_NONE;
	s_previousScissorState = 0;
	NativeRenderer_SetBlendMode(previousBlendMode);
	NativeRenderer_SetScissorState(previousScissorState);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILENABLE, TRUE);
}

internal void NativeRenderer_GpuPackTextureToVRAM(D3DTexture *sourceTexture, int x, int y, int w, int h, b32 flipY)
{
	const ShaderID previousShader = s_previousShader;
	const BlendMode previousBlendMode = s_previousBlendMode;
	const int previousScissorState = s_previousScissorState;
	float flipYVector[4] = {flipY ? 1.0f : 0.0f, 0.f, 0.f, 0.f};
	float diagnosticSolid[4] = {0.f, 0.f, 0.f, 0.f};

	if (s_device == NULL)
	{
		return;
	}

	Platform_Log("[trace] -> UpdateVRAM from GpuPackTextureToVRAM\n");
	NativeRenderer_UpdateVRAM();

	Platform_Log("[trace] pack: before bind VRAM as RT\n");
	IDirect3DDevice9_SetRenderTarget(s_device, 0, s_vram.surface);
	IDirect3DDevice9_SetDepthStencilSurface(s_device, NULL);
	s_boundTarget = NULL;
	Platform_Log("[trace] pack: VRAM bound as RT\n");

	NativeRenderer_SetScissorState(0);
	/* The bridge needs an unconditionally disabled scissor even when the cache
	 * was desynchronized by another D3D pass. */
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_SCISSORTESTENABLE, FALSE);
	/* The pack pass has no depth/stencil attachment and must replace the RG8
	 * destination bytes, regardless of the last game primitive's blend mode. */
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILENABLE, FALSE);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_ALPHABLENDENABLE, FALSE);
	/* The EDRAM target is shared with the main framebuffer. Seed all VRAM
	 * pixels from its main-memory texture before writing this subrectangle. */
	NativeRenderer_SetViewPort(0, 0, VRAM_WIDTH, VRAM_HEIGHT);
	IDirect3DDevice9_SetVertexShader(s_device, s_packVertexShader);
	IDirect3DDevice9_SetPixelShader(s_device, s_vramCopyPixelShader);
	IDirect3DDevice9_SetTexture(s_device, 0, (D3DBaseTexture *)s_vram.texture);
	NativeRenderer_DrawFullscreenQuad(-1.0f);
	Platform_Log("[trace] pack: VRAM seeded from texture\n");
	Platform_Log("[trace] pack: before SetViewPort\n");
	NativeRenderer_SetViewPort(x, y, w, h);
	Platform_Log("[trace] pack: viewport set\n");

	IDirect3DDevice9_SetVertexShader(s_device, s_packVertexShader);
	IDirect3DDevice9_SetPixelShader(s_device, s_packPixelShader);
	IDirect3DDevice9_SetTexture(s_device, 0, (D3DBaseTexture *)sourceTexture);
	IDirect3DDevice9_SetPixelShaderConstantF(s_device, X360_PACK_PS_FLIPY_C0, flipYVector, 1);
	IDirect3DDevice9_SetPixelShaderConstantF(s_device, 1, diagnosticSolid, 1);
	Platform_Log("[trace] pack: before pack draw\n");
	NativeRenderer_DrawFullscreenQuad(-1.0f); /* texture destination */
	Platform_Log("[trace] pack: after pack draw\n");
	IDirect3DDevice9_Resolve(s_device, D3DRESOLVE_RENDERTARGET0, NULL,
	                         (D3DBaseTexture *)s_vram.texture, NULL,
	                         0, 0, NULL, 0.0f, 0, NULL);
	Platform_Log("[trace] pack: VRAM resolved to texture\n");

	if (s_previousOffscreenState)
	{
		IDirect3DDevice9_SetRenderTarget(s_device, 0, s_offscreenRenderTarget.surface);
		IDirect3DDevice9_SetDepthStencilSurface(s_device, s_offscreenRenderTarget.depthStencil);
		s_boundTarget = &s_offscreenRenderTarget;
		NativeRenderer_SetViewPort(0, 0, s_offscreenRenderTarget.width, s_offscreenRenderTarget.height);
	}
	else
	{
	Platform_Log("[trace] pack: before restore main RT\n");
		NativeRenderer_SetRenderTarget(&s_mainRenderTarget);
		NativeRenderer_SetViewPort(0, 0, s_mainRenderTarget.width, s_mainRenderTarget.height);
	Platform_Log("[trace] pack: main RT restored (else branch)\n");
	}

	s_previousShader = previousShader;
	s_lastBoundTexture = (TextureID)-1;
	s_previousBlendMode = BM_NONE;
	s_previousScissorState = 0;
	NativeRenderer_SetBlendMode(previousBlendMode);
	NativeRenderer_SetScissorState(previousScissorState);
	IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILENABLE, TRUE);
	NativeRenderer_MarkGpuVRAMNewer(x, y, w, h);
}

/* Read the already resolved tiled target. Xbox Resolve does not support the
 * linear destination used by the old hash probe. Write ordinary 24-bit TGA
 * pixels, rather than exposing packed PSX texture words as an image. */
internal void NativeRenderer_DebugHashMainTarget(int frame)
{
	D3DLOCKED_RECT lock;
	HRESULT hr;
	u32 hash = 2166136261u;
	u32 first = 0;
	int x;
	int y;
	int nonzero = 0;
	FILE *file;
	char path[96];
	u8 header[18] = {0};
	const int width = s_mainRenderTarget.width;
	const int height = s_mainRenderTarget.height;

	if (s_mainRenderTarget.texture == NULL || width <= 0 || height <= 0)
	{
		return;
	}
	hr = IDirect3DTexture9_LockRect(s_mainRenderTarget.texture, 0, &lock, NULL, D3DLOCK_READONLY);
	if (SUCCEEDED(hr))
	{
		XGUntileSurface(s_vramLinearScratch, width * sizeof(u32), NULL,
		                lock.pBits, width, height, NULL, sizeof(u32));
		sprintf(path, "cache:\\ctr360_main_f%04d.tga", frame);
		file = fopen(path, "wb");
		header[2] = 2;
		header[12] = (u8)width;
		header[13] = (u8)(width >> 8);
		header[14] = (u8)height;
		header[15] = (u8)(height >> 8);
		header[16] = 24;
		header[17] = 0x20;
		if (file != NULL) fwrite(header, 1, sizeof(header), file);
		for (y = 0; y < height; y++)
		{
			const u32 *row = s_vramLinearScratch + y * width;
			for (x = 0; x < width; x++)
			{
				u32 value = row[x];
				u8 bgr[3];
				bgr[0] = (u8)value;
				bgr[1] = (u8)(value >> 8);
				bgr[2] = (u8)(value >> 16);
				if (file != NULL) fwrite(bgr, 1, 3, file);
				if (x == 0 && y == 0) first = value;
				if (value != 0) nonzero++;
				hash = (hash ^ value) * 16777619u;
			}
		}
		if (file != NULL) fclose(file);
		IDirect3DTexture9_UnlockRect(s_mainRenderTarget.texture, 0);
		Platform_Log("[diag] mainRT f=%d size=%dx%d hash=%08x nonzero=%d first=%08x\n",
		             frame, width, height, (unsigned)hash, nonzero, (unsigned)first);
	}
	if (FAILED(hr))
	{
		Platform_LogError("[diag] mainRT f=%d readback failed hr=%08x\n", frame, (unsigned)hr);
	}
}

void NativeRenderer_StoreFrameBuffer(int x, int y, int w, int h)
{
	static int lastHashFrame = -1;
	int frame = (int)sdata->frameCounter;
	NativeRenderer_TraceLateIntro("store-enter");
	if (s_hdCaptureDiagnostics == 1 && frame == 60)
	{
		static int checkedTexturePage = 0;
		if (!checkedTexturePage)
		{
			D3DLOCKED_RECT textureLock;
			HRESULT checkHr;
			int mismatches = 0;
			int firstX = -1;
			int firstY = -1;
			u16 firstCpu = 0;
			u16 firstGpu = 0;
			int row;
			checkedTexturePage = 1;
			NativeRenderer_UpdateVRAM();
			checkHr = IDirect3DTexture9_LockRect(s_vram.texture, 0, &textureLock, NULL, D3DLOCK_READONLY);
			if (SUCCEEDED(checkHr))
			{
				XGUntileSurface(s_vramLinearScratch, VRAM_WIDTH * sizeof(u32), NULL,
				                textureLock.pBits, VRAM_WIDTH, VRAM_HEIGHT, NULL, sizeof(u32));
				for (row = 256; row < VRAM_HEIGHT; row++)
				{
					int column;
					for (column = 768; column < VRAM_WIDTH; column++)
					{
						const u32 packed = s_vramLinearScratch[row * VRAM_WIDTH + column];
						const u16 gpuPixel = (u16)(((packed >> 16) & 0xFFu) | (packed & 0x0000FF00u));
						const u16 cpuPixel = s_vram.cpuPixels[row * VRAM_WIDTH + column];
						if (gpuPixel != cpuPixel)
						{
							if (firstX < 0) { firstX = column; firstY = row; firstCpu = cpuPixel; firstGpu = gpuPixel; }
							mismatches++;
						}
					}
				}
				IDirect3DTexture9_UnlockRect(s_vram.texture, 0);
				Platform_Log("[probe] texture-page f=60 mismatches=%d first=%d,%d cpu=%04x gpu=%04x\n",
				             mismatches, firstX, firstY, (unsigned)firstCpu, (unsigned)firstGpu);
			}
			else
			{
				Platform_LogError("[probe] texture-page lock failed hr=%08x\n", (unsigned)checkHr);
			}
		}
	}
	if (s_mainRenderTarget.texture == NULL)
	{
		return;
	}
	IDirect3DDevice9_Resolve(s_device, D3DRESOLVE_RENDERTARGET0, NULL,
	                         (D3DBaseTexture *)s_mainRenderTarget.texture, NULL,
	                         0, 0, NULL, 0.0f, 0, NULL);
	if (s_hdCaptureDiagnostics == 1 && frame != lastHashFrame && (frame == 13 || frame == 60 || frame == 120 || frame == 205 || frame == 300))
	{
		lastHashFrame = frame;
		NativeRenderer_DebugHashMainTarget(frame);
	}
	if (s_hdCaptureDiagnostics == 1 && frame == 12)
	{
		D3DLOCKED_RECT textureLock;
		HRESULT lockHr = IDirect3DTexture9_LockRect(s_mainRenderTarget.texture, 0,
		                                             &textureLock, NULL, D3DLOCK_READONLY);
		if (SUCCEEDED(lockHr))
		{
			const u32 first = ((const u32 *)textureLock.pBits)[0];
			const u32 center = ((const u32 *)((const u8 *)textureLock.pBits +
			                              (s_mainRenderTarget.height / 2) * textureLock.Pitch))[s_mainRenderTarget.width / 2];
			Platform_Log("[diag] mainTexture f=12 pitch=%d first=%08x center=%08x\n",
			             textureLock.Pitch, (unsigned)first, (unsigned)center);
			IDirect3DTexture9_UnlockRect(s_mainRenderTarget.texture, 0);
		}
		else
		{
			Platform_LogError("[diag] mainTexture lock failed hr=%08x\n", (unsigned)lockHr);
		}
	}

	s_mainResolved = 1;
    {
        extern int g_nativeHDIntermediate;
        /* A render-only midpoint must never become the game's feedback image. */
        if (g_nativeHDIntermediate) return;
    }
	NativeRenderer_TraceLateIntro("store-pack-enter");
	NativeRenderer_GpuPackTextureToVRAM(s_mainRenderTarget.texture, x, y, w, h, 0);
	NativeRenderer_TraceLateIntro("store-pack-exit");
	if (s_hdCaptureDiagnostics == 1 && frame == 12 && w > 0 && h > 0 && x >= 0 && y >= 0 &&
	    x + w <= VRAM_WIDTH && y + h <= VRAM_HEIGHT)
	{
		int rowIndex;
		int magentaCount = 0;
		const u16 before = s_vram.cpuPixels[(y + h / 2) * VRAM_WIDTH + x + w / 2];
		NativeRenderer_SyncGpuVRAMToCPU(x, y, w, h);
		for (rowIndex = y; rowIndex < y + h; rowIndex++)
		{
			int columnIndex;
			for (columnIndex = x; columnIndex < x + w; columnIndex++)
			{
				if (s_vram.cpuPixels[rowIndex * VRAM_WIDTH + columnIndex] == 0xFC1Fu)
				{
					magentaCount++;
				}
			}
		}
		Platform_Log("[diag] pack-after f=12 rect=%d,%d,%d,%d center-before=%04x center-after=%04x magenta=%d\n",
		             x, y, w, h, (unsigned)before,
		             (unsigned)s_vram.cpuPixels[(y + h / 2) * VRAM_WIDTH + x + w / 2],
		             magentaCount);
	}
}

internal void NativeRenderer_FlushOffscreenToVRAM(void)
{
	if ((s_previousOffscreen.w <= 0) || (s_previousOffscreen.h <= 0) || (s_offscreenRenderTarget.texture == NULL))
	{
		return;
	}
	IDirect3DDevice9_Resolve(s_device, D3DRESOLVE_RENDERTARGET0, NULL,
	                         (D3DBaseTexture *)s_offscreenRenderTarget.texture, NULL,
	                         0, 0, NULL, 0.0f, 0, NULL);

	NativeRenderer_GpuPackTextureToVRAM(s_offscreenRenderTarget.texture, s_previousOffscreen.x, s_previousOffscreen.y, s_previousOffscreen.w, s_previousOffscreen.h, 0);
}

void NativeRenderer_SetOffscreenState(const RECT16 *offscreenRect, int enable)
{
	const int sameOffscreenRect = NativeRenderer_RectEquals16(&s_previousOffscreen, offscreenRect);
	if (!enable && !s_previousOffscreenState)
	{
		return;
	}

	if (enable && s_previousOffscreenState && sameOffscreenRect)
	{
		return;
	}

	if (enable)
	{
		if (s_previousOffscreenState)
		{
			NativeRenderer_FlushOffscreenToVRAM();
		}

		s_previousOffscreenState = 1;
		NativeRenderer_EnsureRenderTarget(&s_offscreenRenderTarget, offscreenRect->w, offscreenRect->h);
		s_previousOffscreen = *offscreenRect;
		NativeRenderer_LoadRenderTargetFromVRAM(&s_offscreenRenderTarget, offscreenRect->x, offscreenRect->y);
	}
	else
	{
		s_previousOffscreenState = 0;

		NativeRenderer_FlushOffscreenToVRAM();
		NativeRenderer_BindMainRenderTarget();
		NativeRenderer_SetViewPort(0, 0, s_mainRenderTarget.width, s_mainRenderTarget.height);
	}
}

/* Capture the exact VRAM display rectangle consumed by the presentation
 * shader. StoreFrameBuffer can also run midway through framebuffer feedback,
 * so its first main-target capture need not be the final displayed image. */
internal void NativeRenderer_DebugDisplayRect(int x, int y, int width, int height)
{
	static int lastFrame = -1;
	static int demoStart = -1;
	const int frame = (int)sdata->frameCounter;
	int captureDemo = 0;
	D3DLOCKED_RECT lock;
	FILE *file;
	char path[96];
	u8 header[18] = {0};
	u32 hash = 2166136261u;
	int row;
    if (s_hdCaptureDiagnostics != 1) return;
	if (sdata->gGT->levelID == CRASH_COVE && sdata->Loading.stage == LOAD_IDLE)
	{
		if (demoStart < 0) demoStart = frame;
		captureDemo = frame - demoStart <= 1200 && ((frame - demoStart) % 120) == 0;
		/* Sample the course fly-in before the start-line camera settles. */
		if (frame - demoStart <= 165 && ((frame - demoStart) % 15) == 0)
			captureDemo = 1;
		/* Bounded motion samples for wheel attachment during acceleration/turns. */
		if (frame - demoStart >= 340 && frame - demoStart <= 640 && ((frame - demoStart) % 15) == 0)
			captureDemo = 1;
	}
	if (frame == lastFrame || !(captureDemo || (frame >= 330 && frame <= 430 && frame % 10 == 0) ||
	                           (frame >= 880 && frame <= 1280 && frame % 20 <= 1) ||
	                           frame == 13 || frame == 60 || frame == 120 || frame == 205 ||
	                           frame == 300 || frame == 360 || frame == 400 || frame == 420 || frame == 450 ||
	                           frame == 480 || frame == 500 || frame == 510 || frame == 540 || frame == 600 ||
	                           frame == 660 || frame == 720 || frame == 800 || frame == 900 || frame == 1000 ||
	                           frame == 1200 || frame == 1500 || frame == 1800 || frame == 2400 || frame == 3000 ||
	                           frame == 4000 || frame == 5000 || frame == 6000 || frame == 7000 || frame == 8000 ||
	                           frame == 9000 || frame == 10000 || frame == 12000 || frame == 15000)) return;
	if (x < 0 || y < 0 || width <= 0 || height <= 0 || x + width > VRAM_WIDTH || y + height > VRAM_HEIGHT) return;
	if (FAILED(IDirect3DTexture9_LockRect(s_vram.texture, 0, &lock, NULL, D3DLOCK_READONLY))) return;
	lastFrame = frame;
	XGUntileSurface(s_vramLinearScratch, VRAM_WIDTH * sizeof(u32), NULL,
	                lock.pBits, VRAM_WIDTH, VRAM_HEIGHT, NULL, sizeof(u32));
	sprintf(path, "cache:\\ctr360_display_f%04d.tga", frame);
	file = fopen(path, "wb");
	header[2] = 2;
	header[12] = (u8)width; header[13] = (u8)(width >> 8);
	header[14] = (u8)height; header[15] = (u8)(height >> 8);
	header[16] = 24; header[17] = 0x20;
	if (file != NULL) fwrite(header, 1, sizeof(header), file);
	for (row = 0; row < height; row++)
	{
		int column;
		for (column = 0; column < width; column++)
		{
			const u32 packed = s_vramLinearScratch[(y + row) * VRAM_WIDTH + x + column];
			const u16 pixel = (u16)(((packed >> 16) & 0xFFu) | (packed & 0xFF00u));
			const u8 r = (u8)(pixel & 31), g = (u8)((pixel >> 5) & 31), b = (u8)((pixel >> 10) & 31);
			u8 bgr[3];
			bgr[0] = (u8)((b << 3) | (b >> 2));
			bgr[1] = (u8)((g << 3) | (g >> 2));
			bgr[2] = (u8)((r << 3) | (r >> 2));
			if (file != NULL) fwrite(bgr, 1, 3, file);
			hash = (hash ^ pixel) * 16777619u;
		}
	}
	if (file != NULL) fclose(file);
	IDirect3DTexture9_UnlockRect(s_vram.texture, 0);
	Platform_Log("[diag] display f=%d rect=%d,%d,%d,%d hash=%08x\n", frame, x, y, width, height, (unsigned)hash);
}


/* Opt-in capture of the actual enhanced backbuffer after edge smoothing.
 * Production/hardware runs do not lock or read GPU targets for diagnostics. */
static void NativeRenderer_DebugHDOutput(void)
{
    static D3DTexture *captureTexture;
    static int lastFrame[2] = {-1,-1};
    extern int g_nativeHDIntermediate;
    D3DLOCKED_RECT lock;
    FILE *file;
    char path[96];
    u8 header[18] = {0};
    int x,y, frame, levFrame, take;
    if (!s_hdCaptureDiagnostics) return;
    frame = (int)sdata->frameCounter;
    levFrame = sdata->gGT->framesInThisLEV;
    take = (sdata->gGT->levelID >= 0 && sdata->gGT->levelID < 18 && (levFrame == 200 || levFrame == 300 || levFrame == 400 || levFrame == 455 || levFrame == 480));
    take |= sdata->gGT->levelID == MAIN_MENU_LEVEL && (levFrame == 120 || levFrame == 200 || levFrame == 350);
    take |= (sdata->gGT->gameMode1 & ADVENTURE_ARENA) && sdata->Loading.stage == LOAD_IDLE &&
            levFrame < 1800 && (levFrame == 90 || levFrame == 180 || levFrame == 300 ||
            levFrame == 420 || levFrame == 480 || levFrame == 540 || levFrame == 600 || levFrame == 1140 || levFrame == 1260 || levFrame == 1380);
    take |= frame == 350 || frame == 370;
    take |= sdata->gGT->levelID == CRASH_COVE && (frame == 2145 || frame == 2165 || frame == 2185 || frame == 2205);
    if (!take || lastFrame[g_nativeHDIntermediate != 0] == frame) return;
    lastFrame[g_nativeHDIntermediate != 0] = frame;
    if (captureTexture == NULL && FAILED(IDirect3DDevice9_CreateTexture(s_device,1280,720,1,0,D3DFMT_A8R8G8B8,D3DPOOL_DEFAULT,&captureTexture,NULL))) return;
    if (FAILED(IDirect3DDevice9_Resolve(s_device,D3DRESOLVE_RENDERTARGET0,NULL,(D3DBaseTexture *)captureTexture,NULL,0,0,NULL,0.0f,0,NULL))) return;
    if (FAILED(IDirect3DTexture9_LockRect(captureTexture,0,&lock,NULL,D3DLOCK_READONLY))) return;
    XGUntileSurface(s_vramLinearScratch,1280*sizeof(u32),NULL,lock.pBits,1280,720,NULL,sizeof(u32));
    IDirect3DTexture9_UnlockRect(captureTexture,0);
    sprintf(path,"cache:\\ctr360_output_f%04d_%c.tga",frame,g_nativeHDIntermediate?'i':'f');
    file=fopen(path,"wb");
    if(file == NULL) return;
    header[2]=2; header[12]=0; header[13]=5; header[14]=0xd0; header[15]=2; header[16]=24; header[17]=0x20;
    fwrite(header,1,18,file);
    for(y=0;y<720;y++) for(x=0;x<1280;x++)
    {
        u32 pixel=s_vramLinearScratch[y*1280+x];
        u8 bgr[3];
        bgr[0]=(u8)pixel; bgr[1]=(u8)(pixel>>8); bgr[2]=(u8)(pixel>>16);
        fwrite(bgr,1,3,file);
    }
    fclose(file);
    Platform_Log("[HD] output f=%d level=%d age=%d intermediate=%d 1280x720\n",frame,(int)sdata->gGT->levelID,levFrame,g_nativeHDIntermediate);
}

void NativeRenderer_PresentVRAMRect(int displayX, int displayY, int displayW, int displayH)
{
	float sourceRect[4];
	const float flip = 1.0f; /* backbuffer: row 0 is the visual top row */
	NativeRenderer_TraceLateIntro("present-rect-enter");

	if ((displayW <= 0) || (displayH <= 0) || (s_device == NULL))
	{
		return;
	}

	Platform_Log("[trace] -> UpdateVRAM from PresentVRAMRect\n");
	NativeRenderer_UpdateVRAM();

	/* Backbuffer pass: GL window y -> D3D viewport y. */
	NativeRenderer_DebugDisplayRect(displayX, displayY, displayW, displayH);
    if (s_mainResolved)
    {
        /* Present the full-color 720p raster, retaining packed legacy VRAM
         * only as a side channel for game screen-copy effects and CPU reads. */
        NativeRenderer_SetRenderTarget(NULL);
        NativeRenderer_SetViewPort(0, 0, 1280, 720);
        NativeRenderer_SetScissorState(0);
        NativeRenderer_EnableDepth(0);
        NativeRenderer_SetBlendMode(BM_NONE);
        IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILENABLE, FALSE);
        IDirect3DDevice9_SetVertexShader(s_device, s_packVertexShader);
        IDirect3DDevice9_SetPixelShader(s_device, s_hdEdgeAA ? s_hdPresentPixelShader : s_vramCopyPixelShader);
        IDirect3DDevice9_SetTexture(s_device, 0, (D3DBaseTexture *)s_mainRenderTarget.texture);
        IDirect3DDevice9_SetSamplerState(s_device, 0, D3DSAMP_MINFILTER, s_hdEdgeAA ? D3DTEXF_LINEAR : D3DTEXF_POINT);
        IDirect3DDevice9_SetSamplerState(s_device, 0, D3DSAMP_MAGFILTER, s_hdEdgeAA ? D3DTEXF_LINEAR : D3DTEXF_POINT);
        NativeRenderer_DrawFullscreenQuad(-1.0f);
        NativeRenderer_DebugHDOutput();
        IDirect3DDevice9_SetSamplerState(s_device, 0, D3DSAMP_MINFILTER, D3DTEXF_POINT);
        IDirect3DDevice9_SetSamplerState(s_device, 0, D3DSAMP_MAGFILTER, D3DTEXF_POINT);
        IDirect3DDevice9_SetRenderState(s_device, D3DRS_STENCILENABLE, TRUE);
        s_previousShader = (ShaderID)-1;
        s_lastBoundTexture = (TextureID)-1;
        return;
    }
	NativeRenderer_SetViewPortGL(s_presentViewport.x, s_presentViewport.y, s_presentViewport.w, s_presentViewport.h, g_windowHeight);
	Platform_Log("[trace] pvr: viewport set\n");

	NativeRenderer_SetRenderTarget(NULL);
	Platform_Log("[trace] pvr: backbuffer bound\n");

	NativeRenderer_SetScissorState(0);
	NativeRenderer_EnableDepth(0);
	NativeRenderer_SetBlendMode(BM_NONE);
	Platform_Log("[trace] pvr: states set\n");

	sourceRect[0] = (float)displayX;
	sourceRect[1] = (float)displayY;
	sourceRect[2] = (float)displayW;
	sourceRect[3] = (float)displayH;

	IDirect3DDevice9_SetVertexShader(s_device, s_presentVertexShader);
	IDirect3DDevice9_SetPixelShader(s_device, s_presentPixelShader);
	Platform_Log("[trace] pvr: shaders set\n");
	IDirect3DDevice9_SetTexture(s_device, 0, (D3DBaseTexture *)s_vram.texture);
	Platform_Log("[trace] pvr: texture set\n");
	IDirect3DDevice9_SetVertexShaderConstantF(s_device, X360_PRESENT_VS_RECT_C17, sourceRect, 1);
	Platform_Log("[trace] pvr: consts set\n");

	NativeRenderer_DrawFullscreenQuad(flip);
	Platform_Log("[trace] pvr: quad drawn\n");
	NativeRenderer_TraceLateIntro("present-rect-exit");

	s_previousShader = (ShaderID)-1;
	s_lastBoundTexture = (TextureID)-1;
}

void NativeRenderer_PresentVRAMDisplay(void)
{
	Platform_Log("[trace] EndScene: PresentVRAMRect next\n");
	NativeRenderer_PresentVRAMRect(activeDispEnv.disp.x, activeDispEnv.disp.y, activeDispEnv.disp.w, activeDispEnv.disp.h);
}

void NativeRenderer_SwapWindow(void)
{
	NativeRenderer_TraceLateIntro("swap-enter");
	/* Frame heartbeat: tells a hung boot apart from a live loop that simply
	 * has nothing visible yet. One line on the first frame, then every ~5s. */
	s_presentedFrames++;
    {
        static LARGE_INTEGER start, frequency;
        static int level = -1, frames, simulationStart;
        LARGE_INTEGER now;
        QueryPerformanceCounter(&now);
        if (level != sdata->gGT->levelID)
        {
            QueryPerformanceFrequency(&frequency);
            start = now; frames = 0; level = sdata->gGT->levelID;
            simulationStart = (int)sdata->frameCounter;
        }
        if (++frames == 120)
        {
            double seconds = (double)(now.QuadPart-start.QuadPart)/(double)frequency.QuadPart;
            Platform_Log("[HD] level=%d renderFPS=%.2f simulationFPS=%.2f\n",level,120.0/seconds,((int)sdata->frameCounter-simulationStart)/seconds);
            start=now; frames=0; simulationStart=(int)sdata->frameCounter;
        }
    }
	if ((s_presentedFrames == 1) || ((s_presentedFrames % 300) == 0))
	{
		Platform_Log("[CTR Renderer] frame %d presented\n", s_presentedFrames);
	}

	if (s_device != NULL)
	{
		IDirect3DDevice9_Present(s_device, NULL, NULL, NULL, NULL);
	}
	NativeRenderer_TraceLateIntro("swap-exit");

	if ((s_presentedFrames >= 598) && (s_presentedFrames <= 606))
	{
		Platform_Log("[trace] present ok %d\n", s_presentedFrames);
	}
}
