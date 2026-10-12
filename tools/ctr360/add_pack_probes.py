"""Probe each step of GpuPackTextureToVRAM (the frame-end VRAM pack) so the exact
blocking call is visible in the log. CRLF-aware, real backslash-n escapes."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

def log(t):
    return '\tPlatform_Log("[trace] pack: ' + t + NLE + '");'

edits = [
    ('\tIDirect3DDevice9_SetRenderTarget(s_device, 0, s_vram.surface);' + NL + '\tIDirect3DDevice9_SetDepthStencilSurface(s_device, NULL);' + NL + '\ts_boundTarget = NULL;',
     log('before bind VRAM as RT') + NL
     + '\tIDirect3DDevice9_SetRenderTarget(s_device, 0, s_vram.surface);' + NL
     + '\tIDirect3DDevice9_SetDepthStencilSurface(s_device, NULL);' + NL
     + '\ts_boundTarget = NULL;' + NL
     + log('VRAM bound as RT')),
    ('\tNativeRenderer_SetViewPort(x, y, w, h);',
     log('before SetViewPort') + NL + '\tNativeRenderer_SetViewPort(x, y, w, h);' + NL + log('viewport set')),
    ('\tNativeRenderer_DrawFullscreenQuad(-1.0f); /* texture destination */',
     log('before pack draw') + NL
     + '\tNativeRenderer_DrawFullscreenQuad(-1.0f); /* texture destination */' + NL
     + log('after pack draw')),
    ('\t\tNativeRenderer_SetRenderTarget(&s_mainRenderTarget);' + NL + '\t\tNativeRenderer_SetViewPort(0, 0, s_mainRenderTarget.width, s_mainRenderTarget.height);',
     log('before restore main RT') + NL
     + '\t\tNativeRenderer_SetRenderTarget(&s_mainRenderTarget);' + NL
     + '\t\tNativeRenderer_SetViewPort(0, 0, s_mainRenderTarget.width, s_mainRenderTarget.height);' + NL
     + log('main RT restored (else branch)')),
]

for i, edit in enumerate(edits):
    if len(edit) == 3:
        label, old, new = edit
    else:
        old, new = edit
        label = 'edit %d' % i
    n = s.count(old)
    print('%-34s matches=%d' % (label, n))
    assert n == 1, (label, n)
    s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('pack-path probes written')
