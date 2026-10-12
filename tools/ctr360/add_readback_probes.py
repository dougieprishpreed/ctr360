"""Probe each step of the SyncGpuVRAMToCPU readback (bind RT -> Resolve ->
lock -> copy -> restore) so the blocking call is visible."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

def log(t):
    return '\t\tPlatform_Log("[trace] readback: ' + t + NLE + '");'

edits = [
    ('\t\tIDirect3DDevice9_SetRenderTarget(s_device, 0, s_vram.surface);' + NL
     + '\t\tIDirect3DDevice9_SetDepthStencilSurface(s_device, NULL);' + NL
     + '\t\ts_boundTarget = NULL;',
     '\t\tPlatform_Log("[trace] readback: rect=%d,%d,%d,%d' + NLE + '", (int)readRect.x, (int)readRect.y, (int)readRect.w, (int)readRect.h);' + NL
     + '\t\tPlatform_Log("[trace] readback: before bind VRAM as RT' + NLE + '");' + NL
     + '\t\tIDirect3DDevice9_SetRenderTarget(s_device, 0, s_vram.surface);' + NL
     + '\t\tIDirect3DDevice9_SetDepthStencilSurface(s_device, NULL);' + NL
     + '\t\ts_boundTarget = NULL;' + NL
     + '\t\tPlatform_Log("[trace] readback: VRAM bound as RT' + NLE + '");'),
    ('\t\tIDirect3DDevice9_Resolve(s_device, D3DRESOLVE_RENDERTARGET0, &resolveRect, (D3DBaseTexture *)s_vram.readbackTexture, &destPoint, 0, 0, NULL, 0.0f, 0, NULL);',
     '\t\tPlatform_Log("[trace] readback: before resolve' + NLE + '");' + NL
     + '\t\tIDirect3DDevice9_Resolve(s_device, D3DRESOLVE_RENDERTARGET0, &resolveRect, (D3DBaseTexture *)s_vram.readbackTexture, &destPoint, 0, 0, NULL, 0.0f, 0, NULL);' + NL
     + '\t\tPlatform_Log("[trace] readback: resolve returned' + NLE + '");'),
    ('\t\tif (SUCCEEDED(IDirect3DTexture9_LockRect(s_vram.readbackTexture, 0, &lock, NULL, D3DLOCK_READONLY)))',
     '\t\tPlatform_Log("[trace] readback: before lock readback texture' + NLE + '");' + NL
     + '\t\tif (SUCCEEDED(IDirect3DTexture9_LockRect(s_vram.readbackTexture, 0, &lock, NULL, D3DLOCK_READONLY)))'),
    ('\t\t\tIDirect3DTexture9_UnlockRect(s_vram.readbackTexture, 0);',
     '\t\t\tIDirect3DTexture9_UnlockRect(s_vram.readbackTexture, 0);' + NL
     + '\t\t\tPlatform_Log("[trace] readback: copy done' + NLE + '");'),
    ('\t\tif (previousTarget != NULL)' + NL + '\t\t{' + NL + '\t\t\ts_boundTarget = previousTarget;',
     '\t\tPlatform_Log("[trace] readback: restoring RT' + NLE + '");' + NL
     + '\t\tif (previousTarget != NULL)' + NL + '\t\t{' + NL + '\t\t\ts_boundTarget = previousTarget;'),
]

for i, (old, new) in enumerate(edits):
    n = s.count(old)
    print('probe %d matches=%d' % (i, n))
    assert n == 1, (i, n)
    s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('readback probes written')
