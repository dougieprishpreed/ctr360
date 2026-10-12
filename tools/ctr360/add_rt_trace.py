"""Insert temporary [trace] log lines into the 360 renderer's scene/RT path so
the next console run shows exactly which call blocks. Handles the file's CRLF
line endings and emits backslash-n escapes via chr(92)."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'          # escape sequence as it must appear in the C source
NL = chr(13) + chr(10)  # file's line ending

s = io.open(P, encoding='utf-8', newline='').read()

def logcall(label):
    return '\tPlatform_Log("[trace] ' + label + NLE + '");'

edits = [
    ('void NativeRenderer_BeginScene(void)' + NL + '{' + NL + '\ts_lastBoundTexture = (TextureID)-1;',
     'void NativeRenderer_BeginScene(void)' + NL + '{' + NL + '\ts_lastBoundTexture = (TextureID)-1;' + NL
     + logcall('BeginScene enter') + NL
     + logcall('BeginScene after viewport+bars') + NL
     + logcall('BeginScene after bind main RT') + NL
     + logcall('BeginScene after UpdateVRAM') + NL
     + logcall('BeginScene after load RT from VRAM')),
    ('internal void NativeRenderer_EnsureRenderTarget(struct X360RenderTarget *target, int width, int height)' + NL + '{',
     'internal void NativeRenderer_EnsureRenderTarget(struct X360RenderTarget *target, int width, int height)' + NL + '{' + NL
     + '\tPlatform_Log("[trace] EnsureRT enter' + NLE + '");'),
    ('\tif (SUCCEEDED(IDirect3DTexture9_LockRect(s_vram.texture, 0, &lock, &region, 0)))',
     '\tPlatform_Log("[trace] UpdateVRAM locking VRAM texture' + NLE + '");' + NL
     + '\tif (SUCCEEDED(IDirect3DTexture9_LockRect(s_vram.texture, 0, &lock, &region, 0)))'),
]

for old, new in edits:
    n = s.count(old)
    print('edit %-42s matches=%d' % (old.split(NL)[0][:40], n))
    assert n == 1, n
    s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('trace instrumentation written')
