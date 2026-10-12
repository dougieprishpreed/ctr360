"""Add fine-grained probes around the VRAM texture lock and the frame-end path:
which dirty rects are being uploaded, whether the VRAM texture is the current
render target, and post-lock markers. CRLF-aware; emits real backslash-n."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

def log(line):
    return '\tPlatform_Log("[trace] ' + line + NLE + '");'

edits = []

# 1. UpdateVRAM: report the rect list and whether VRAM is currently bound
old = '\tPlatform_Log("[trace] UpdateVRAM locking VRAM texture' + NLE + '");'
new = (log('UpdateVRAM: enter') + NL
       + '\tPlatform_Log("[trace] UpdateVRAM: %d rect(s) first=%d,%d,%d,%d vramBoundAsRT=%d' + NLE + '",'
       + ' s_vram.cpuDirtyRectCount,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].x : -1,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].y : -1,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].w : -1,'
       + ' s_vram.cpuDirtyRectCount > 0 ? s_vram.cpuDirtyRects[0].h : -1,'
       + ' (s_boundTarget == &s_vram_as_target) ? 1 : 0);' + NL
       + old)
edits.append(('UpdateVRAM entry report', old, new))

# 2. after the lock/copy/unlock: a done marker (anchor on the unlock inside UpdateVRAM)
old2 = '\t\tIDirect3DTexture9_UnlockRect(s_vram.texture, 0);'
new2 = old2 + NL + log('UpdateVRAM: unlocked')
edits.append(('UpdateVRAM unlock marker', old2, new2))

# 3. frame-end path markers
old3 = '\tNativeRenderer_StoreFrameBuffer(activeDispEnv.disp.x, activeDispEnv.disp.y, activeDispEnv.disp.w, activeDispEnv.disp.h);'
edits.append(('StoreFrameBuffer marker', old3, log('EndScene: StoreFrameBuffer next') + NL + old3))

old4 = '\tNativeRenderer_PresentVRAMRect(activeDispEnv.disp.x, activeDispEnv.disp.y, activeDispEnv.disp.w, activeDispEnv.disp.h);'
edits.append(('PresentVRAMRect marker', old4, log('EndScene: PresentVRAMRect next') + NL + old4))

applied = []
for label, old_t, new_t in edits:
    n = s.count(old_t)
    print('%-28s matches=%d' % (label, n))
    if n == 1:
        s = s.replace(old_t, new_t)
        applied.append(label)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('applied:', applied)

# s_vram_as_target must exist for the vramBoundAsRT probe; add it if missing
s2 = io.open(P, encoding='utf-8', newline='').read()
if 's_vram_as_target' in s2 and 'global_variable struct X360RenderTarget s_vram_as_target' not in s2:
    old5 = 'global_variable struct X360RenderTarget s_nullTarget;'
    new5 = (old5 + NL +
            '/* marker target used only so probes can tell whether the VRAM surface is bound */' + NL +
            'global_variable struct X360RenderTarget s_vram_as_target;')
    assert s2.count(old5) == 1
    s2 = s2.replace(old5, new5)
    io.open(P, 'w', encoding='utf-8', newline='').write(s2)
    print('added s_vram_as_target marker')
print('probes written')
