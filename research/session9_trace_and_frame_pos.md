# Session 9: the quiet build, the run harness, and the ModelFrame.pos cook bug

_Session 9. Phase 0.1 + 0.3 of `IMPLEMENTATION_PLAN.md`, the Phase-2.2
single-instance cull trace, and the first real Phase-2 fix. Everything below is
backed by tool output (offline byte checks, guest logs, harness result dirs).

## 1. What was built (Phase 0.1, 0.3)

**Trace categories + buffered logging.** `platform/native_trace.c` (new,
C89-clean, compiled through both unity TUs) owns a tag -> category table and the
runtime mask; `platform/xbox360/native_xbox360_log.c` classifies every line at
the sink, drops the disabled categories, buffers the rest (64 KB, flushed on
fault/guard/error/phase/capture lines, on a 1 s heartbeat and on shutdown) and
takes a spinlock because the game thread and the audio callback thread both log.

- Categories: `boot packet cull title vram geom misc watch` (+ `all`, `none`,
  `ods`, `perf`). Default mask = `boot|title|vram` (`0x19`).
- The mask is a **runtime** property: `cache:\ctr360_trace.txt` is read at log
  init, so an experiment changes categories without a rebuild. The confirmation
  line `[trace] config ... -> mask=...` is classified essential.
- Measured effect: the quiet log for a full run is **634 lines** vs the 3.9 MB /
  93 k lines of session 8. The flood (`walk#N`, `pack:`, `pvr:`, `BeginFrame`,
  `DrawAllSplits:`, `w2`, ...) is gone from the default run.

**Run harness.** `tools/ctr360/run_harness.py`:
`python tools/ctr360/run_harness.py --secs 150 --trace cull --tag name`.
It asserts staged == cooked (md5), records the XEX hash/mtime and the probe
markers found in the linked PE (ImageXex compresses `default.xex`, so identity
comes from `Release/ctr360.exe`), writes/removes the trace config, runs Xenia,
then stores `guest.log`, a Xenia excerpt, every `*_vram.tga` with its
**decoded-pixel** pixelsum (same convention as `tga_to_png.py`, so values are
comparable across sessions) and wall times, plus `summary.txt`/`result.json`
with one outcome: `PASS / FAULT / PACKET_INVALID / STALLED / TIMEOUT /
ASSET_MISMATCH`. Results land in `build-360/results/<stamp>_<tag>/`.

Note: `perf` in the trace config turns on the existing `NativePerf` frame
capture, but `NativePerf_*` is compiled out unless `CTR_INTERNAL` is defined,
which the 360 project is not — so the keyword is inert in this build.

## 2. The ModelFrame.pos cook bug (the Phase-2 divergence)

`cook_disc.dram_model_anim_sites` registered each ModelFrame's origin as a
`(offset, 8)` site. `apply_swaps` reverses the **whole block** for a 2-element
site, so the four halfwords `x y z pad` came out *rotated*, not swapped:

```
retail (LE s16 x,y,z,pad)  81 ff 7e 01 81 ff 00 00   ->  (-127, 382, -127, 0)
cooked before the fix      00 00 ff 81 01 7e ff 81   ->  (   0, -127,  382, -127)   rotated
cooked after  the fix      ff 81 01 7e ff 81 00 00   ->  (-127, 382, -127, 0)       per-u16 swap
```

Every reader therefore got a *neighbouring coordinate*: the bbox corners built
by `RenderBucket_PackedFrameXY`, the split-line `frameY`, `RenderBucket_FrameZ`
and the DrawFunc `frameOrigin` (vertex positions). Verified offline with
`tools/ctr360`-style site discovery on the retail and cooked images: all 18
ModelAnim candidates in entry 514 now satisfy `cooked == byteswap16(retail)`.

Fix: the site is `(fo, 8, 2)` (per-halfword swap); `site_span()` was added so
the 3-tuple sites still flow through the overlap/avoid/round-trip gates
(`cook_disc.py --check` validates 496 regions and writes nothing).

**Reader side.** `RenderBucket_PackedFrameXY` read the pair with
`RenderBucket_ReadPackedWord` (byte-wise LE), which byte-swaps *both* halves on
Xenon when the data is host-order. It now composes the PSX packed word from the
fields, exactly like the port's other readers
(`(u16)frame->pos.x | ((u32)(u16)frame->pos.y << 16)`).

Two more instances of the same class were fixed while auditing the readers:

- `RenderBucket_GetCommandColor` / `GetIndexedColor`: the colour words are
  cooked host-order (the cmdlist pass swaps `ModelHeader.ptrColors`, and
  `CopyScratchColorCache` loads them with a plain `u32` load) — the LE reads
  byte-swapped every channel.
- `RenderBucket_RunInstanceSetupCallback`'s `LR1/LR2`: `idpp->halfVector` is
  written as plain `SVec3` fields by the game, so the pair is composed from the
  fields now.

## 3. Guest evidence (the instrument list from the session-7b plan)

`xs/xs2/xs3/xs4/xs5` (CULL) trace one instance end-to-end: raw frame-pos bytes +
both decodings, the packed corner inputs, the GTE RT/TR/OFX/OFY/H as loaded,
SXY0..2/SZ0..3 after each `rtpt`, and the folded bounds. `xq` prints the
identity of every instance offered at f>=500 (model id, name, flags, push
buffer), `xz` explains the `pb == 0` drops.

Before the fix (session 8 log, crate/copyright frames):

```
[trace] pj f=19 minXY=abf80000 minZ=00000014 sxy=03ff0100 sz=0
[trace] pk f=19 x=256..1023 y=1023..1023 z=0..0 h=320
```

After the fix (crate scene, f=61):

```
[trace] pj f=61 minXY=0010fd4c minZ=fffffea8 sxy=0061ffcd sz=1133 ...
[trace] pk f=61 x=-1024..1023 y=-1024..97 z=0..1133 h=320
```

The projected depth is no longer 0 and the Y bound is no longer pinned at the
clamp, i.e. the corners now carry real geometry.

## 4. The two blockers that keep the pixel gate from moving

**Pixels.** The scheduled captures still show the boot 2D pages: the f=12
capture is `6811c482ead27c0b` in every run of this session (quiet 90 s, quiet
240 s, all-trace). The 3D frames (f=205 crate, f=455 menu, f=505+ title) were
never reached, so the pixel gate has not been re-judged since the fix. The
capture list now also covers f=20/30/40/50/61/75/100 so a short run that gets
into the crate scene produces a comparable capture.

**Speed / stalls.** The quiet build does *not* reach the title in 90 s:

- `[timing] vblank wait=16.4ms` (60 Hz, normal), `[timing] endScene=0.0-0.1ms`,
  `present=0.0-3.2ms`, `swap=0.0ms` — the platform side is cheap.
- `[timing] framePeriod=2342.1ms` for the boot frames; guest CPU 0.19-0.31 s per
  3 s wall = the main thread is parked, not spinning.
- Runs are nondeterministic: the same build reached f=61 in one 45 s run, sat in
  the load's music-bank stage (5) for 240 s in another, and in stage 3 for 200 s
  in a third. `mbank` (stage 6) and `hb` (every 30 frames, with
  ms/state/stage/mode1/lvl) are the new instruments for this.
- With `--trace all` the frame time is dominated by the log itself: the OT walk
  emits `walk#N` lines per packet (`s_walkTrace < 120`, 15 k-line budget) and
  one bin chain is ~1000 entries long, i.e. ~8 k OT entries walked per frame.

**OT sizes are the next thing to look at**: a single `walk#11` chain spans
~1034 distinct 4-byte entries (`826E2284..826FFEB0` region) and the frame walks
bins 11..18, so the OT walk is ~8 k entries/frame. The OT pool is 0x8000 bytes
(8192 entries) for 1P (`MainInit.c`), so this is "the whole pool every frame" —
fine in principle, but it means any *oversized* per-instance range
(`range = maxDepth - minDepth`, `minDepth = minZ>>5 - 2`, `maxDepth = maxZ>>5 +
1`) is directly multiplied by the walk cost, and a saturated SZ (0xffff) yields
a ~2048-entry range per instance.

## 5. Open items for the next session

1. **Re-judge the pixel gate at a 3D frame**: get one run into the crate scene
   (f>=61) and compare `ctr360_crate61_f0061_vram.tga`'s pixelsum with
   `6811c482ead27c0b`. This is the acceptance signal for the frame-pos fix.
2. **The boot/load freeze, localized**: the guest stops right after
   `[trace] pi done` (the tail of `MainInit_JitPoolsNew`, called from
   `LOAD_TenStages` case 0 which then returns `loadingStage + 1`); the next
   `[trace] stage=1` never prints, the frame counter never advances and the main
   thread is parked. Stage 1 starts with the XA fade wait
   (`if (sdata->XA_State == XA_FADING) return loadingStage;`) after stage 0's
   `CDSYS_XAPauseRequest()`, and the XA assets are NOT staged — that wait is the
   prime suspect, followed by the post-load frame work (no probes there).
   Instruments ready: `mbank` (stage 6), `ndbox wait` (first-boot song wait, never
   entered in these runs), `pi done`, `hb` (frame heartbeat), `[timing]
   framePeriod`. Next: a phase marker between the load return and the frame
   render, and/or Xenia's debugger on the parked thread (the plan's lever #3).

   There is a **second stall mode**: `results/20260920-090951_cull9` (the run
   started before the short-run harness) got past the load (stage 0..9 all
   printed) and then stopped at f=21 **while spinning** (3.2 s CPU per 3 s),
   right after the `[trace] g0` marker at the top of `MainFrame`'s game-logic
   section. The `g1m..g7m` sub-phase markers are menu-gated
   (`gameMode1 & 0x2000`), so cutscene frames (gameMode1 = GAME_CUTSCENE)
   have no coverage there - widening those gates is the next instrument.
3. **Attribute the frame time** (0.7-2.3 s/frame in the quiet build): the
   platform sub-timings are small, so the time is in game/native_gpu code.
   `[timing] framePeriod=` is the new coarse instrument; `CTR_INTERNAL` would
   enable the per-bucket `NativePerf` capture. Prime suspect: the VRAM upload
   path — `UpdateVRAM` runs ~40 dirty rects per frame and each one
   `LockRect`s/`UnlockRect`s the VRAM texture (a render target under Xenia), and
   the mid-frame cost is not covered by the `endScene`/`present`/`swap` numbers.
4. **Nothing 3D is emitted even when draws run**: at the crate frames (f=13-60)
   `qall` shows 22 instances queued/frame and `rbe cas[0]` shows 4
   `RenderBucket_DrawFunc_Normal` calls/frame, but `DrawAllSplits: 0 split(s) at
   0 verts` every frame and the OT walk only contains the 2D present/pack quads
   (`pkt=7018F9F0 len=3`, `pkt=7018FA00 len=5`). So the DrawFunc path runs and
   emits nothing — `dw` (new, PACKET) prints the command list's count and first
   words per call to show whether the list is empty or the strip/prim emission
   bails.
5. **Per-instance projected bounds**: with the pos fix the corners are real, so
   the next divergence to compare is the *depth* row (RT3/TRZ -> MAC3 -> SZ) and
   the resulting OT ranges; `xs*` already prints the raw values per stage.
6. The `xq`/`xz`/`xs*` identity traces were never exercised in a run that
   reached f>=500 (no run did) — they are ready for the next one.
