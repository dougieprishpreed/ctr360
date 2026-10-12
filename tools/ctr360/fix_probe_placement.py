"""Move the two entry probes after each function's declaration block (C89)."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

# SyncGpuVRAMToCPU: probe currently right after '{', declarations follow it
old = NL.join([
    'internal void NativeRenderer_SyncGpuVRAMToCPU(int x, int y, int w, int h)',
    '{',
    '\tPlatform_Log("[trace] SyncGpuVRAMToCPU enter x=%d y=%d w=%d h=%d' + NLE + '", x, y, w, h);',
    '\tRECT16 readRect;',
    '\tint tileX0, tileY0, tileX1, tileY1;',
    '\tb32 needsReadback = 0;',
    '\tD3DRECT resolveRect;',
    '\tD3DPOINT destPoint;',
    '\tD3DLOCKED_RECT lock;',
    '\tint tileY;',
    '',
])
new = NL.join([
    'internal void NativeRenderer_SyncGpuVRAMToCPU(int x, int y, int w, int h)',
    '{',
    '\tRECT16 readRect;',
    '\tint tileX0, tileY0, tileX1, tileY1;',
    '\tb32 needsReadback = 0;',
    '\tD3DRECT resolveRect;',
    '\tD3DPOINT destPoint;',
    '\tD3DLOCKED_RECT lock;',
    '\tint tileY;',
    '',
    '\tPlatform_Log("[trace] SyncGpuVRAMToCPU enter x=%d y=%d w=%d h=%d' + NLE + '", x, y, w, h);',
])
n = s.count(old)
print('SyncGpuVRAMToCPU block matches:', n)
assert n == 1, n
s = s.replace(old, new)

# LoadRenderTargetFromVRAM: check its declaration block and relocate if needed
i = s.index('internal void NativeRenderer_LoadRenderTargetFromVRAM(struct X360RenderTarget *target, int x, int y)')
j = s.index('{', i)
k = s.index('Platform_Log("[trace] LoadRenderTargetFromVRAM enter' + NLE + '");', j)
print('LoadRenderTarget probe offset from {:', k - j)
# find the end of the declaration block (first blank line after '{')
blk_end = s.index(NL + NL, j)
if k < blk_end:
    probe = '\tPlatform_Log("[trace] LoadRenderTargetFromVRAM enter' + NLE + '");' + NL
    s = s[:k] + s[k + len(probe):]
    j = s.index('{', s.index('NativeRenderer_LoadRenderTargetFromVRAM(struct X360RenderTarget'))
    blk_end = s.index(NL + NL, j)
    s = s[:blk_end + 2] + probe + s[blk_end + 2:]
    print('LoadRenderTargetFromVRAM probe relocated after declarations')
else:
    print('LoadRenderTargetFromVRAM probe already after declarations')

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('probe placement fixed')
