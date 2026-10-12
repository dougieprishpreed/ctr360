/* ctr360 probe: does the renderer's D3D9 + D3DX surface compile under the XDK? */
#include <xtl.h>
#include <d3d9.h>
#include <d3dx9.h>

typedef struct { float x, y; } P2;

int probe_render(void)
{
	IDirect3D9 *d3d;
	IDirect3DDevice9 *dev;
	D3DPRESENT_PARAMETERS pp;
	HRESULT hr;
	IDirect3DTexture9 *vram;
	IDirect3DTexture9 *readback;
	IDirect3DSurface9 *surf;
	IDirect3DSurface9 *ds;
	D3DLOCKED_RECT lock;
	ID3DXBuffer *code;
	ID3DXBuffer *errs;
	ID3DXConstantTable *ctab;
	IDirect3DVertexShader9 *vs;
	IDirect3DPixelShader9 *ps;
	D3DVERTEXELEMENT9 elems[5];
	D3DRECT r;
	D3DPOINT pt;
	D3DVIEWPORT9 vp;
	RECT rc;
	INT ival = 1;
	BOOL bval = TRUE;
	float f4[4];
	const char *src = "float4 main() : COLOR0 { return 1; }";

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

	d3d = Direct3DCreate9(D3D_SDK_VERSION);
	if (d3d == NULL) return 0;
	hr = d3d->CreateDevice(0, D3DDEVTYPE_HAL, 0, D3DCREATE_HARDWARE_VERTEXPROCESSING, &pp, &dev);
	if (FAILED(hr)) return 1;

	dev->SetRenderState(D3DRS_ZENABLE, FALSE);
	dev->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
	dev->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
	dev->SetRenderState(D3DRS_BLENDFACTOR, D3DCOLOR_ARGB(128, 64, 64, 64));
	dev->SetRenderState(D3DRS_BLENDOP, D3DBLENDOP_REVSUBTRACT);
	dev->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_BLENDFACTOR);
	dev->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVBLENDFACTOR);
	dev->SetRenderState(D3DRS_STENCILENABLE, TRUE);
	dev->SetRenderState(D3DRS_STENCILFUNC, D3DCMP_NOTEQUAL);
	dev->SetRenderState(D3DRS_STENCILREF, 1);
	dev->SetRenderState(D3DRS_STENCILMASK, 0xFF);
	dev->SetRenderState(D3DRS_STENCILFAIL, D3DSTENCILOP_REPLACE);
	dev->SetRenderState(D3DRS_SCISSORTESTENABLE, TRUE);
	dev->SetRenderState(D3DRS_COLORWRITEENABLE, D3DCOLORWRITEENABLE_ALL);
	dev->SetRenderState(D3DRS_SEPARATEALPHABLENDENABLE, TRUE);
	dev->SetRenderState(D3DRS_SRCBLENDALPHA, D3DBLEND_ONE);
	dev->SetRenderState(D3DRS_DESTBLENDALPHA, D3DBLEND_ZERO);
	dev->SetRenderState(D3DRS_FILLMODE, D3DFILL_SOLID);
	dev->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
	dev->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
	dev->SetTextureStageState(1, D3DTSS_COLOROP, D3DTOP_DISABLE);
	dev->SetSamplerState(0, D3DSAMP_MINFILTER, D3DTEXF_POINT);
	dev->SetSamplerState(1, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP);
	dev->SetSamplerState(1, D3DSAMP_MIPFILTER, D3DTEXF_NONE);

	if (FAILED(dev->CreateTexture(1024, 512, 1, D3DUSAGE_RENDERTARGET, D3DFMT_LIN_G8R8, D3DPOOL_DEFAULT, &vram, NULL))) return 2;
	if (FAILED(vram->GetSurfaceLevel(0, &surf))) return 3;
	if (FAILED(dev->CreateTexture(1024, 512, 1, D3DUSAGE_CPU_CACHED_MEMORY, D3DFMT_LIN_G8R8, D3DPOOL_DEFAULT, &readback, NULL))) return 4;
	if (FAILED(dev->CreateTexture(256, 256, 1, 0, D3DFMT_LIN_A8R8G8B8, D3DPOOL_DEFAULT, &vram, NULL))) return 5;
	if (FAILED(dev->CreateDepthStencilSurface(640, 480, D3DFMT_D24S8, D3DMULTISAMPLE_NONE, 0, TRUE, &ds, NULL))) return 6;

	dev->SetRenderTarget(0, surf);
	dev->SetDepthStencilSurface(NULL);
	dev->SetDepthStencilSurface(ds);
	dev->SetRenderTarget(0, NULL);

	if (SUCCEEDED(vram->LockRect(0, &lock, NULL, 0))) vram->UnlockRect(0);
	if (SUCCEEDED(readback->LockRect(0, &lock, NULL, D3DLOCK_READONLY))) readback->UnlockRect(0);

	r.left = 0; r.top = 0; r.right = 8; r.bottom = 8;
	pt.x = 0; pt.y = 0;
	dev->Resolve(D3DRESOLVE_RENDERTARGET0, &r, (D3DBaseTexture *)readback, &pt, 0, 0, NULL, 0.0f, 0, NULL);

	vp.X = 0; vp.Y = 0; vp.Width = 640; vp.Height = 480; vp.MinZ = 0.0f; vp.MaxZ = 1.0f;
	dev->SetViewport(&vp);
	rc.left = 0; rc.top = 0; rc.right = 8; rc.bottom = 8;
	dev->SetScissorRect(&rc);
	dev->Clear(1, NULL, D3DCLEAR_TARGET, 0, 1.0f, 0);
	dev->Clear(0, NULL, D3DCLEAR_STENCIL, 0, 1.0f, 0);

	hr = D3DXCompileShader(src, (UINT)strlen(src), NULL, NULL, "main", "ps_3_0", 0, &code, &errs, &ctab);
	if (SUCCEEDED(hr)) {
		UINT count = 1;
		D3DXCONSTANT_DESC desc;
		D3DXHANDLE h = ctab->GetConstantByName(NULL, "Projection");
		(void)h;
		(void)count;
		(void)desc;
		dev->CreatePixelShader((DWORD *)code->GetBufferPointer(), &ps);
		code->Release();
		ctab->Release();
	}
	if (errs != NULL) errs->Release();

	D3DXCompileShader(src, (UINT)strlen(src), NULL, NULL, "main", "vs_3_0", 0, &code, &errs, &ctab);
	dev->CreateVertexShader((DWORD *)code->GetBufferPointer(), &vs);

	elems[0].Stream = 0; elems[0].Offset = 0; elems[0].Type = D3DDECLTYPE_FLOAT4;
	elems[0].Method = D3DDECLMETHOD_DEFAULT; elems[0].Usage = D3DDECLUSAGE_POSITION; elems[0].UsageIndex = 0;
	elems[4] = D3DDECL_END();
	{
		IDirect3DVertexDeclaration9 *decl;
		dev->CreateVertexDeclaration(elems, &decl);
		dev->SetVertexDeclaration(decl);
	}
	{
		IDirect3DVertexBuffer9 *vb;
		void *data;
		dev->CreateVertexBuffer(1024 * 64, D3DUSAGE_DYNAMIC | D3DUSAGE_WRITEONLY, 0, D3DPOOL_DEFAULT, &vb, NULL);
		vb->Lock(0, 64, &data, D3DLOCK_DISCARD);
		vb->Unlock();
		dev->SetStreamSource(0, vb, 0, 64);
	}

	dev->SetVertexShaderConstantF(0, f4, 1);
	dev->SetPixelShaderConstantF(8, f4, 1);
	dev->SetPixelShaderConstantI(0, &ival, 1);
	dev->SetPixelShaderConstantB(0, &bval, 1);
	dev->SetPixelShader(ps);
	dev->SetVertexShader(vs);
	dev->SetTexture(0, vram);
	{
		const float quad[12] = {-1.f, -1.f, -1.f, 1.f, 1.f, 1.f, -1.f, -1.f, 1.f, 1.f, 1.f, -1.f};
		dev->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 2, quad, 2 * sizeof(float));
		dev->DrawPrimitive(D3DPT_TRIANGLELIST, 0, 2);
	}
	dev->Present(0, 0, 0, 0);

	return 7;
}
