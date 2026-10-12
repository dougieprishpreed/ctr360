# CTR360 — Performance & Playability Strategy

Forward-looking companion to `PORT_360.md`. The goal is not "reach the title
screen" but **a stable, playable 30 fps game** in races, menus, 2P split and
cutscenes. This document inventories the real workload, ranks the risks, fixes
the design decisions that must be made *before* the 360 backend is written,
and sets the benchmark ladder.

## 1. The frame budget

- Game cadence: `VSync(2)` on the PSX NTSC clock = **29.909 fps** (see the
  vblank math in `platform/native_platform.c`: 897619 GPU cycles / 53693175 Hz
  per vblank). Budget ≈ **33.4 ms/frame**.
- Xenon: 3 cores × 3.2 GHz → ≈107 M cycles/core/frame; 6 hardware threads.
  The original code ran on a **33 MHz** MIPS + fixed-function GPU + SPU.
  The port is native C plus *software emulation of the GPU packet layer, the
  GTE, and the SPU* — all cheap by Xenon standards, but the following are the
  places where that assumption must be checked, not assumed.

## 2. Workload inventory (where the cycles actually go)

| # | Subsystem | Source | Est. cost @30 fps | Notes |
|---|---|---|---|---|
| 1 | Game logic | `game/**` (~native C of a 33 MHz game) | ~2-5 ms | fixed-point, integer-heavy; PPC loves it |
| 2 | GPU packet parse (OT walk) | `platform/native_gpu.c` (2.0k lines) | ~1-3 ms heavy scenes | branchy bit-field decoding, bounded by prim count |
| 3 | GTE (per-vertex transform) | `platform/native_gte_core.c` (733 lines) | <1 ms | table-driven rcosin/sqrt; PSX did this at 33 MHz |
| 4 | SPU + XA software mixing | `platform/native_audio.c` (3.5k lines) | 1-4 ms | **must live off the main thread** |
| 5 | STR/MDEC video decode (FMV) | `platform/native_str.c` (827 lines) | few ms during FMV only | software IDCT/RLE; acceptable at 15 fps video |
| 6 | Renderer submission | `platform/native_gpu.c` → `native_renderer.c` | 2-4 ms | vertex upload + VRAM texture updates + draws |
| 7 | Present | new D3D9 upscale blit | <0.5 ms | see §3.1 |
| 8 | Memory | mempack arena (`native_memory.c`) | 0 | 512 MB vs a PSX working set of a few MB |
| 9 | Streaming / IO | `native_disc_image.c` + cooked image | 0 in steady state | see §3.5 |

Composite main-thread estimate: **~8-16 ms** typical. The margin exists on
hardware; the risks below are about *spikes*, not averages.

## 3. Design decisions taken now (they shape the backend)

### 3.1 Render at PSX resolution by default, upscale at present
`native_renderer.c` already draws into a PSX-sized main render target (FBO,
line ~1326). Default: keep exactly that - D3D9 renders to a 512×240-ish
texture and a single fullscreen-quad pass upscales to 720p; fill cost stays
PSX-scale and the look stays authentic. User-selectable alternative
(`internal_resolution = upscaled` in `ctr360.ini`): render at the output
resolution for sharper textures - this raises fill rate and pixel-shader cost
roughly 7x at 720p (122k -> 921k pixels/frame); it is the documented
perf-costly variant, gated on the M6 hardware numbers.

### 3.2 Framebuffer readback is THE risk — keep it rect-based and sparse
The PSX GPU copies framebuffer→VRAM and games sample it (fades, motion blur).
The GL renderer already limits uploads to dirty rects:

    glBindFramebuffer(GL_READ_FRAMEBUFFER, s_glVramFramebuffer);
    glReadPixels(readRect.x, readRect.y, readRect.w, readRect.h, ...)
        -- platform/native_renderer.c:1806-1816

D3D9 equivalent is `GetRenderTargetData` + `LockRect` — expensive on Xenon
(tiling + cache sync) and *especially* expensive under Xenia (host staging).
Rules for the 360 backend:
- Never read back more than the game actually consumed (dirty rects only).
- Batch all readbacks for a frame into one render-target resolve.
- If a frame does not consume framebuffer pixels, do zero readbacks.
- Profile with the existing `NATIVE_PERF_BUCKET_FRAMEBUFFER_READBACK` bucket
  from day one; budget: <3 ms/frame, warning threshold 5 ms.
- Reserve: readback one frame late (double-buffer) if a title screen effect
  ever forces a stall.

### 3.3 Draw call & state-change discipline
One `glDrawArrays` per `NativeRenderer_DrawTriangles` call today
(`native_renderer.c:2256`). Xenos eats thousands of draws per frame; Xenia's
per-draw translation does not, and PSX content is state-change heavy
(texture pages, CLUTs, semi-transparency, draw masks). Rules:
- Keep the vertex buffer as a per-frame ring; never re-upload the whole frame.
- Merge consecutive draws sharing (texture page, CLUT, blend, mask) — only
  *within* equal OT depth (painter's order must not change).
- Watch `NATIVE_PERF_BUCKET_DRAW_OTAG` + `RENDER_SUBMIT`; if Xenia draw-call
  bound, that is a Xenia artifact — check the same scene on hardware before
  optimizing further.

### 3.4 Audio runs on its own thread
The audio path is already producer/consumer: `NativeAudio_StreamCallback`
mixes SPU/XA into a queue (`SDL_GetAudioStreamQueued`, line ~2182). Port
shape for 360: XAudio2 source voice whose `OnBufferEnd` pull (or a dedicated
producer thread) drives the same mixing entry point. Net: the SPU/XA emulation
never runs on the game/render thread. Zero main-thread spikes from audio.
Keep 4-6 buffers in flight (~10 ms each at 44.1 kHz) for underrun safety.

### 3.5 IO / streaming: a solved problem by construction
PSX 2× CD ≈ 300 KB/s; 360 DVD ≈ 16 MB/s (RGH HDD ≫). All reads hit the
offline-cooked image beside the XEX via `CreateFileA`+`SetFilePointer` (no
runtime endian conversion anywhere — resolved at cook time). Level loads get
faster than original by an order of magnitude; nothing to optimize here beyond
not reading more than the game asks for.

### 3.6 Timing and pacing
`Platform_*` already paces VBlank emission with a remainder-exact
NTSC-derived tick count. 360 port: same math on `KeQueryPerformanceCounter`
(measured 50 MHz on Xenon = ~835,878 ticks/vblank), with the final ~200 µs
spin window replaced by a `KeStallExecutionProcessor` tail (no host spin).

### 3.7 Instrumentation from day one
The perf buckets (`native_perf.h`, 29 buckets: logic, OT parse, submit, draw,
readback, swap, vsync wait, audio vblank...) already partition the frame.
360 backend: keep `CTR_INTERNAL` instrumentation available, but emit a
compact 5-second summary line to the log (`game:\` / `cache:\`) instead of a
host UI. First on-hardware profile = M6 gate.

## 4. Risk ranking (spikes, not averages)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Framebuffer readback spikes (blur/fade effects) | high if naive | frame drops | §3.2: rect-only, batched, skipped when unused, budgeted |
| Xenia draw-call translation cost | high in emu | slow dev testing only | batching §3.3; validate on hardware |
| Audio mixing on main thread | medium if unthreaded | 1-4 ms spikes | §3.4: dedicated thread |
| VRAM upload churn (texture streaming scenes) | medium | upload stalls | coalesce dirty rects; single Lock/frame |
| MDEC video decode (intro FMV) | low | few ms in cutscenes | acceptable; measure at M3 |
| Xenia JIT overhead skewing measurements | certain | wrong conclusions | treat Xenia as correctness gate only |

## 5. Reserved optimizations (do NOT start early)

1. **VMX128 / AltiVec SIMD** for SPU mixing, OT packet decode and vertex
   transforms — after profiling identifies a real hot loop.
2. **Render-thread pipelining** (Xbox 360 supports command-buffered
   multi-threaded rendering): split render submission onto a second core for
   a full frame of overlap.
3. **Dynamic resolution**: drop the internal PSX-res target only if a scene
   can't hold 30 fps — unlikely given §3.1 fill costs.
4. **Precomputed VRAM/CLUT caches**: only if texture-state changes dominate.

Rule: every optimization above needs a profile that says the subsystem is hot
and a measurement that proves the fix. No speculative rewrites.

## 6. Benchmark ladder (what gets measured, when)

| Milestone | Measurement | Bar |
|---|---|---|
| M2 boot | init time, log integrity | boots, logs beside XEX |
| M3 title | frame time, readback ms, draw count | 29.9 fps held; readback <3 ms |
| M4 race (Palace/Skuld) | frame time under load; 1P/2P split | 29.9 fps held; no >40 ms frames |
| M5 menus+audio | underruns; input latency | zero underruns; ≤1 frame input lag |
| M6 RGH hardware | the same numbers on real Xenon | parity with Xenia-or-better; Xenia is not the target |

## 7. Non-goals (explicitly)

- Not chasing 60 fps: the game's logic, animation and vblank contract are
  30 fps (29.909). A 60 fps mode is a *separate* project (retail code changes),
  not a port concern.
- No runtime big-endian conversion (already solved offline by the cooker).
- No dynamic recompilation of game code: the decompilation IS the native code.
