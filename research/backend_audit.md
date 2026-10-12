# ctr360 Xbox 360 backend audit — renderer-focused

_Audit pass 2026-09-19. Scope: `platform/xbox360/` (5 `.c` files, 4,985 lines).
Read-only; no builds, no runs. Every claim below is tied to a `file:line`, a log line
with its line number, or a struct/API definition from the XDK at
`C:\Program Files (x86)\Microsoft Xbox 360 SDK` (21256.3) or from Xenia Canary
`canary_experimental@44cb87328` (the exact build in `xenia.log:1`)._

Artifacts cited:
- `platform/xbox360/native_xbox360_video.c` (2,687 lines) — D3D9 renderer
- `platform/xbox360/native_xbox360_platform.c` (565) — device bring-up, vblank/VSync, present
- `platform/xbox360/native_xbox360_input.c` (1,007), `..._audio_out.c` (355),
  `..._log.c` (177), `main_xbox360.c` (125), `..._compat.h` (69)
- `F:\downloads\xenia_canary_windows\xenia.log` (218,641 lines, run of Sep 19 10:11)
- `F:\downloads\xenia_canary_windows\cache\ctr360.log` (42,366 lines, guest log, same run)
- `platform/native_gpu.c`, `platform/native_libgpu.c`, `platform/native_renderer.c` (the
  portable layer the 360 backend implements; read for contract comparison)

---

## 0. Bottom line

| Area | Verdict |
|---|---|
| VRAM model (1024×512 linear G8R8 texture + CPU mirror + dirty rects) | Sound, faithful to the GL backend's contract |
| Frame flow guest-draw → swapchain | Complete end to end; 729 BeginScene / 728 present calls in the run |
| Present path (`PresentVRAMRect` / `PresentVRAMDisplay` / `SwapWindow`) | Works, but has 6 real correctness risks (§3) |
| `Resolve` readback path (`SyncGpuVRAMToCPU`) | **Never executed in the recorded run** — silently dead code path (§3.6) |
| The reported pitch-9552 / `PM4_DRAW_INDX(6,4,2)` failures | **Not produced by this backend at all** (§2) — they are the *stock 360 D3D9 runtime's* own display blit inside the command buffer our `Present` causes it to rebuild; Xenia refuses the render-target update because of guest register state. Decisive counter: 753 of our own 4-vertex quads drew in this run and **zero** failed. |
| Per-frame performance | Fine at 729 frames; three O(VRAM)-scale hazards exist on the save-state / framebuffer-feedback paths (§4) |
| Stubs / unfinished | Audio is a deliberate silent sink; 2 temporary diagnostics; several dead-but-necessary functions (§5) |

---

## 1. (a) Architecture map of the video backend

### 1.1 Object inventory

```
s_d3d / s_device                  Direct3D9 + D3DDevice          video.c:118-119
s_backBuffer / s_backBufferDepth  swap-chain back buffer = "GL framebuffer 0"   video.c:122-123
s_vram  { texture, surface, readbackTexture,
          cpuPixels[1024*512], cpuDirtyRects[128], gpuNewerTiles[8192], cpuDirtyRectCount }
                                                                 video.c:101-110
s_mainRenderTarget      = activeDispEnv.disp.w × .h, A8R8G8B8 + D24S8   video.c:113, 796-808
s_offscreenRenderTarget = activeDrawEnv.clip.w × .h, same                video.c:114, 2582-2615
s_nullTarget            = the back-buffer sentinel (never has a surface) video.c:115, 775-783
s_boundTarget           = which of the above is currently bound         video.c:124
```

The PSX VRAM is a **persistent 1024×512 `D3DFMT_LIN_G8R8` texture created with
`D3DUSAGE_RENDERTARGET`** (`video.c:973`), i.e. simultaneously a render target and a
sampled texture. Pitch is 2048 bytes (linear 16-bpp), a multiple of the 256-byte
linear alignment rule (comment `video.c:971-972`). Confirmed at runtime:
`xenia.log:3932 Created linear 1024x512x1 2D k_8_8 texture … (pitch 1024 …)`.

`cpuPixels` is the authoritative CPU-side mirror. `gpuNewerTiles` is a 128×64 tile
bitmap (8×8 tiles → 8,192 tiles → 8,192/32 = 256 u32 words, `video.c:64-69`) marking
VRAM tiles that the GPU wrote and the CPU mirror has not yet picked up.

### 1.2 Shaders

Nine stages, all HLSL compiled at runtime via `D3DXCompileShader` + `CreateVertexShader`/
`CreatePixelShader` (`video.c:482-526`), source strings at `video.c:234-476`:

| Stage | Source | Registers |
|---|---|---|
| PSX PS 4bpp / 8bpp / 16bpp | `x360_psx_common` + `x360_psx_sample{4,8,16}` + `x360_psx_main` (`video.c:876-883`) | `s0` VRAM, `s1` RG-LUT, `c0` bilinear, `c1` semitrans pass, `c2` maskset, `c3` output-STP, `c4-c7` dither |
| PSX PS 32-bit | common + `x360_psx32_main` (`video.c:885`) | + `c16` texel size |
| PSX VS | `x360_psx_vs` (`video.c:372-401`) | `c0-c3` projection |
| Quad VS (pack + present) | `x360_quad_vs` (`video.c:403-416`) | `c0` posFlipY |
| Pack PS | `x360_pack_ps` (`video.c:418-439`) | `c0` flipY, `s0` source |
| Present VS | `x360_present_vs` (`video.c:441-456`) | **`c1` sourceRect** |
| Present PS | `x360_present_ps` (`video.c:458-476`) | `s0` VRAM |

Register constants are `#define`d at `video.c:71-81`; note the explicit comment
`X360_PRESENT_VS_RECT_C1 1 /* c0 belongs to the fullscreen-quad helper */` — that is the
documented fix for the flat-fill bug (HANDOFF §5.4), and it is intact.

### 1.3 A frame, start to finish

```
guest: DrawOTag(ot)                                  [platform/native_libgpu.c]
  → NativeRenderer_UpdateVRAM()                      (flush pending CPU VRAM writes)
  → NativeGpu walker → AddSplit() per primitive      (native_gpu.c:796-860)
  → DrawAllSplits()                                  (native_gpu.c:948-…)
      → NativeRenderer_UpdateVRAM()                  (native_gpu.c:949)
      → NativeRenderer_UpdateVertexBuffer(verts,n)   (video.c:2315-2390)
      → for each split: DrawSplit()                  (native_gpu.c:871-931)
          → SetStencilMode / SetTexture / SetOverrideTextureSize /
            SetPSXDrawMaskSet / SetPSXTextureOutputSTP /
            SetupClipMode / SetOffscreenState / SetProjection /
            SetBlendMode / [SetPSXTextureSemiTransPass ×2] /
            NativeRenderer_DrawTriangles()           (video.c:2392-2414)
                → SetVertexShader(gte) SetVertexDeclaration SetStreamSource
                → UploadDitherTable()  ← per draw call
                → IDirect3DDevice9_DrawPrimitive(TRIANGLELIST, …)
      → optional GpuPackTextureToVRAM for framebuffer-feedback runs (native_gpu.c:795)
guest: DrawSync / EndFrame
  → Platform_EndScene()                              (platform.c:183-271)
      → NativeRenderer_EndScene()                    (restore offscreen, video.c:1912)
      → NativeRenderer_StoreFrameBuffer(disp)        (video.c:2562 → GpuPackTextureToVRAM)
      → NativeRenderer_PresentVRAMRect(disp)         (video.c:2617-2660)
      → NativeRenderer_EndGpuFrame()                 (no-op, video.c:1904)
      → NativeRenderer_SwapWindow()                  (video.c:2668-2687 → Present)
guest: VSync(n)                                      (platform.c:504-541)
```

Per-draw state changes are **not** fully redundant: `SetBlendMode` (`video.c:2104`),
`SetStencilMode` (`video.c:2068`), `SetScissorState` (`video.c:2038`), `EnableDepth`
(`video.c:2053`) all early-out on an unchanged value. `SetTexture` (`video.c:2202`)
early-outs on the *texture id* only (`video.c:2250`) but unconditionally re-sets the
pixel shader, the bilinear constant and the semitrans constant on every call
(`video.c:2210-2248`).

---

## 2. (b) The pitch-9552 / `PM4_DRAW_INDX(6,4,2)` failures — root cause

### 2.1 The premise in RESEARCH.md F2 is wrong: these are **not our draws**

RESEARCH.md F2 and HANDOFF "UNANSWERED QUESTIONS 3" both assert the failures are
"one of OUR draws (present or offscreen/Resolve pass)" binding a surface Xenia sees as
9552-pitch. The evidence contradicts that in three independent ways:

1. **No `CreateTexture`/`CreateDepthStencilSurface`/`Resolve` call appears anywhere near
   any failure.** Every surface creation in the whole run is one of five lines:
   `xenia.log:3916, 3926, 3928` (the runtime's own EDRAM render targets, 640×1024 and
   1280×2048) and `xenia.log:3932, 4063` (our `CreateTexture` for the 1024×512 VRAM
   texture and the 1280×720 back buffer — the latter is `CreateTexture`, not
   `CreateRenderTarget`, because that is how `GetBackBuffer` surfaces surface in Xenia).
   There is no pitch-9552 surface creation at all.

2. **The failures are bracketed by `Vd*` kernel calls on the *guest's own* display path,
   not by any of our probe lines.** Cluster at `xenia.log:85753` (guest frame 2):

   ```
   85741  d> VdRetrainEDRAM(00000000, …)
   85742  [trace] TenStages: stage 1 level=41
   85747  [trace] stage=1 d15=00000434 d64=00000484
   85752  G> Make 00001000 -> 00001000 (0b) coherent, action = N/A
   85753  !> Surface pitch 9552 larger than the maximum texture width 8192 specified by the guest
   85754  !> PM4_DRAW_INDX(6, 4, 2): Failed in backend
   85755  !> Surface pitch 9552 larger than the maximum texture width 8192 specified by the guest
   85756  !> PM4_DRAW_INDX_2(3, 8, 2): Failed in backend
   85757  [trace] frame: gamepad done f=2
   ```

   and at `xenia.log:96546` / `107329` / `150516` / `204432` the identical quadruple sits
   **immediately after `VdGetSystemCommandBuffer` + `VdRetrainEDRAM`** and immediately
   before the guest's next probe. Our renderer never calls `Vd*` anything —
   `grep Vd platform/xbox360/*.c` returns nothing.

   **But the `Vd*` path is *entered by* our Present, every present.** `VdGetSystemCommandBuffer`
   occurs **729 times** in `xenia.log` — exactly the 729 `BeginScene enter` lines in
   `cache\ctr360.log`. The distance from the nearest preceding `pvr: quad drawn` to each
   `VdGetSystemCommandBuffer` is a constant **3 lines** for all 729 (verified by
   index-matching on 20 consecutive samples). So:

   ```
   our IDirect3DDevice9_Present(s_device, NULL,NULL,NULL,NULL)   video.c:2680
     → Xenia Present → VdGetSystemCommandBuffer + VdRetrainEDRAM  (every present)
     → XDK runtime rebuilds its display+scaler command buffer
     → emits RB_SURFACE_INFO for its own fullscreen blit surface
     → surface_pitch = 0x2550 → RenderTargetCache::Update() returns false
     → the 6-index blit is dropped
   ```

   The pitch condition itself is **state-dependent, not per-present**: it fires on only
   **14 of the 729** present-driven `Vd*` runs. The 14 correlate with display/scaler
   reconfiguration — cluster 1 is at the first `VdSetDisplayMode` (`xenia.log:3918`),
   clusters 2–14 each sit immediately after a `TenStages: stage N` level-load line
   (`85742, 96535, 107318, …, 204421`). The offset from the preceding
   `VdGetSystemCommandBuffer` is **not** constant: cluster 2's two failures are 14 and 16
   lines after it, cluster 3's are 68 and 85 lines after — i.e. the runtime's blit is
   emitted later in the rebuilt command buffer on those frames, after other guest-visible
   work. So the correct statement is *"inside the command buffer that Present causes the
   runtime to rebuild"*, not *"immediately adjacent to the `Vd*` call"*.

3. **The decisive counter: 753 of our own fullscreen quads were drawn in this run and
   exactly zero produced a backend failure.** `cache\ctr360.log` has **753**
   `dfq: primitive up done` lines — the counter incremented by
   `NativeRenderer_DrawFullscreenQuad` (`video.c:2442`), which is the *only* path that
   emits a quad from this backend. They decompose exactly as
   `728 pvr: quad drawn` + `12 pack: before pack draw` + `13 LoadRenderTargetFromVRAM
   enter` = 753. Every one of those is a `DrawPrimitiveUP(TRIANGLELIST, 2, quad, …)` —
   a 4-vertex, 6-index-equivalent quad, i.e. **the exact primitive shape of the failure
   message**. None of them failed. `xenia.log` contains 50 pitch errors and 50 draw
   failures, in **50/50 strict line adjacency** (verified by index matching), i.e. a clean
   1:1 pairing of "refused surface update" → "the blit that needed it". A backend failure
   from one of our draws would appear as an unpaired line.

### 2.2 What actually raises the error

Xenia raises it in `RenderTargetCache::Update`
(`xenia/gpu/render_target_cache.cc`, canary_experimental):

```cpp
uint32_t pitch_pixels = rb_surface_info.surface_pitch;
if (!pitch_pixels) { is_rasterization_done = false; }
else if (pitch_pixels > xenos::kTexture2DCubeMaxWidthHeight) {   // 8192
  XELOGE("Surface pitch {} larger than the maximum texture width {} specified "
         "by the guest", pitch_pixels, xenos::kTexture2DCubeMaxWidthHeight);
  return false;                       // ← render targets are NOT updated
}
```

`RB_SURFACE_INFO.surface_pitch` is a 14-bit field (`registers.h`: `surface_pitch : 14`
at bit 0). **The reported value is masked before being compared, so 9552 is a genuine
0..16383 pitch value, not a truncated one.**

`pitch_pixels = 0x2550` is, read back through the register's field layout, exactly the
*whole register dword* `0x2550` with `msaa_samples = 0`:

| register bits | 0x2550 | field |
|---|---|---|
| 0..13 | 0x2550 → masked = 9552 | `surface_pitch` |
| 14..15 | 0 | `_pad_14` |
| 16..17 | 0 | `msaa_samples` = 1x |
| 18..31 | 0 | `hiz_pitch` |

i.e. a guest wrote `RB_SURFACE_INFO = 0x00002550`. In the *unmasked* interpretation this
is a plausible PSX-shaped pitch (`0x2550` low 14 bits), and in the *masked* interpretation
it is 9552 > 8192 → Xenia refuses the whole `Update()`, which is what drops **all** render
target handling for the draws that follow, not just the 4-vertex blit.

The companion `PM4_DRAW_INDX(6, 4, 2)` is emitted from
`COMMAND_PROCESSOR::ExecutePacketType3Draw` (`pm4_command_processor_implement.h:1150-1155`):

```cpp
if (!draw_succeeded) {
  XELOGE("{}({}, {}, {}): Failed in backend", opcode_name,
         vgt_draw_initiator.num_indices, uint32_t(vgt_draw_initiator.prim_type),
         uint32_t(vgt_draw_initiator.source_select));
}
```

`(6, 4, 2)` = 6 indices, `prim_type 0x04` = `kTriangleList` (`xenos.h:39-55`),
`source_select 2` = `kAutoIndex` (`xenos.h:785-789`). A 4-vertex, 6-index quad is the
canonical fullscreen-blit shape, and `(12, 4, 2)` (in the later clusters) is the same quad
as a 12-index list. The `PM4_DRAW_INDX_2(3, 8, 2)` lines are 3 indices / `prim_type 0x08`
= `kRectangleList` / `kAutoIndex` — a *different* runtime blit (the presentation rectangle),
not an alternative encoding of the failed one. All three shapes are runtime blits, not
game draws: CTR's own geometry is 3- and 4-vertex PSX primitives funnelled through
`DrawPrimitive(TRIANGLELIST, …)` (`video.c:2413`) from a locked vertex buffer, which is a
`kDMA`/`kAutoIndex` draw with index counts in the hundreds, and none of our draws use
`DrawPrimitiveUP` except `DrawFullscreenQuad`.

**Conclusion: every failing draw is a XDK-runtime display/scaler blit, and the failure is
Xenia refusing to update render targets because of guest register state.** The blit is
dropped; the EDRAM stays coherent (`Make 00001000 -> 00001000 (0b) coherent` immediately
precedes every cluster) and the guest's frame probes and the `frame 300/600 presented`
heartbeats all continue, so the dropped blit is not visible in this run. Boot is
unaffected — but for a different reason than RESEARCH.md F2 guessed: it is not *our* draw
that fails and gets rescued, it is the runtime's blit that fails and is simply dropped.

**Caveat I could not resolve:** the "1000 → 1000" coherence range is a 4 KiB region,
while a 1280×720 present is 3.7 MiB, so the `Make … coherent` line and the failing blit
are probably *not* the same operation. I therefore cannot claim the drop is harmless by
that argument alone — only that the run's guest-side progress is uninterrupted.

### 2.3 Which backend code path is responsible (the honest answer)

**None in `platform/xbox360/`.** The chain is:

```
our IDirect3DDevice9_Present(s_device, NULL,NULL,NULL,NULL)      video.c:2680
  → Xenia Present → VdSwap (xenia.log:708, once) / VdGetSystemCommandBuffer (729×)
  → XDK runtime rebuilds its display+scaler command buffer
      → VdRetrainEDRAM / VdSetDisplayMode / VdInitializeScalerCommandBuffer
      → emits RB_SURFACE_INFO = 0x2550 for its own fullscreen blit surface
      → surface_pitch = 9552 > 8192 → RenderTargetCache::Update() returns false
      → the blit's draw is refused; the render targets are not updated for it
```

What our code contributes is only the **frequency of the opportunity**: `Present` is
called once per `Platform_EndScene` (`platform.c:256-261`), and `Platform_EndScene` is
called from `Platform_EndFrame` (`platform.c:273-277`), which runs both from the guest's
frame loop and from `Platform_PresentVRAMDisplay` (`platform.c:279-284`, called from
`LOAD_TenStages.c:79` in the ND-box intro wait and `MainInit.c:725`). Every present
rebuilds the runtime's command buffer; the pitch error appears only when the guest's
display-environment state makes the runtime emit that stale pitch — which is why the 14
clusters line up with the `TenStages: stage N` level loads
(`xenia.log:85742, 96535, 107318, …, 204421`).

**Consequence for the fix list:** there is no backend-side fix, because there is no
backend-side bug. The only lever this project has is reducing the *number* of redundant
presents (§3.4 P1), which reduces the number of rebuild opportunities.

### 2.4 Does it matter, and what to do

It is a **Xenia-only artifact** of guest register state at display-mode changes. On real
hardware the real Xenos has no 8192 limit and the runtime's blit is fine — so this must
not drive any design decision, and above all must not be "fixed" with a Xenia-only hack
(HANDOFF §1 forbids that).

1. **Do not chase it as a renderer bug.** RESEARCH.md F2's "next step … find the texture-
   creation call that produced the 9552-pitch surface" is unfalsifiable — no such call
   exists in `xenia.log`. Update RESEARCH.md F2 and HANDOFF "UNANSWERED QUESTIONS 3" to
   record the finding above and close the thread.
2. **If it ever becomes visible** (a black or stale frame after a level load), the only
   available lever is to reduce redundant presents. `Platform_EndScene`'s
   `s_platformBeginScene` guard (`platform.c:191-194`) already suppresses a present for an
   `EndScene` with no matching `BeginScene`; a further cheap step is to skip the present
   when neither the display rect nor the frame's VRAM content changed. See §3.4 P1.

---

## 3. (c) The present path — how it works and where it is wrong

### 3.1 `PresentVRAMRect` (`video.c:2617-2660`)

```c
Platform_Log("[trace] -> UpdateVRAM from PresentVRAMRect\n");   // 2627  ← log BEFORE flush
NativeRenderer_UpdateVRAM();                                    // 2628
NativeRenderer_SetViewPortGL(presentViewport.x, .y, .w, .h, g_windowHeight);  // 2631
NativeRenderer_SetRenderTarget(NULL);                           // 2634 → back buffer
NativeRenderer_SetScissorState(0); EnableDepth(0); SetBlendMode(BM_NONE);     // 2637-2639
sourceRect = {displayX, displayY, displayW, displayH};          // 2642-2645
SetVertexShader(present VS); SetPixelShader(present PS);        // 2647-2648
SetTexture(0, s_vram.texture);                                  // 2650
SetVertexShaderConstantF(X360_PRESENT_VS_RECT_C1, sourceRect);  // 2652
NativeRenderer_DrawFullscreenQuad(1.0f);                        // 2655 (flip = 1)
s_previousShader = -1; s_lastBoundTexture = -1;                 // 2658-2659
```

The present VS reads `sourceRect` from `c1` (`video.c:442`), maps the quad's NDC to
`screenUV = pos*0.5+0.5`, then to `sourcePixel = sourceRect.xy + (screenUV.x, 1-screenUV.y)
* sourceRect.zw` and finally `uv = sourcePixel / (1024, 512)` (`video.c:451-453`). The
`1.0 - screenUV.y` plus the D3D viewport's top-left origin gives the "row 0 of the
back buffer is the visual top row" contract documented at `video.c:18-21`. The
`DrawFullscreenQuad(1.0f)` flip only mirrors `pos.y`, leaving `uv` alone — so the flip
constant is a no-op for the present pass and *is* used by the pack pass.

### 3.2 `PresentVRAMDisplay` — two layers, and the pinned branch bypasses the inner one

There are **two** functions with that name and they are on different layers:

- **`NativeRenderer_PresentVRAMDisplay`** (`video.c:2662-2666`) → logs
  `"[trace] EndScene: PresentVRAMRect next"` then `PresentVRAMRect(activeDispEnv…)`.
- **`Platform_PresentVRAMDisplay`** (`platform.c:279-284`):
  `PinVRAMDisplayFrames(1); BeginScene(); EndFrame();`

`Platform_PresentVRAMDisplay` is a live, load-bearing entry point — it is called from the
guest at `game/LOAD/LOAD_TenStages.c:79` (the ND-box intro song-sync wait, once per
`VSync(0)` iteration) and `game/MAIN/MainInit.c:725` (once per boot page). It does **not**
call `NativeRenderer_PresentVRAMDisplay`; it sets the pin counter and then runs the normal
`BeginScene`/`EndFrame` pair, which lands in the pinned branch of `Platform_EndScene`
(`platform.c:203-253`).

**Measured consequence:** `cache\ctr360.log` has 728 `pvr: viewport set` lines (one per
`PresentVRAMRect` call, `video.c:2632`) but only 716 `EndScene: PresentVRAMRect next`
lines — i.e. **12 of the 728 present passes were reached without going through
`NativeRenderer_PresentVRAMDisplay`**, and those 12 are exactly the pinned-display
presents (matching 13 `LoadRenderTargetFromVRAM enter` and 12 `pack: VRAM bound as RT`
lines). I verified the 12 are real orphans by index-matching: every one of the 12 has the
`pack: main RT restored (else branch)` → `-> UpdateVRAM from PresentVRAMRect` →
`pvr: viewport set` sequence with **no** `EndScene: PresentVRAMRect next` between them.

So `NativeRenderer_PresentVRAMDisplay` is **not dead** — it is the non-pinned path, and it
is dead only in the sense that this run always took the pinned path. The real finding is
the **layer split**: the pinned branch calls `NativeRenderer_PresentVRAMRect` directly
(`platform.c:228, 232`) and skips the wrapper, which means the wrapper's log line is an
unreliable frame marker. Cosmetic, but it will mislead the next person who greps it.

### 3.3 `SwapWindow` (`video.c:2668-2687`)

```c
s_presentedFrames++;
if ((s_presentedFrames == 1) || ((s_presentedFrames % 300) == 0))
    Platform_Log("[CTR Renderer] frame %d presented\n", s_presentedFrames);
if (s_device != NULL)
    IDirect3DDevice9_Present(s_device, NULL, NULL, NULL, NULL);
```

The heartbeat is a **present-call counter, not a frame rate** — HANDOFF says this and the
log confirms it: `frame 1` at `xenia.log:3910`, `frame 300` at `34703`, `frame 600` at
`63723` in a ~150 s run ≈ 4 presents/s… which is *not* 60 fps, because the run also
emits 729 vblanks and the frame limiter is off (`xenia.log:104 framerate_limit = 0`).
The gap is the guest spending most of its wall time in the level-load path; the counters
are literally "presents" and "vblanks" and must not be read as fps (skill rule).

`IDirect3DDevice9_Present` on 360 takes **no swap-chain/rect/dirty-rect/flag arguments in
the PC sense**; the D3D9 `Present` inline wrapper here is
`D3DDevice_Swap(pThis, D3DSWAP_DEFAULT)`-shaped. Passing four NULLs is therefore correct,
but note the wrapper ignores `pp.BackBufferCount`, `SwapEffect`, `hDeviceWindow`,
`Windowed` and `MultiSampleQuality` entirely (`d3d9types.h:2272-2277`, all marked
"Unused on Xbox 360"). **`pp.BackBufferCount = 1` and `pp.SwapEffect = D3DSWAPEFFECT_DISCARD`
(`video.c:567-569`) are therefore decorative** — worth a comment so nobody "fixes" them.

### 3.4 Correctness risks in the present path

| # | Risk | Evidence | Impact |
|---|---|---|---|
| P1 | **`Platform_EndScene` presents unconditionally whenever `s_platformBeginScene` was set, even if nothing was drawn.** | `platform.c:191-194, 256-261` | An extra `Present` per level-load → an extra `Vd*` command-buffer rebuild → an extra chance to hit the §2 pitch error. Cheap fix: only present when `s_presentedFrames` advanced or `activeDispEnv` changed. |
| P2 | **`NativeRenderer_ClearPresentationBars` calls `NativeRenderer_SetRenderTarget(NULL)` (binds the back buffer) and then four `Clear`s *before* `BeginScene`'s own bind of the main RT.** | `video.c:1136-1141`, called from `BeginScene` `video.c:1880` | Correct order today (bars → bind main RT at `video.c:1883`), but the *scissor state* is untouched: the four bar clears rely on `IDirect3DDevice9_Clear` honouring the D3DRECT and not the scissor. `NativeRenderer_Clear` (`video.c:1761`) explicitly notes this at `video.c:1111-1112`; `ClearPresentationBars` does **not** disable scissor first. On 360, `Clear` is documented as rect-limited and scissor-independent, so this is probably fine — but it is an unasserted dependency. |
| P3 | **`PresentVRAMRect` leaves the viewport set to the presentation viewport (e.g. 960×720) when it returns.** | `video.c:2631`; nothing restores it | The next frame's `BeginScene` re-sets it (`video.c:1895`), so no bug today. But `NativeRenderer_StoreFrameBuffer` runs *before* `PresentVRAMRect` in `Platform_EndScene` (`platform.c:256-257`) and the pack pass sets its own viewport (`video.c:2526`), so the ordering happens to be safe. Fragile. |
| P4 | **`SetRenderTarget(NULL)` early-outs on `s_boundTarget == &s_nullTarget` (`video.c:775`) and does not re-bind after an external RT change.** `SyncGpuVRAMToCPU` (`video.c:1421-1423`) and `GpuPackTextureToVRAM` (`video.c:2519-2521`) bind VRAM directly and set `s_boundTarget = NULL` (not `&s_nullTarget`), so the sentinel is correctly invalidated. **But** `SyncGpuVRAMToCPU` only restores the previous RT `if (previousTarget != NULL)` (`video.c:1461`) — if `s_boundTarget` was `&s_nullTarget` when it was entered, the restore is skipped and the *back buffer stays unbound-as-far-as-the-cache-knows* while VRAM is still bound. | `video.c:1417, 1461-1466` | Latent: a subsequent `SetRenderTarget(NULL)` would early-out on `s_boundTarget != &s_nullTarget`… actually `s_boundTarget` was set to `NULL`, so it would **not** early-out and would re-bind. The bug is the reverse: after restore-skip, the *device* still has VRAM bound while `s_boundTarget == NULL`, and the next `SetRenderTarget(&s_mainRenderTarget)` will see `s_boundTarget != target` and bind correctly. So it self-heals. Still worth fixing to `if (previousTarget == NULL) { SetRenderTarget(NULL); }`. |
| P5 | **`SetViewPortGL` is only used by the present pass** (`video.c:686-689`, sole caller `2631`). Every texture-destination pass uses raw `SetViewPort(x, y, w, h)` — `GpuPackTextureToVRAM` at `video.c:2526` passes the **VRAM** coordinates as the D3D viewport origin. | `video.c:2526` | This is intentional and matches the GL backend (`native_renderer.c` does `glViewport(x, y, w, h)` for the same pass) because D3D9 render targets share GL's bottom-left row origin for the pack's purposes… **no**: D3D9 render targets are top-left. The GL backend's `glViewport(x,y,w,h)` on a texture-attached FBO addresses rows bottom-up; the D3D9 `SetViewport(x,y,w,h)` addresses them top-down. The `x360_pack_ps` `flipY` uniform (`video.c:429`) exists precisely to compensate, and it is set to `flipY ? 1 : 0` where callers pass `1` (`video.c:2569`, `2579`). **This is the highest-value thing to verify visually** — if the VRAM image were row-mirrored, every PSX texture read would be upside-down and the already-verified SCEA/copyright pages prove it is not. Recorded as *verified by prior visual confirmation*, not re-derived. |
| P6 | **`EnableDepth(int enable)` ignores its argument and always writes `FALSE`.** | `video.c:2053-2066` (`D3DRS_ZENABLE, FALSE`) | Intentional (PSX has no Z-buffer) but the parameter is a lie; `s_previousDepthMode` still tracks it, so the early-out is meaningless. Harmless; should be `(void)enable`. |

### 3.5 `Resolve`-based readback: `SyncGpuVRAMToCPU` (`video.c:1367-1468`)

The GL backend does a partial `glReadPixels` here; the 360 version binds the VRAM surface
as RT, calls `IDirect3DDevice9_Resolve(D3DRESOLVE_RENDERTARGET0, &resolveRect,
readbackTexture, &destPoint, 0, 0, NULL, 0.0f, 0, NULL)` (`video.c:1434`), then locks the
readback texture and copies rows into `cpuPixels` (`video.c:1438-1448`). The XDK signature
is confirmed at `d3d9.h:3611`. Resolve rects are snapped to the 8×8 tile grid first
(`video.c:1407-1410`), matching the documented `D3DUSAGE_CPU_CACHED_MEMORY` linear
readback texture (`video.c:985`).

**This whole path never ran in the recorded run.** `cache\ctr360.log` has 13
`SyncGpuVRAMToCPU enter` lines, all of them the `DebugDumpVRAM` calls from the
pinned-display diagnostic (`ctr360.log:195, 222, 249, 276, 300, 553, 580, 607, 634, 658,
696, 6086, 11530`), and **zero** `readback: before resolve`, `readback: resolve returned`,
`readback: copy done` or `restoring RT` lines. Every one of those 13 entries returned at
the `needsReadback == 0` early-out (`video.c:1402-1405`) because `gpuNewerTiles` was
never set on a tile that mattered — i.e. the `Resolve` branch is **completely unexercised**.
Treat it as untested code, not verified code.

Two concrete risks inside it once it *is* exercised:

- `IDirect3DDevice9_Resolve` with `pDestTexture` = a `D3DFMT_LIN_G8R8` CPU-cached texture
  and source format = the VRAM RT format: the resolve format conversion is
  `D3DRESOLVE_PARAMETERS.ColorFormat` (`d3d9types.h:2539-2543`), passed as `NULL` here.
  A G8R8→G8R8 resolve with the RT bound at the same format should be a straight copy, but
  the RT is bound with **no depth/stencil** (`video.c:1422`) and the resolve is issued
  **without a `BlockUntilIdle`/fence**. On 360 the resolve is queued, and the immediately
  following `LockRect(…, D3DLOCK_READONLY)` on the destination must stall for it — the
  XDK guarantees this for `D3DUSAGE_CPU_CACHED_MEMORY` destinations, but there is no
  comment saying so. **Add the comment or add the fence.**
- The dest point is `(0,0)` (`video.c:1430-1431`) while the source rect is `readRect`,
  and the readback texture is the full 1024×512. So the resolved block lands at the
  *top-left* of the readback texture and the row copy reads `row * lock.Pitch` from there
  (`video.c:1444`). Correct, but only because the readback texture is never partially
  reused. A comment would prevent a future "optimisation" from breaking it.

### 3.6 Pinned-VRAM-display mode (`platform.c:203-253`)

When `s_pinnedVramDisplayFrames > 0`, `Platform_EndScene` takes an early-return branch
that (a) dumps a 48×14 ASCII brightness map of the display rect up to 3 times then every
300th frame (`platform.c:219-224`), (b) presents either the pinned rect or the display,
(c) `EndGpuFrame`, (d) `SwapWindow`, (e) decrements the pin counter, (f) logs timings.
This is the "screen-copy effect" path — the game calls it to hold a copied framebuffer
on screen. **It does not call `NativeRenderer_StoreFrameBuffer`** (`platform.c:255-257` is
in the *non*-pinned branch), so during a pin the main RT is not re-packed into VRAM. That
is almost certainly correct (the pin exists to show a *snapshot*), but the asymmetry
between the two branches is undocumented.

---

## 4. (d) Performance risks in the per-frame path

Measured from `cache\ctr360.log` timing lines (the only quantitative source):

```
[timing] endScene=0.0ms present=0.1ms endGpu=0.0ms swap=0.0ms total=0.1ms   (steady state, ×20+)
[timing] endScene=0.0ms present=3.2ms endGpu=0.0ms swap=8.6ms total=11.8ms  (frame 1)
[timing] vblank wait=16.3ms emit=0.0ms nextTargetIn=15.6ms                  (steady state)
```

The present path itself is 0.1 ms and `swap` is 0.0 ms once warm. The real costs are:

**R1 — `UpdateVRAM` is called 4–5× per frame and each call can `LockRect` the whole
dirty bounding box.** Call sites per frame: `DrawAllSplits` (`native_gpu.c:949`),
`libgpu.c:49` (DrawSync), `video.c:1414` (SyncGpuVRAMToCPU), `video.c:1887` (BeginScene),
`video.c:2480` (LoadRenderTargetFromVRAM), `video.c:2516` (GpuPackTextureToVRAM),
`video.c:2628` (PresentVRAMRect) — up to **7** in a frame with an offscreen pass and a
framebuffer-feedback run. Each call coalesces all pending dirty rects into one bounding
box and locks that box (`video.c:1293-1352`). If a `LoadImage` wrote a rect at (0,0) and
another at (1023,511), the bounding box is the whole 1024×512 texture and the upload
copies 1 MiB of rows (`rowBytes = (region.right-region.left)*2` per row,
`video.c:1348-1351`). The GL backend issues one `glTexSubImage2D` per rect; this backend
issues one lock over the bounding box. **Under a many-rect workload the 360 path is
strictly worse.** A `LockRect` on a `D3DPOOL_DEFAULT` texture also forces a full
resource rename on 360 (no partial update without a tiled layout), so the bounding-box
strategy can cost a full 1 MiB copy per call. Mitigation: keep an explicit
"few large rects" fast path and fall back to a full upload (which is what the
`NATIVE_VRAM_DIRTY_RECT_CAP` overflow at `video.c:1218-1226` already does) rather than
uploading a bounding box that is nearly the full texture anyway.

**R2 — `UpdateVRAM` is bracketed by 6 synchronous `Platform_Log` calls** (`video.c:1321,
1325, 1331, 1333, 1336, 1344, 1354`), each of which does `OutputDebugStringA` + `fputs`
to `stdout` + `fputs` + **`fflush`** to the log file (`native_xbox360_log.c:31-39`). The
`fflush` per line is the killer: every logged line is a synchronous write. The renderer
emits **~7,000 log lines per frame** at the current trace level in the worst case
(`walk#N` probe lines dominate: 13,444 `packet done` lines for 23 walks in the whole run,
plus 753 `dfq: flip const set` + 753 `dfq: primitive up done` for 753 fullscreen quads,
plus 5,096 `pvr:` lines). In Xenia each of those lines costs an `RtlInitAnsiString` +
`NtWriteFile` kernel transition (`xenia.log` is 218,641 lines, of which 84,724 are the
continuation `))` of a split `RtlInitAnsiString`). **On the console the same logging
remains, and `fflush`-per-line on a FATX/XTAF write path is the single largest avoidable
per-frame cost in this backend.** The trace probes are diagnostic scaffolding and should
be compiled out (`#ifdef CTR360_TRACE`) before the console performance milestone.

**R3 — `DrawTriangles` re-sets the whole pipeline per draw call.** `video.c:2407-2413`
sets vertex shader, vertex declaration, stream source, dither table (4 constant registers)
**and then draws**, for every split. `SetTexture` already re-set the pixel shader and two
constants (`video.c:2210-2248`) per split, and `SetPSXTextureSemiTransPass` is called
twice more in the two-pass semitrans path (`native_gpu.c:913-928`). None of these are
early-outed except `SetBlendMode`/`SetStencilMode`/`SetScissorState`. In the run's frame-2
walk there are 22 `DrawAllSplits` invocations and 753 fullscreen quads — i.e. the state
redundancy is currently masked by the low draw count. **At gameplay draw counts
(CTR: 500–1,500 splits/frame) the redundant shader + declaration + stream binds are the
first thing to profile.** Cheap wins: cache the last-set vertex shader/declaration/stream
in globals (the file already does exactly this for `s_lastBoundTexture`,
`s_previousShader`, `s_previousBlendMode`), and move `UploadDitherTable()` to
`BeginScene` (the table is a compile-time constant — `video.c:175-180` — and never
changes; uploading it once per frame instead of once per draw is free).

**R4 — `NativeRenderer_UpdateVertexBuffer` expands every vertex on the CPU, every upload.**
`video.c:2364-2386` converts 20-byte packed `GrVertex` → 64-byte `X360Vertex` with 12
float divisions (`/255.0f`) per vertex. At `MAX_VERTEX_BUFFER_SIZE = 1<<16`
(`native_renderer_types.h:23`) the worst case is 65,536 × (12 divides + 16 stores) ≈ 1 M
flops + 4 MiB of stores per upload. The GL backend feeds the packed struct straight to the
vertex fetcher with per-attribute types, so this is a **new 360-only cost**. Precompute a
256-entry `u8→f32` reciprocal table to kill the divides, and consider a
`D3DDECLTYPE_UBYTE4N`/`SHORT4N` declaration so the expansion can be done by the fetcher
(the PSX VS only uses `a_color` as `o.color = a_color; o.color.xyz *= a_texcoord.z`, so
normalised u8 attributes are sufficient — the only reason for FLOAT4 is the
`a_position.xy`/`a_texcoord` float math).

**R5 — `EnsureRenderTarget` logs 6 lines and is called 729×/run** (`video.c:710, 725,
728, 740, 748, 756, 761`), i.e. once per `BeginScene`. It early-outs before logging when
the size is unchanged (`video.c:720-723`), so in the steady state it is 2 lines
(`EnsureRT enter` at 710 and nothing else). **That `EnsureRT enter` line is unconditional
and fires 729×/run — delete it or gate it.** Same class: `BeginScene` emits 7 trace lines
(`video.c:1877, 1881, 1884, 1886, 1888, 1893`) + 2 from `LoadRenderTargetFromVRAM`
(`2477, 2479`), 9 per frame; `PresentVRAMRect` emits 8 (`2627, 2632, 2635, 2640, 2649,
2651, 2653, 2656`).

**R6 — `DebugDumpVRAM` (`video.c:1511-1639`) is a full nested-loop VRAM scan.** It walks
`clippedW × clippedH` pixels for the nonzero count (`video.c:1530-1539`), then walks them
**again** for the histogram (`video.c:1562-1604`), and `DebugDumpVRAMRaw` (`video.c:1478-
1504`) walks the entire 524,288-pixel mirror. The pinned-display branch calls **both**
(`platform.c:221-222`) every 300th frame. That is ~1.5 M pixel visits + 14 log lines on
those frames. Diagnostic only; must not survive to the console build.

---

## 5. (e) Stubs, TODOs, unfinished parts

| # | Item | Location | Status |
|---|---|---|---|
| S1 | **Audio output is a deliberate silent sink.** A worker thread pulls PCM at the SDL contract rate and discards it; `SDL_PutAudioStreamData` only accumulates a counter; `SDL_GetCurrentAudioDriver()` returns `"xbox360-silent"`. | `native_xbox360_audio_out.c:1-15, 49-85, 239-253, 307-310` | Documented as "milestone 3 scope"; XAudio2 is named as the next milestone. The pull thread is correctly affinity-pinned off the main loop's core (`:144`, `XSetThreadProcessor(thread, 4)`). **This is the largest genuine stub in the backend.** |
| S2 | `SDL_GetAudioStreamQueued` returns a *simulated* device consumption model, not a real queue depth: `pendingBytes` is decremented by `consumedPerPull = freq*ch*2*3ms/1000` every 3 ms regardless of what was submitted. | `native_xbox360_audio_out.c:56, 75-80` | Fine for the emulation's underrun bookkeeping (which is what it is for) but it will read as "the device is keeping up" even if a future XAudio2 path drops data. |
| S3 | `NativeRenderer_EndGpuFrame()` and `NativeRenderer_FinishGpuMeasurements()` are empty. | `video.c:1904-1910` | Intentional (the GL backend uses them for perf scopes). The 360 backend has **no** `NativePerf_BeginScope/EndScope` calls at all, unlike `platform/native_renderer.c` (`NativePerf_BeginScope(NATIVE_PERF_BUCKET_DRAW_ALL_SPLITS)` in `native_gpu.c:952`, `NATIVE_PERF_BUCKET_FRAMEBUFFER_STORE` at `native_renderer.c:1983`). So `native_perf` instrumentation is compiled in but never fed. |
| S4 | `NativeRenderer_DestroyTexture(TextureID)` is an empty function with only a `-1` guard. | `video.c:2307-2313` | **Not a leak**: the backend never creates per-PSX-texture D3D objects — every PSX texture is the single `s_vram.texture` (`native_gpu.c:816`). Correct by construction, but it means the "TextureID" space is overloaded (`s_vram.texture`, `s_whiteTexture`, or a caller-provided override) and `DestroyTexture` silently ignores all of them. Should be `(void)` + comment. |
| S5 | `NativeRenderer_PushDebugLabel` / `PopDebugLabel` are no-ops. | `video.c:2416-2423` | The 360 has `D3DPERF_*`; unused. |
| S6 | `NativeRenderer_SaveVRAM` ignores `x`, `y` and `bReadFromFrameBuffer` and always writes the full 1024×512 in BGR-16 TGA order with the PSX word written raw. | `video.c:1833-1868` | Deliberate (`(void)` casts at `:1840-1842`) but it means the function's name lies about its arguments. It also does an unconditional full-VRAM `SyncGpuVRAMToCPU(0,0,1024,512)` (`:1844`) — an expensive forced readback — before every save. |
| S7 | Two `TEMPORARY` diagnostics remain in the shipped path: `DebugDumpVRAMRaw` / `DebugDumpVRAM` (`video.c:1475, 1509`) and the pinned-display dump block (`platform.c:211`). | — | Explicitly marked temporary; both are wired into the *normal* present path via the pinned branch. |
| S8 | `NikoGetEnterKey()` returns 0 with a "no host keyboard" comment. | `platform.c:341-345` | Correct stub. |
| S9 | `NativeRenderer_ResetDevice` (`video.c:635-639`) only updates the viewport + swap interval; it does **not** recreate the render targets or the VRAM texture after a device reset. | `video.c:635` | On 360 there is no `D3DERR_DEVICELOST`/`Reset` flow, so this is fine — but the function silently does less than its name implies and is only called from `InitialisePSX` (`video.c:1016`). |
| S10 | `Platform_PollHostEvents` calls `XLaunchNewImage(NULL, NULL)` then spins forever. | `platform.c:310-332` | Correct for the quit chord; note it calls `Platform_LogShutdown()` *before* the launch, so the last lines of any quit are lost. |
| S11 | No `#ifdef` guard around the ~7,000-lines-per-frame trace scaffolding. | `video.c` passim, `platform.c:244-251, 263-270, 495-501, 518-537` | Not a stub, but the highest-leverage unfinished *task* in the file (see R2). |
| S12 | `main_xbox360.c` has no error path after `Platform_Init` failure: it logs "Platform ready" and proceeds into `CTR_Main()` even when `Platform_Init` returned early (it is `void`). | `main_xbox360.c:112-113`; `platform.c:116-128` returns without setting `s_platformInitialized` | If D3D9 device creation fails, the game runs to `CTR_Main` with a null device. Every renderer entry point guards `s_device != NULL`, so it degrades to a black screen + a log line rather than a crash — acceptable, but "Platform ready" is printed unconditionally and is a lie on that path. |

---

## 6. Cross-check against the two source logs (what the run actually proves)

| Observation | Evidence |
|---|---|
| 729 `BeginScene enter` / 728 `pvr: quad drawn` | `cache\ctr360.log` line-shape histogram |
| 6 `frame N presented` heartbeats (1, 300, 600 ×2 each — the log is written twice per line by Xenia's two `RtlInitAnsiString` copies) | `xenia.log:3910, 34703, 63723` |
| 753 `dfq: flip const set` / `primitive up done` pairs = 753 fullscreen quads in the whole run (present + pack) | `cache\ctr360.log` |
| 0 parse errors, 0 `MAX_VERTEX_BUFFER_SIZE reached`, 0 `lock failed`, 0 `shader compilation failed` | `grep` over both logs |
| All 9 shaders compiled (`shader failures: 0`) | `[CTR Renderer] PSX pipeline ready (shader failures: 0, vertex buffer: ok)` |
| VRAM texture created as `linear 1024x512x1 2D k_8_8` (G8R8) at `0x1EDB4000`, pitch 1024 | `xenia.log:3932` |
| Back buffer created as `tiled 1280x720x1 2D k_8_8_8_8` at `0x1F6F8000` | `xenia.log:4063` |
| VRAM mirror at boot is 352,256/524,288 nonzero, all sampled words `8000` (PSX black) | `cache\ctr360.log:299-302` |
| Pinned display dumps show real content after the intro page moves: `ffff:4021`, `bdef:893`, `d6b5:245` | `cache\ctr360.log:660` |
| The `Resolve` readback path never executed | 13 `SyncGpuVRAMToCPU enter`, 0 `readback: before resolve` |
| 14 pitch-failure clusters ↔ 729 presents: 1 cluster per display-mode transition, not per frame | §2.1 |
| 753 of our fullscreen quads drawn, 0 backend failures; 50 pitch errors ↔ 50 draw failures in strict 1:1 adjacency | `cache\ctr360.log` `dfq: primitive up done` = 753 = 728 pvr + 12 pack + 13 loadRT; `xenia.log` index match |

---

## 7. Recommended fix order (renderer only)

1. **Gate the trace logging behind `#ifdef CTR360_TRACE`** (R2/R5/S11). This is the single
   biggest console-side cost and it is pure deletion.
2. **Move `UploadDitherTable()` out of `DrawTriangles`** into `BeginScene` (R3) and cache
   the vertex shader / declaration / stream source (R3).
3. **Replace the 12 float divides per vertex** in `UpdateVertexBuffer` with a 256-entry
   reciprocal table, or move the normalisation into the vertex declaration (R4).
4. **Assert or fence the `Resolve`→`LockRect` ordering** and restore the RT explicitly when
   `previousTarget == NULL` (P4, §3.5).
5. **Make the pinned branch log a distinct frame marker** (or call
   `NativeRenderer_PresentVRAMDisplay` from it) so the 716-vs-728 discrepancy stops
   misleading greps (§3.2). Do **not** delete `NativeRenderer_PresentVRAMDisplay` — it is
   the live non-pinned path.
6. **`UpdateVRAM`: prefer "upload the whole texture" over "upload a bounding box that is
   nearly the whole texture"** once the box exceeds some fraction (e.g. 1/4) of the
   texture (R1).
7. **Update RESEARCH.md F2** to record that the pitch-9552 errors are the stock runtime's
   display blit, not a ctr360 surface — and drop the "find the texture-creation call"
   next-step as unfalsifiable (§2.4).

---

## 8. What I could not determine

- **Whether the pitch-9552 condition is guest-driver code or XDK runtime code.** All I can
  prove is that no ctr360 call site is adjacent to the failure and that the failing
  primitive shape (6 indices / `kTriangleList` / `kAutoIndex`) is a blit, not a game draw.
  Naming the exact writer of `RB_SURFACE_INFO = 0x2550` needs a Xenia GPU trace
  (`trace_gpu_prefix`), which the task forbade running.
- **Whether the `VdRetrainEDRAM` + `VdGetSystemCommandBuffer` pair is *caused* by our
  `Present` or merely *observed* next to it.** The correlation is 14 clusters ↔ 729
  presents, so it is not per-present; I could not isolate which present triggers the
  scaler rebuild without a trace.
- **Whether `Present` with four NULLs is byte-identical in behaviour to the XDK's
  `D3DDevice_Swap`.** The XDK ships only headers, not the D3D runtime source, so the
  semantics of the four unused parameters cannot be confirmed from the SDK on this machine.
- **The D3D9 `Clear`-vs-scissor interaction on 360** (risk P2). The XDK has no
  documentation tree (`SDK\doc` contains a single file); I could not confirm that a
  rect-limited `Clear` is scissor-independent from first-party docs, only from the code's
  own comment at `video.c:1111-1112`.
- **Actual per-frame draw counts** — the run only reached frame 13 with real content, and
  the walker probe caps (60/walk) mean the `walk#N` counts in `cache\ctr360.log` are
  censored. So R3/R4 are *structural* performance risks, not measured ones.
- **The console-side cost of `fflush` per log line** — Xenia's file path is a host `FILE*`,
  not the 360's XTAF/FATX write path, so the 0.1 ms present times above do not bound the
  console cost of R2.
