"""Probe the split-draw path (CRLF/LF aware, C89-safe placement)."""
import io

GPU = r'F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\gen\platform\native_gpu.c'
VID = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
BS = chr(92)
NLE = BS + 'n'

def try_patch(path, build_edits):
    for nl_name, NL in (('CRLF', chr(13) + chr(10)), ('LF', chr(10))):
        s = io.open(path, encoding='utf-8', newline='').read()
        edits = build_edits(NL)
        ok = all(s.count(old) == 1 for old, _ in edits)
        if ok:
            for old, new in edits:
                s = s.replace(old, new)
            io.open(path, 'w', encoding='utf-8', newline='').write(s)
            print('%s: patched with %s endings' % (path.split(chr(92))[-1], nl_name))
            return
    raise SystemExit('no single-ending variant matched for ' + path)

def gpu_edits(NL):
    return [
        (NL.join([
            '\tNativePerf_BeginScope(NATIVE_PERF_BUCKET_DRAW_ALL_SPLITS);',
            '\t// CPU-originated LoadImage, MoveImage, and fill commands are GPU-visible',
            '\t// before the next draw batch, matching PS1 command ordering.',
            '\tNativeRenderer_UpdateVRAM();',
        ]),
         NL.join([
            '\tNativePerf_BeginScope(NATIVE_PERF_BUCKET_DRAW_ALL_SPLITS);',
            '\t// CPU-originated LoadImage, MoveImage, and fill commands are GPU-visible',
            '\t// before the next draw batch, matching PS1 command ordering.',
            '\tNativeRenderer_UpdateVRAM();',
            '\tPlatform_Log("[trace] DrawAllSplits: %d split(s) at %d verts' + NLE + '", s_gpu.splitIndex, s_gpu.vertexIndex);',
         ])),
    ]

def vid_edits(NL):
    return [
        (NL.join([
            'void NativeRenderer_DrawTriangles(int startVertex, int numTriangles)',
            '{',
        ]),
         NL.join([
            'void NativeRenderer_DrawTriangles(int startVertex, int numTriangles)',
            '{',
            '\tstatic int s_drawLogCount = 0;',
            '',
            '\tif (s_drawLogCount < 24)',
            '\t{',
            '\t\ts_drawLogCount++;',
            '\t\tPlatform_Log("[trace] DrawTriangles start=%d count=%d' + NLE + '", startVertex, numTriangles);',
            '\t}',
            '',
         ])),
    ]

try_patch(GPU, gpu_edits)
try_patch(VID, vid_edits)
print('split-path probes written')
