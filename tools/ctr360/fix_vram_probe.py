"""Replace the placeholder VRAM-bound probe with an exact device query:
compare the device's current render target against s_vram.surface."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

old = ('\tPlatform_Log("[trace] UpdateVRAM: %d rect(s) first=%d,%d,%d,%d vramBoundAsRT=%d' + NLE + '",'
       + ' s_vram.cpuDirtyRectCount,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].x : -1,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].y : -1,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].w : -1,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].h : -1,'
       + ' (s_boundTarget == &s_vram_as_target) ? 1 : 0);')

new = (NL.join([
    '\t{',
    '\t\tD3DSurface *curRT = NULL;',
    '\t\tint vramBound = 0;',
    '\t\tif (s_device != NULL && SUCCEEDED(IDirect3DDevice9_GetRenderTarget(s_device, 0, &curRT)))',
    '\t\t{',
    '\t\t\tvramBound = (curRT == s_vram.surface) ? 1 : 0;',
    '\t\t\tif (curRT != NULL)',
    '\t\t\t{',
    '\t\t\t\tIDirect3DSurface9_Release(curRT);',
    '\t\t\t}',
    '\t\t}',
    '\t\tPlatform_Log("[trace] UpdateVRAM: %d rect(s) first=%d,%d,%d,%d vramBoundAsRT=%d' + NLE + '",',
    '\t\t\t(int)s_vram.cpuDirtyRectCount,',
    '\t\t\t(int)(s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].x : -1),',
    '\t\t\t(int)(s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].y : -1),',
    '\t\t\t(int)(s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].w : -1),',
    '\t\t\t(int)(s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].h : -1),',
    '\t\t\tvramBound);',
    '\t}',
]))

n = s.count(old)
print('placeholder probe matches:', n)
assert n == 1, n
s = s.replace(old, new)

# drop the marker global that is no longer used
old2 = NL.join([
    '/* marker target used only so probes can tell whether the VRAM surface is bound */',
    'global_variable struct X360RenderTarget s_vram_as_target;',
])
if s.count(old2) == 1:
    s = s.replace(old2, '')
    print('removed unused marker global')

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('exact RT probe written')
