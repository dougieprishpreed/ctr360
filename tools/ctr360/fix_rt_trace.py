"""Fix the BeginScene trace placement: the 'after X' markers must come after
each real call, not all at the top."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'
NL = chr(13) + chr(10)

s = io.open(P, encoding='utf-8', newline='').read()

def logcall(label):
    return '\tPlatform_Log("[trace] ' + label + NLE + '");'

old = NL.join([
    'void NativeRenderer_BeginScene(void)',
    '{',
    '\ts_lastBoundTexture = (TextureID)-1;',
    logcall('BeginScene enter'),
    logcall('BeginScene after viewport+bars'),
    logcall('BeginScene after bind main RT'),
    logcall('BeginScene after UpdateVRAM'),
    logcall('BeginScene after load RT from VRAM'),
    '',
    '\tNativeRenderer_UpdatePresentationViewport();',
    '\tNativeRenderer_ClearPresentationBars();',
    '\tNativeRenderer_BindMainRenderTarget();',
    '',
    '\tNativeRenderer_UpdateVRAM();',
    '\tif (!activeDrawEnv.isbg)',
    '\t{',
    '\t\tNativeRenderer_LoadRenderTargetFromVRAM(&s_mainRenderTarget, activeDispEnv.disp.x, activeDispEnv.disp.y);',
    '\t}',
])

new = NL.join([
    'void NativeRenderer_BeginScene(void)',
    '{',
    '\ts_lastBoundTexture = (TextureID)-1;',
    logcall('BeginScene enter'),
    '',
    '\tNativeRenderer_UpdatePresentationViewport();',
    '\tNativeRenderer_ClearPresentationBars();',
    logcall('BeginScene after viewport+bars'),
    '',
    '\tNativeRenderer_BindMainRenderTarget();',
    logcall('BeginScene after bind main RT'),
    '',
    '\tNativeRenderer_UpdateVRAM();',
    logcall('BeginScene after UpdateVRAM'),
    '\tif (!activeDrawEnv.isbg)',
    '\t{',
    '\t\tNativeRenderer_LoadRenderTargetFromVRAM(&s_mainRenderTarget, activeDispEnv.disp.x, activeDispEnv.disp.y);',
    '\t}',
    logcall('BeginScene after load RT from VRAM'),
])

n = s.count(old)
print('BeginScene block matches:', n)
assert n == 1, n
s = s.replace(old, new)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('BeginScene trace placement fixed')
