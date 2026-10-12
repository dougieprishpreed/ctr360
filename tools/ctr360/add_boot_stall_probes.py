"""ctr360 boot-stall instrumentation + DR_MOVE code-byte fix (CRLF/LF aware).

Applies:
  1. DR_MOVE code-byte fix in SetDrawMove (platform/native_libgpu.c) - the raw
     32-bit store of 0x01000000 places the DR_MOVE command byte (packet offset 7)
     in byte 4 on the big-endian Xenon, so ParsePrimitive reads code 0x00, treats
     the packet as primSubType 0 (3 words) and walks the MoveImage payload as
     tagless primitives ("Unhandled tagless primitive 00d80100").
  2. Boot-stall probe trail: DrawOTag / DrawSync / MoveImage / walker /
     DrawAllSplits tail / DR_MOVE handler / vertex-buffer upload.
  3. 0-vertex vertex-buffer upload guard: D3D9 SizeToLock 0 means "whole buffer";
     skipping the empty upload avoids the degenerate lock.

Every edit asserts exactly one match; line ending is detected per file.
"""
import io

ROOT = r'F:\downloads\temp\python\hermes\ctrport\ctr360'
LIBGPU = ROOT + r'\platform\native_libgpu.c'
GPUC = ROOT + r'\platform\native_gpu.c'
VID = ROOT + r'\platform\xbox360\native_xbox360_video.c'

BS = chr(92)
NLE = BS + 'n'          # C "\n" escape inside emitted string literals
T = chr(9)


def try_patch(path, build_edits):
    for nl_name, NL in (('CRLF', chr(13) + chr(10)), ('LF', chr(10))):
        s = io.open(path, encoding='utf-8', newline='').read()
        edits = build_edits(NL)
        if all(s.count(new) == 1 for _, new in edits):
            print('%s: already applied (%s endings)' % (path.split(chr(92))[-1], nl_name))
            return
        counts = [s.count(old) for old, _ in edits]
        if all(c == 1 for c in counts):
            for old, new in edits:
                s = s.replace(old, new)
            io.open(path, 'w', encoding='utf-8', newline='').write(s)
            print('%s: %d edit(s) applied (%s endings)' % (path.split(chr(92))[-1], len(edits), nl_name))
            return
        print('%s: %s variant counts=%s' % (path.split(chr(92))[-1], nl_name, counts))
    raise SystemExit('no single-ending variant matched for ' + path)


def libgpu_edits(NL):
    return [
        # --- DrawOTag: entry + walker/splits/exit markers ------------------
        (NL.join([
            'void DrawOTag(void *p)',
            '{',
            T + 'NativePerf_BeginScope(NATIVE_PERF_BUCKET_DRAW_OTAG);',
        ]),
         NL.join([
            'void DrawOTag(void *p)',
            '{',
            T + 'static int s_drawOTagTrace = 0;',
            T + 'NativePerf_BeginScope(NATIVE_PERF_BUCKET_DRAW_OTAG);',
            T + 'if (s_drawOTagTrace < 12)',
            T + '{',
            T + T + 's_drawOTagTrace++;',
            T + T + 'Platform_Log("[trace] DrawOTag#%d enter p=%p' + NLE + '", s_drawOTagTrace, p);',
            T + '}',
        ])),

        (NL.join([
            T + T + 'ParsePrimitivesLinkedList((uint32_t *)p, 0);',
            T + T + 'DrawAllSplits();',
            T + '} while (g_dbg_emulatorPaused);',
            T + 'NativePerf_EndScope(NATIVE_PERF_BUCKET_DRAW_OTAG);',
        ]),
         NL.join([
            T + T + 'ParsePrimitivesLinkedList((uint32_t *)p, 0);',
            T + T + 'if (s_drawOTagTrace <= 12)',
            T + T + '{',
            T + T + T + 'Platform_Log("[trace] DrawOTag#%d walker done' + NLE + '", s_drawOTagTrace);',
            T + T + '}',
            T + T + 'DrawAllSplits();',
            T + T + 'if (s_drawOTagTrace <= 12)',
            T + T + '{',
            T + T + T + 'Platform_Log("[trace] DrawOTag#%d splits done' + NLE + '", s_drawOTagTrace);',
            T + T + '}',
            T + '} while (g_dbg_emulatorPaused);',
            T + 'NativePerf_EndScope(NATIVE_PERF_BUCKET_DRAW_OTAG);',
            T + 'if (s_drawOTagTrace <= 12)',
            T + '{',
            T + T + 'Platform_Log("[trace] DrawOTag#%d exit' + NLE + '", s_drawOTagTrace);',
            T + '}',
        ])),

        # --- DrawSync: entry + exit ---------------------------------------
        (NL.join([
            'int DrawSync(int mode)',
            '{',
            T + '(void)mode;',
        ]),
         NL.join([
            'int DrawSync(int mode)',
            '{',
            T + 'static int s_drawSyncTrace = 0;',
            T + 'if (s_drawSyncTrace < 12)',
            T + '{',
            T + T + 's_drawSyncTrace++;',
            T + T + 'Platform_Log("[trace] DrawSync#%d enter mode=%d' + NLE + '", s_drawSyncTrace, mode);',
            T + '}',
            T + '(void)mode;',
        ])),

        (NL.join([
            T + 'if (drawsync_callback != NULL)',
            T + '{',
            T + T + 'drawsync_callback();',
            T + '}',
            '',
            T + 'return 0;',
            '}',
        ]),
         NL.join([
            T + 'if (drawsync_callback != NULL)',
            T + '{',
            T + T + 'drawsync_callback();',
            T + '}',
            '',
            T + 'if (s_drawSyncTrace <= 12)',
            T + '{',
            T + T + 'Platform_Log("[trace] DrawSync#%d exit' + NLE + '", s_drawSyncTrace);',
            T + '}',
            '',
            T + 'return 0;',
            '}',
        ])),

        # --- MoveImage: prove the page move actually runs ------------------
        (NL.join([
            'int MoveImage(RECT16 *rect, int x, int y)',
            '{',
            T + 'NativeRenderer_CopyVRAM(NULL, rect->x, rect->y, rect->w, rect->h, x, y);',
        ]),
         NL.join([
            'int MoveImage(RECT16 *rect, int x, int y)',
            '{',
            T + 'static int s_moveImageTrace = 0;',
            T + 'if (s_moveImageTrace < 24)',
            T + '{',
            T + T + 's_moveImageTrace++;',
            T + T + 'Platform_Log("[trace] MoveImage#%d rect=%d,%d %dx%d dest=%d,%d' + NLE + '", s_moveImageTrace, (int)rect->x, (int)rect->y, (int)rect->w, (int)rect->h, x, y);',
            T + '}',
            T + 'NativeRenderer_CopyVRAM(NULL, rect->x, rect->y, rect->w, rect->h, x, y);',
        ])),

        # --- THE FIX: DR_MOVE command byte must land at packet offset 7 ----
        (NL.join([
            T + 'p->code[0] = 0x1000000;',
            T + 'p->code[1] = 0x80000000;',
        ]),
         NL.join([
            T + '/* NOTE(ctr360): code[0] is the PSX little-endian byte image 00 00 00 01;',
            T + ' * the DR_MOVE command byte is packet offset 7 (P_TAG->code). A raw',
            T + ' * 32-bit store lands 0x01 in byte 4 on the big-endian Xenon, so the',
            T + ' * parser read code 0x00 and walked the MoveImage payload as tagless',
            T + ' * primitives - the VRAM page move never ran. Write the byte image. */',
            T + 'memset(&p->code[0], 0, sizeof(p->code[0]));',
            T + 'setcode(p, 0x01);',
            T + 'p->code[1] = 0x80000000;',
        ])),
    ]


def gpuc_edits(NL):
    return [
        # --- DrawAllSplits: keep the split probe + add tail markers --------
        (NL.join([
            T + 'NativePerf_BeginScope(NATIVE_PERF_BUCKET_DRAW_ALL_SPLITS);',
            T + '// CPU-originated LoadImage, MoveImage, and fill commands are GPU-visible',
            T + '// before the next draw batch, matching PS1 command ordering.',
            T + 'NativeRenderer_UpdateVRAM();',
            '#ifdef CTR_INTERNAL',
        ]),
         NL.join([
            T + 'NativePerf_BeginScope(NATIVE_PERF_BUCKET_DRAW_ALL_SPLITS);',
            T + '// CPU-originated LoadImage, MoveImage, and fill commands are GPU-visible',
            T + '// before the next draw batch, matching PS1 command ordering.',
            T + 'NativeRenderer_UpdateVRAM();',
            T + 'Platform_Log("[trace] DrawAllSplits: %d split(s) at %d verts' + NLE + '", s_gpu.splitIndex, s_gpu.vertexIndex);',
            '#ifdef CTR_INTERNAL',
        ])),

        (NL.join([
            T + '// next code ideally should be called before EndScene',
            T + 'NativeRenderer_UpdateVertexBuffer(s_gpu.vertexBuffer, s_gpu.vertexIndex);',
            '',
            T + 'for (int i = 1; i <= s_gpu.splitIndex; i++)',
            T + '{',
            T + T + 'DrawSplit(&s_gpu.splits[i]);',
            T + '}',
            '',
            T + 'ClearSplits();',
        ]),
         NL.join([
            T + '// next code ideally should be called before EndScene',
            T + 'NativeRenderer_UpdateVertexBuffer(s_gpu.vertexBuffer, s_gpu.vertexIndex);',
            T + 'Platform_Log("[trace] DrawAllSplits: vertex upload returned' + NLE + '");',
            '',
            T + 'for (int i = 1; i <= s_gpu.splitIndex; i++)',
            T + '{',
            T + T + 'DrawSplit(&s_gpu.splits[i]);',
            T + '}',
            T + 'Platform_Log("[trace] DrawAllSplits: splits drawn' + NLE + '");',
            '',
            T + 'ClearSplits();',
            T + 'Platform_Log("[trace] DrawAllSplits: cleared, leaving' + NLE + '");',
        ])),

        # --- walker trace (capped at 20 walks) -----------------------------
        (NL.join([
            T + T + '// walk OT_TAG linked list',
            T + T + 'u8 *basePacket = (u8 *)p;',
            T + T + 'while (true)',
            T + T + '{',
            T + T + T + 'const int tagLength = getlen(basePacket);',
            T + T + T + 'if (tagLength > 0)',
            T + T + T + '{',
        ]),
         NL.join([
            T + T + '// walk OT_TAG linked list',
            T + T + 'u8 *basePacket = (u8 *)p;',
            T + T + 'static int s_walkTrace = 0;',
            T + T + 'const int walkTraceOn = (s_walkTrace < 20);',
            T + T + 'if (walkTraceOn)',
            T + T + '{',
            T + T + T + 's_walkTrace++;',
            T + T + '}',
            T + T + 'while (true)',
            T + T + '{',
            T + T + T + 'const int tagLength = getlen(basePacket);',
            T + T + T + 'if (walkTraceOn)',
            T + T + T + '{',
            T + T + T + T + 'Platform_Log("[trace] walk#%d pkt=%p len=%d code=%02x tag=%08x' + NLE + '", s_walkTrace, (void *)basePacket, tagLength, getcode(basePacket), (unsigned)CTR_GPU_ReadTagWord(basePacket));',
            T + T + T + '}',
            T + T + T + 'if (tagLength > 0)',
            T + T + T + '{',
        ])),

        (NL.join([
            T + T + T + T + 'if (currentPacket < endPacket)',
            T + T + T + T + '{',
            T + T + T + T + T + 'primLength = ParsePrimitive((P_TAG *)currentPacket);',
            T + T + T + T + T + 'currentPacket += (primLength + P_LEN) * sizeof(u32);',
            T + T + T + T + '}',
            '',
            T + T + T + T + 'while (currentPacket < endPacket)',
            T + T + T + T + '{',
            T + T + T + T + T + 'primLength = ParseTaglessPrimitive((u32 *)currentPacket);',
            T + T + T + T + T + 'currentPacket += primLength * sizeof(u32);',
            T + T + T + T + '}',
        ]),
         NL.join([
            T + T + T + T + 'if (currentPacket < endPacket)',
            T + T + T + T + '{',
            T + T + T + T + T + 'primLength = ParsePrimitive((P_TAG *)currentPacket);',
            T + T + T + T + T + 'if (walkTraceOn)',
            T + T + T + T + T + '{',
            T + T + T + T + T + T + 'Platform_Log("[trace] walk#%d   prim code=%02x len=%d primLength=%d' + NLE + '", s_walkTrace, getcode(currentPacket), getlen(currentPacket), primLength);',
            T + T + T + T + T + '}',
            T + T + T + T + T + 'currentPacket += (primLength + P_LEN) * sizeof(u32);',
            T + T + T + T + '}',
            '',
            T + T + T + T + 'while (currentPacket < endPacket)',
            T + T + T + T + '{',
            T + T + T + T + T + 'primLength = ParseTaglessPrimitive((u32 *)currentPacket);',
            T + T + T + T + T + 'if (walkTraceOn)',
            T + T + T + T + T + '{',
            T + T + T + T + T + T + 'Platform_Log("[trace] walk#%d   tagless cmd=%08x primLength=%d' + NLE + '", s_walkTrace, (unsigned)CTR_GPU_ReadTagWord(currentPacket), primLength);',
            T + T + T + T + T + '}',
            T + T + T + T + T + 'currentPacket += primLength * sizeof(u32);',
            T + T + T + T + '}',
        ])),

        (NL.join([
            T + T + T + 'GPUDrawSplit *lastSplit = &s_gpu.splits[s_gpu.splitIndex];',
            T + T + T + 'lastSplit->numVerts = s_gpu.vertexIndex - lastSplit->startVertex;',
            '',
            T + T + T + 'if (isendprim(basePacket))',
        ]),
         NL.join([
            T + T + T + 'GPUDrawSplit *lastSplit = &s_gpu.splits[s_gpu.splitIndex];',
            T + T + T + 'lastSplit->numVerts = s_gpu.vertexIndex - lastSplit->startVertex;',
            '',
            T + T + T + 'if (walkTraceOn)',
            T + T + T + '{',
            T + T + T + T + 'Platform_Log("[trace] walk#%d   packet done: splits=%d verts=%d end=%d' + NLE + '", s_walkTrace, s_gpu.splitIndex, s_gpu.vertexIndex, (int)isendprim(basePacket));',
            T + T + T + '}',
            '',
            T + T + T + 'if (isendprim(basePacket))',
        ])),

        # --- DR_MOVE handler: prove the page move runs ---------------------
        (NL.join([
            T + T + T + 'if (NativeGpu_HasPendingSplits())',
            T + T + T + '{',
            T + T + T + T + 'DrawAllSplits();',
            T + T + T + '}',
            T + T + T + 'MoveImage(&rect, x, y);',
            T + T + T + 'primLength = 5;',
        ]),
         NL.join([
            T + T + T + 'if (NativeGpu_HasPendingSplits())',
            T + T + T + '{',
            T + T + T + T + 'DrawAllSplits();',
            T + T + T + '}',
            T + T + T + 'Platform_Log("[trace] DR_MOVE rect=%d,%d %dx%d dest=%d,%d' + NLE + '", (int)rect.x, (int)rect.y, (int)rect.w, (int)rect.h, x, y);',
            T + T + T + 'MoveImage(&rect, x, y);',
            T + T + T + 'primLength = 5;',
        ])),
    ]


def vid_edits(NL):
    return [
        (NL.join([
            'void NativeRenderer_UpdateVertexBuffer(const GrVertex *vertices, int num_vertices)',
            '{',
            T + 'X360Vertex *out;',
            T + 's32 bufferIndex;',
        ]),
         NL.join([
            'void NativeRenderer_UpdateVertexBuffer(const GrVertex *vertices, int num_vertices)',
            '{',
            T + 'X360Vertex *out;',
            T + 's32 bufferIndex;',
            T + 'static int s_vbTrace = 0;',
        ])),

        (NL.join([
            T + 'bufferIndex = s_curVertexBuffer;',
            T + 's_curVertexBuffer = (s_curVertexBuffer + 1) & 1;',
            T + 's_boundVertexBuffer = bufferIndex;',
        ]),
         NL.join([
            T + 'bufferIndex = s_curVertexBuffer;',
            T + 's_curVertexBuffer = (s_curVertexBuffer + 1) & 1;',
            T + 's_boundVertexBuffer = bufferIndex;',
            '',
            T + 'if (s_vbTrace < 12)',
            T + '{',
            T + T + 's_vbTrace++;',
            T + T + 'Platform_Log("[trace] vb#%d verts=%d bytes=%d buffer=%d' + NLE + '", s_vbTrace, num_vertices, (int)(num_vertices * (int)sizeof(X360Vertex)), (int)bufferIndex);',
            T + '}',
            '',
            T + 'if (num_vertices <= 0)',
            T + '{',
            T + T + '/* NOTE(ctr360): D3D9 SizeToLock 0 means "lock the whole buffer"; for an',
            T + T + ' * empty upload that lock is pure overhead and it stalled the d3d9',
            T + T + ' * resource path in Xenia at the first post-TIM-lock call. Skip it. */',
            T + T + 'return;',
            T + '}',
        ])),

        (NL.join([
            T + 'out = (X360Vertex *)D3DVertexBuffer_Lock(s_vertexBuffer[bufferIndex], 0, num_vertices * sizeof(X360Vertex), D3DLOCK_NOOVERWRITE);',
            T + 'if (out == NULL)',
        ]),
         NL.join([
            T + 'if (s_vbTrace <= 12) { Platform_Log("[trace] vb: locking bytes=%d' + NLE + '", (int)(num_vertices * (int)sizeof(X360Vertex))); }',
            T + 'out = (X360Vertex *)D3DVertexBuffer_Lock(s_vertexBuffer[bufferIndex], 0, num_vertices * sizeof(X360Vertex), D3DLOCK_NOOVERWRITE);',
            T + 'if (s_vbTrace <= 12) { Platform_Log("[trace] vb: lock returned %p' + NLE + '", (void *)out); }',
            T + 'if (out == NULL)',
        ])),

        (NL.join([
            T + 'IDirect3DVertexBuffer9_Unlock(s_vertexBuffer[bufferIndex]);',
            '}',
        ]),
         NL.join([
            T + 'IDirect3DVertexBuffer9_Unlock(s_vertexBuffer[bufferIndex]);',
            T + 'if (s_vbTrace <= 12) { Platform_Log("[trace] vb: unlocked' + NLE + '"); }',
            '}',
        ])),
    ]


try_patch(LIBGPU, libgpu_edits)
try_patch(GPUC, gpuc_edits)
try_patch(VID, vid_edits)
print('boot-stall probes + DR_MOVE fix written')
