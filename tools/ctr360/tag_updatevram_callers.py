"""Tag each UpdateVRAM call site so the log names the caller, and probe the
entry/exit of the two functions that have no post-call markers."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

# ordered: the call sites appear in file order; label them by their enclosing function
labels = [
    'SyncGpuVRAMToCPU',
    'BeginScene',
    'LoadRenderTargetFromVRAM',
    'GpuPackTextureToVRAM',
    'PresentVRAMRect',
]
parts = s.split('\tNativeRenderer_UpdateVRAM();')
print('call sites found:', len(parts) - 1)
assert len(parts) - 1 == len(labels), len(parts) - 1

out = [parts[0]]
for label, chunk in zip(labels, parts[1:]):
    out.append('\tPlatform_Log("[trace] -> UpdateVRAM from ' + label + NLE + '");' + NL + '\tNativeRenderer_UpdateVRAM();')
    out.append(chunk)
s = ''.join(out)

# entry/exit probes for the two unlabelled functions
edits = [
    ('internal void NativeRenderer_LoadRenderTargetFromVRAM(struct X360RenderTarget *target, int x, int y)' + NL + '{',
     'internal void NativeRenderer_LoadRenderTargetFromVRAM(struct X360RenderTarget *target, int x, int y)' + NL + '{' + NL
     + '\tPlatform_Log("[trace] LoadRenderTargetFromVRAM enter' + NLE + '");'),
    ('internal void NativeRenderer_SyncGpuVRAMToCPU(int x, int y, int w, int h)' + NL + '{',
     'internal void NativeRenderer_SyncGpuVRAMToCPU(int x, int y, int w, int h)' + NL + '{' + NL
     + '\tPlatform_Log("[trace] SyncGpuVRAMToCPU enter x=%d y=%d w=%d h=%d' + NLE + '", x, y, w, h);'),
]
for old, new in edits:
    n = s.count(old)
    print('probe matches=%d for %s' % (n, old.split('(')[0][:50]))
    assert n == 1, n
    s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('call-site tags + entry probes written')
