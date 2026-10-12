# ctr360 — HANDOFF (current state of work)

## Current checkpoint — 2026-10-11, HD hardware candidate ready

The user reports the port fully playable and requests 720p, smoothing, a 60 FPS
target and true widescreen. The new candidate rasterizes at 1280x720, expands
horizontal world projection/visibility for 16:9, filters decoded world texels
and applies edge smoothing. Authored UI retains its 4:3 aspect. Single-player
race rendering uses midpoint camera/instance poses at a 60 FPS target while
simulation/input/game timers stay at the existing cadence. Menus, loading,
pause, adventure hubs, end-of-race menus and split-screen keep the original route.

Read `research/20261011_hd_graphics.md` for implementation boundaries, Xbox 360
EDRAM/shader checks, actual visual evidence and remaining validation. The user
will test on physical hardware; console performance is not yet verified.
Memory-card saves report full and remain open. An unintended Adventure route
test logged packet errors; baseline isolation of that separate finding is pending.

Hardware ZIP: `build-360/releases/ctr360-hd-720p-20261011.zip`, including the
tested default.xex, unchanged cooked assets/ctr-u.bin, README, identities and
an inactive graphics-settings example. ZIP members/CRC and both XEX/image
SHA-256 were verified after compression. The ordinary complete staged folder
is `build-360/xex/dist/`. No controller script or capture settings are installed.
Xenia stopped; normal player controls are restored.

Visual test `20261011-hd-candidate-3`: 70 seconds requested, 74.04 wall, zero
faults/packet errors. Actual enhanced 1280x720 captures show crate characters,
countdown, race HUD, attached wheels, acceleration and steering. Paired `_i` and
`_f` frames show distinct intermediate/current poses with coherent wheel geometry.
Their inspection caught and repaired a prior missing countdown/stale banner
despite clean packet logs. Production rebuild changes only an aspect comment.

Final `20261011-hd-production`: 70 seconds requested, 73.98 wall, exit 0,
zero faults/packet failures, video/audio file captures disabled. Normal menus
load Crash Cove Time Trial and scripted inputs drive it. Steady windows report
59.14–60.01 render FPS (aggregate 59.75) and 29.57–30.00 simulation FPS;
the initial level window settles at 48.81/29.69. Audio output has zero device
failures. These rates validate emulator pacing, not physical console performance.

Release builds with zero errors and 85 warnings. Full mirror regeneration from
an absolute root passes 246 units/2532 hoists, zero manual-review notes,
designators or host AST errors; audited MainHD regeneration and XDK-only
compilation pass. Actual midpoint/state fixture and real Xbox 360 shader
compilation pass. Main color/depth and VRAM bridge occupy 1856/2048 EDRAM tiles.

Current tested identities:

- XEX: `0941d2682d5c150ba63ea9abeb916f8816b7f80e087b117bdff2fa2b9a0837c8`
- PE: `73c15b05f49d0aae3a74a6989e837457a7d114ca4415e3f9a54bc53e48f5a094`
- Cooked/staged image: `e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0`
- Prior accepted playable XEX backup: `build-360/results/20261011-playable-baseline/default.xex`
  (`b1c5de4d95fec71350ca8004a7184f9abf65a33c5267067c2b4f9902b3189e74`).

**New capture contract:** `ctr360_output_fNNNN_i/f.tga` is the final enhanced
post-AA backbuffer, ordinary 24-bit 1280x720 TGA. Use its same-size PNG for HD
review. `ctr360_display_fNNNN.tga` now represents only the legacy VRAM side
channel. Whole legacy VRAM remains packed textures/CLUTs, not a framebuffer.
Never infer graphics success from counters, checksums or zero faults alone.

Build: `bash tools/ctr360/build_xex.sh Release`; no manual mirror edits.
Header/generator/broad source changes require full absolute-root regeneration
and passing host AST checks. References under ../repos remain read-only.
Preserve extensive existing uncommitted work.

Tests always run minimized, only for the required duration, awaited inside tools,
archived after shutdown. Do not poll live Xenia, edit sleeping runners, modify
live staged assets/XEX or start a PSX reference emulator. The current fast normal
menu/drive script is `20261011-hd-fast-pad.txt`; the one-run `20261011-hd-run.py`
restores inputs/settings in finally. Capture mode 1 includes legacy diagnostics,
2 only enhanced output, 0/absent disables capture readbacks. Production/hardware
packages contain no captures or scripts. Optional assets/ctr360_graphics.txt
keys interpolation/texture_filter/edge_aa accept 0/1, default 1; restart to apply.

Next: collect the user's real-hardware result, then scope any console issues,
broader tracks/modes/effects and the memory-card save failure. A full lap and
complete effect/mode coverage are still pending for this candidate. Prior paused
checkpoint/prompt are archived in research/20261011_pre_hd_checkpoint.md and
research/next_session_20261011_pre_hd_archive.md. Older notes below are historical.

---

## Historical checkpoint — 2026-10-11, player inputs restored; paused

**The user confirmed all reported graphics fixes, including the bursting crate
and race flyby, and requested a pause.** Crash Cove Time Trial loads through
ordinary menus, and Crash's wheels remain attached during acceleration and
turning. Track selection has its course preview again. Earlier title/flag,
menu text, audible title music and performance were confirmed by the user.
Do not start more work or tests until requested.

The final minimized test is `build-360/results/20261011-time-trial-scene-transforms/`:
150 seconds requested, 154.03 seconds wall time, exit 0, zero logged faults and
zero packet failures. Xenia stopped. The final sustained 2,000-frame window
is 29.91 FPS. Its `result.json`, guest log, final displayed captures and title/
race WAVs are archived. The staged `ctr360_pad_script.txt` is absent, and a
post-run check found zero Xenia processes. Normal physical-controller input
is restored for the next launch. The script loads only at XEX initialization,
so shutdown as well as script removal is required to restore player control.
A separate Xenia process appeared after that cleanup (PID 17696, started
2026-10-11 10:58:15 local). It was left running; no new test was launched by
the agent. The pad script remains absent for that later launch.

The wheel fix reads LE rotation words explicitly and uses the numeric signed
low half for wheel centers/hazard offsets. Scene repairs correct raw fly-in
path reads, native vector/GTE transfer, LE cutscene model scales/matrix stores,
particle matrix packing, split-polygon texture halves and preview tpage reads.
Read `research/20261011_wheels_scenes.md` for scoped repairs and test evidence.
The prior loader/racer cooker and HUD packet repairs remain intact; assets
were not recooked during the wheel/scene fixes.

Actual final display frames 350/370 show coherent burst characters and karts;
1000 shows the course preview; 1933 shows attached wheels while turning.
Flyby frames 1513/1588 show close track surfaces; whole flyby animation
acceptance comes from the user's live confirmation. Do not infer visual success
from frame counters, checksum changes or the absence of faults.

Full regeneration `20261011-scenes-transforms-mirror.log` passes 2,532 hoists,
zero manual-review notes, zero leftover designators and zero host syntax
failures. Release builds with zero errors and 85 warnings. The solid/reflection
wheel, scene interpolation/scale, and native camera/bone transfer fixtures pass.
There are no source edits after the final passing build/run.

Current tested SHA-256 identities:

- XEX: `b1c5de4d95fec71350ca8004a7184f9abf65a33c5267067c2b4f9902b3189e74`
- PE: `c15075be610f9006c3cc3edcb55df03cdb5472f96e952423489a62cb51e26471`
- Cooked and staged image: `e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0`

Earlier `20261011-time-trial-drive-hud` and `20261011-demo-racer-hud` runs
verified loading/movement/HUD at about 30 FPS, but their captures still lacked
wheels. Their earlier broad graphics assessment is superseded. The intermediate
wheel test passed wheel attachment; the next scene test restored the preview
but still failed opening/flyby review. Preserve those results as historical
evidence rather than treating every zero-fault run as visually correct.

Race audio is captured from the game's own mix: ten seconds, 44.1 kHz stereo,
441,000 frames; final PCM has 881,235 nonzero samples, peak 6,622 and RMS
1,032.77. Device playback reports zero failures. Detailed race sound quality,
a full controlled lap, broader tracks/modes/controls and physical Xbox 360
hardware have not been separately validated. When resumed, leave this passing
build intact and agree the next milestone with the user.

Build: `bash tools/ctr360/build_xex.sh Release`. The mirror syncs audited changed
units and Xbox video. Headers/generator/broader source edits require full mirror
regeneration with an absolute source root and successful host AST parsing.
Never hand-edit the mirror. XDK-only files compile directly through MSBuild.

Test: `CTR360_READBACK=full bash tools/ctr360/run_xenia.sh <seconds> '<pattern>'`.
Always launch minimized, await completion inside tools and archive after stop.
Do not repeatedly poll live Xenia, edit its sleeping shell script, replace live
staged assets/XEX, or open a separate PSX emulator. Final `ctr360_display_fNNNN.tga`
is the displayed rectangle in ordinary 24-bit pixels; whole legacy VRAM dumps
include packed textures/CLUTs and are not ordinary framebuffer images.

Ordinary automated pad inputs are authorized for future iteration. The helper
`build-360/results/20261011-scripted-run.py` stages a test script for one run and
restores/removes it in `finally`. `20261011-time-trial-scenes-pad.txt` dwells on
the preview before normal Time Trial loading and acceleration/steering. No
menu, loader or gameplay flags are bypassed. Do not leave a script installed
when returning control to the user.

Reference repos under `../repos` are read-only. Preserve existing uncommitted
work. Read `research/20261010_flag_loading.md` for prior loading/audio/HUD work
and `research/20261009_graphics_debug.md` for representation/capture contracts.
The superseded checkpoint/prompt are archived in
`research/20261011_pre_wheel_checkpoint.md` and
`research/next_session_20261011_pre_wheel_archive.md`. Older checkpoints below
are historical.

---

## Historical checkpoint — 2026-10-09

**The crate graphics now render coherently beyond copyright.** The current
Release XEX builds with zero errors (81 warnings). Final display captures at
frames 60 and 120 show an open crate and a clean Naughty Dog front face with
readable textures. These are actual decoded display rectangles, not full VRAM
memory dumps. The completed 250-second verification run is archived under
`build-360/results/20261009-clock-*`.

Read `research/20261009_graphics_debug.md` for the current representation
contract, evidence, fixes, and concrete remaining faults. The older state below
is historical: its identical-framebuffer, empty-geometry, and early-stall claims
do not describe this build. A changed checksum alone is never visual acceptance.

Important repairs: raw LE camera/sky/animation deltas; normalized shader dither;
GPU control-command byte layout; blur packet XY/RGBC fields; average blending;
and an old probe insertion that made `clockSend--` unconditional. That u8 timer
wrapped zero to 255 and enabled unwanted blur despite camera flags being zero.
Deleting the misplaced probes restored the original conditional and removed
the repeated-image trails.

Build with `bash tools/ctr360/build_xex.sh Release`. It reuses the validated
mirror and regenerates only audited changed units or copies the Xbox video
source. A full mirror is needed for headers, generator changes, or other units;
use an absolute source root. Failed AST/hoist parses now stop generation. The
XDK sources are already MSVC C89 and are compiled by MSBuild, not host clang.

Test with `CTR360_READBACK=full bash tools/ctr360/run_xenia.sh 140 '<pattern>'`.
Xenia launches minimized and is stopped by the script. Final presentation
captures are `cache:\ctr360_display_fNNNN.tga`, ordinary 24-bit top-origin TGA.
`ctr360_main_fNNNN.tga` can precede a framebuffer-feedback effect; prefer the
display captures when judging output. Full readback slows these diagnostic
runs; the old frame-rate estimates below are obsolete. Do not edit a running
shell script or open a separate reference emulator.

Next work: later flag coloring and the loader's repeated stage 6, then title,
performance, audio, input, and racing validation. Track mesh payloads need an LE contract
before racing; the crate level has no mesh. The animation-word store and packed
clear-color store also have concrete BE field-layout faults recorded in the
research note. No gameplay, flag transition, audio, or input milestone has been
verified yet.

---

## Historical checkpoint — 2026-09-20

_Updated 2026-09-20 (session 9). Supersedes all earlier HANDOFF content. For a
fresh-context session: read this file, then `research/session9_trace_and_frame_pos.md`
(infra + the ModelFrame.pos cook bug + the new instruments + the two blockers),
then `research/visual_gate_plan.md` (session-7b: the log-vs-pixels state, the
cull blocker, the ranked plan), then `research/gte_endianness_findings.md`
(sessions 6-7: the GTE byte-order bug class, the f=205 wedge, the store-order
fixes).
Recent commits: `89217da` (trace categories + buffered logging, run harness),
`ea9d83a` (ModelFrame.pos cook fix + reader conventions), `7ddad82` (boot-freeze
and empty-emission probes, harness early stop + minimized launch), `28be0c0`
(the second stall mode), plus the session-6/7/8 commits before them._

---

## 0. What this is, and how to operate

**Project.** Source port of Crash Team Racing (PSX) to native Xbox 360 (Xenon).
Decompiled game code in `game/` compiles for the 360 with `CTR_NATIVE`; `platform/` is the
portable native layer; `platform/xbox360/` is the 360 backend (D3D9, official XDK
21256.3). Goal: boot to the title screen, then gameplay.

**Paths.**
- Repo: `F:/downloads/temp/python/hermes/ctrport/ctr360` (git)
- Retail dump (user's own): `../CTR - Crash Team Racing (USA)/`
- Cooked image: `build-360/ctr-u-360.bin`; staged asset: `build-360/xex/dist/assets/ctr-u.bin`
- Build tree (what compiles): `build-360/gen` (generated from the repo; see §6)
- XEX: `build-360/xex/dist/default.xex` (+ `default.xdb`, symbols)
- Reference ports (read-only, for diffing): `../repos/ctr-native`, `../repos/CTR-in-C`
- Xenia Canary: `F:/downloads/xenia_canary_windows`; logs `cache/ctr360.log` (guest),
  `xenia.log`. `run_xenia.sh` deletes the guest log each run. Logging goes to `cache:`.

**Commands.**
- Build: `bash tools/ctr360/build_xex.sh Release` (trust its FATAL gates; grep the built
  `Release/ctr360.exe` for a new probe string to confirm build identity)
- Regen mirror: `python tools/ctr360/build_360_mirror.py --root . --out build-360/gen` (~25-28 min; NEVER hand-edit generator anchors)
- Probes pre-check: `python tools/ctr360/check_probes.py`
- Cook: `python tools/ctr360/cook_disc.py --check` (validate, no write) / `--out build-360/ctr-u-360.bin`
- Stage: `bash tools/ctr360/prep_test.sh --cooked build-360/ctr-u-360.bin`
  (ALWAYS `--cooked`; then md5-assert `build-360/ctr-u-360.bin` == `build-360/xex/dist/assets/ctr-u.bin`)
- Run (preferred): `python tools/ctr360/run_harness.py --secs <ceiling> --until-frame <N>
  --trace "<cats>" --tag <tag> [--expect-frame <N>]` — launches Xenia **minimized**
  (`SW_MINIMIZE`, so it does not steal focus), kills the run the moment frame N appears in
  the guest log, and writes `build-360/results/<stamp>_<tag>/` (guest log, build/asset
  hashes, per-capture decoded pixelsums + wall times, one outcome line). `--trace` writes
  `cache:\ctr360_trace.txt`.
- Run (raw, no early stop): `bash tools/ctr360/run_xenia.sh <secs> '<grep pattern>'`

**Run length: stop at the target frame, not on the clock.** The freeze is early (f=0-25),
so the working cycle is `--until-frame 25 --secs 75`. Only a run that must reach the title
(`TITLE_INTRO_MENU_READY_FRAME` = 230 intro frames, IN_MENU handoff ~f=732) needs minutes;
the frame loop advances ~18-20 fps under the current trace volume.

**Operating rules (user-granted).** Work autonomously: launch/kill Xenia, judge progress
from guest logs, no visual-confirmation requests. The real-console path stays viable (no
Xenia-only hacks; Xenia config options only for debugging).

---

## 1. Current state (session 9)

**Phase 0.1 + 0.3 are done** (see `research/session9_trace_and_frame_pos.md`):

- Trace categories + buffered logging (`platform/native_trace.c`, log sink in
  `platform/xbox360/native_xbox360_log.c`). Runtime mask from
  `cache:\ctr360_trace.txt`; default `boot|title|vram`. A quiet run's log is
  **634 lines** instead of 3.9 MB. The sink takes a spinlock (the game thread and
  the audio callback thread both log).
- `tools/ctr360/run_harness.py` is the reproducible run: hashes (XEX/PE/cooked/
  staged), trace categories, guest log + Xenia excerpt, captures with decoded
  pixelsums and wall times, and one outcome line. Results in
  `build-360/results/<stamp>_<tag>/`.

**Phase-2 fix landed (repo + tree): the ModelFrame.pos cook rotated x/y/z.**
`dram_model_anim_sites` registered `(fo, 8)`; `apply_swaps` reverses the whole
block for 2-element sites, so `x y z pad` came out rotated by one halfword and
every reader (bbox corners, `frameY`, `FrameZ`, DrawFunc `frameOrigin`) got a
neighbouring coordinate. Now `(fo, 8, 2)` (per-u16) with a `site_span()` helper
for the overlap gates; offline-verified: `cooked == byteswap16(retail)` for all
18 ModelAnim candidates of entry 514. Readers fixed to match the port's
convention: `RenderBucket_PackedFrameXY` (composes the packed word from the
fields), `GetCommandColor`/`GetIndexedColor` (colour words are cooked
host-order), `RunInstanceSetupCallback`'s LR1/LR2 (`halfVector` is written
plain). Guest evidence: `pj f=61 ... sxy=0061ffcd sz=1133`,
`pk f=61 x=-1024..1023 y=-1024..97 z=0..1133` (was `sxy=03ff0100 sz=0`,
`y=1023..1023`).

**Two blockers stand between this and the pixel gate:**

1. **Runs do not reach the 3D capture frames.** The f=12 capture is still
   `6811c482ead27c0b`; f=205/455/505+ were never reached, so the pixel verdict is
   still open. The capture list now also covers f=20/30/40/50/61/75/100.
2. **Nondeterministic boot/load stalls + a slow frame loop.** Two distinct
   modes, both upstream of any 3D frame:
   - **Parked** (0.19-0.41 s CPU per 3 s): the guest stops right after
     `[trace] pi done` (`MainInit_JitPoolsNew`'s tail, called from
     `LOAD_TenStages` case 0) and `stage=1` never prints. Stage 1 opens with the
     XA fade wait after stage 0's `CDSYS_XAPauseRequest()`, and XA assets are
     not staged — prime suspect.
   - **Spinning** (3.2 s CPU per 3 s): the pre-short-run `cull9` run got past
     the load (`stage=0..9` all printed) and stopped at f=21 immediately after
     the `[trace] g0` marker at the top of `MainFrame`'s game-logic section.
     The `g1m..g7m` sub-phase probes are menu-gated (`gameMode1 & 0x2000`), so
     cutscene frames have no coverage there — widen those gates next.
   `[timing] framePeriod=2342.1ms` in the boot; the platform sub-timings are
   small (`endScene` 0.0-0.1 ms, `vblank wait` 16.4 ms). New instruments:
   `pi done`, `ndbox wait` (first-boot song clock; never entered so far),
   `hb` (every 30 frames: ms/state/stage/mode1/lvl), `mbank` (stage-6
   music-bank state), `framePeriod`. With `--trace all` the OT walk (`walk#N`)
   dominates the log: one bin chain is ~1000 entries, bins 11..18 per frame
   ≈ 8 k entries — the OT pool is 0x8000 bytes (8192 entries) for 1P.

**Instruments added this session (category CULL, f>=500 gated):** `xq` (identity
of every offered instance: model id, name words, flags, pb, idpp, anim),
`xz` (why `pb == 0` drops happen, with `idpp[0]`/`idpp[1]` push buffers), and
`xs/xs2/xs3/xs4/xs5` — one picked instance end-to-end: raw frame-pos bytes + both
decodings, packed corner inputs, GTE RT/TR/OFX/OFY/H as loaded, SXY0..2/SZ0..3
after each `rtpt`, folded bounds. None of them have run yet (no run reached
f>=500).

### 1.1 Session-8 state (still true where not superseded above)

**Pixel truth (new, deterministic).** `MainFrame_ResetDB` now takes scheduled
VRAM captures to `cache:\ctr360_<tag>_fNNNN_vram.tga` (frames 12/205/455/505/
565/625/715/745/800); convert with `python tools/ctr360/tga_to_png.py <tga>
<png>`. Result this session: the copyright capture is readable
("(c) 1999 Sony Computer Entertainment Inc."), and **all seven captures from
f=12 to f=715 have the identical pixelsum `6811c482ead27c0b`** - the VRAM never
updates after the boot 2D pages. The crate/menu/title draw nothing. That is the
gate every Phase 2 step must move.

**Packet ABI (IMPLEMENTATION_PLAN Phase 1) - fixed and measured:**

| class | before | after |
|---|---|---|
| `invalid tag length` | 99 | **1** |
| `invalid-prim-words` | 354 | **4** |
| `[fault]` | 0 | 0 |

1. `RenderBucket_LinkPrimRaw` wrote the OT tag through the byte-wise LE
   `RenderBucket_WritePackedWord` while the walker reads it natively
   (`CTR_GPU_ReadTagWord` = memcpy) and every other emitter stores natively.
   Now `CTR_GPU_WriteTagWord`.
2. `CTR_GteStoreSXY*` stored LE bytes into fields read as native s16 pairs
   (`MakeVertexTriangle` p0[0]/p0[1], `DrawLevelOvr1P` posScreen rebuild);
   now a native-halves store (`CTR_GteStoreSXYWord`, x low / y high).
3. `CtrGpu_WritePackedUVWord` now keeps u/v as bytes but stores clut/tpage as a
   native u16 (`poly->clut`/`poly->tpage` are native field reads).
4. `RenderBucket_StoreInstanceAnimWord` wrote animFrame/vertSplit LE while every
   reader is a plain C load; now a host store.
5. **The walker's `polyTag->len` bitfield reads** (`ProcessDrawEnv` loop bound +
   the `len==2`/`len==0` zero-packet checks) were mis-packed on BE (MSB-first):
   `getlen` returned the right length but `polyTag->len` read the low byte, so
   the len==2 zero packet fell through to a 3-word parse -> the `diff=-4`
   overshoot class. All four sites now use `getlen(polyTag)`.
6. `NativeRenderer_SaveVRAM` honors its rectangle now (it wrote full-VRAM rows
   regardless of the header); `tools/ctr360/tga_to_png.py` converts.

**Residual packet anomaly (small, localized):** ~1 tag-length + ~4 prim-overshoot
reports per run, all in one region (`db0/db1.prim+0x220`, words like
`05ee85e0 12a00000 00000000 00000051` - the payload words look byte-swapped,
`0x12a00000` = swap of `0x0000a012`). One specific packet family, not yet
identified; chase after the draw path works.

**Plan checklist status (IMPLEMENTATION_PLAN §12):** (1) trace categories +
buffered logging **done**; (2) deterministic early captures **wired** - their
pixelsums are still all identical, which *is* the Phase-2 gate, not an infra
gap; (3) packet ABI host tests + the `CTR360_SELFTEST` XEX (= Phase 1.1)
**open**; (4) the proven OT-tag mismatch **done**; (5) the crate scene is
**reached** but ~5 packet-walker reports per run remain (the residual anomaly
above). Phase 2 (the cull/draw gate) is the active phase.

### 1.0b Session-7b state (history; still accurate where not superseded above)

**Where the work stands.** The guest runs end-to-end: boot -> SCEA/copyright ->
crate cutscene -> menu load -> title object spawns -> title intro camera sweeps
and settles (f=734, `title-menu intro=210`, `tcp p=0,128,960 r=2168,0,0`), 0
`[fault]`. **But the framebuffer still shows the copyright page** — the user
watched a multi-minute run and nothing repainted. Guest-log state is NOT pixels;
the user's screen is the judge (see `research/visual_gate_plan.md`).

**The visual blocker: degenerate projected bounds cull every title-frame
instance.** `rbe ents=150 ok=0 drop=0,0,0,0,150,...` at the title frames (crate
frames get `ok=19..45`); `bdy maxY=-1024`, `bdz maxZ=0`, `pk y=-1024..-1024`,
`pj sxy=fc000100` — the projected y sits on the GTE clamp floor (-1024) or
ceiling (1023), so `RenderBucket_AcceptProjectedBounds` rejects and no prim is
ever emitted.

**Session-7 fixes (landed, repo + tree):**

1. **The `gte_st*` store macros byte-reversed every GTE scalar output on BE**
   (`CTR_WriteU32LE` -> `CTR_STORE_U32` host-order, 55 sites in
   `include/psx/inline_c.h`). This was the f=205 wedge: `gte_stopz` wrote the
   MAC0 byte-swapped (`mf f=204 mfc=01e78c30 loc=308ce701`), the OT bin went
   wild and the OT link writes clobbered the Jit list head. Guest now runs
   f=205 -> f=734. The prim path is untouched (it uses `CTR_GteStoreU32`, and
   `gte_stsxy*`/`gte_strgb*`/`gte_stlvl`/`gte_sttr` have zero game callers).
2. **`CTR_GteStoreMAC` stored the matrix `t[]` host-order** while
   `gte_SetTransMatrix` (the cull) and `PushBuffer_SetMatrixVP`'s aspect scale
   read them LE. Fixed to LE stores (the PSX `sw` model). Landed and verified
   (the `sm t=` reads flipped to the LE artifact) — necessary, not sufficient:
   the projected-y blocker persists.

**Checked and clean (offline; retail and cooked images identical at the bytes):**
the cooked `ModelHeader.scale` (`18 10 3b 0b c9 06`) — the LE read gives the
plausible all-positive scale (1.006, 0.703, 0.424), the BE read a negative z.

**Probe rule (hard-won):** a probe that reads a field with a different
convention than the code produces artifacts (the `sm t=`, `mhs scH`, `qd4 mvp=`
plain reads each misled a review). Read via the code's own helper, or print both
orders.

**Open blocker (the visual gate):** the projected y = -1024/1023 at BOTH crate
and title frames. Instrument the chain in order: `RenderBucket_PackedFrameXY`
(frame pos) -> the `MTC2` corner loads in `RenderBucket_ProjectFrameBounds` ->
`gte_rtpt()` -> `MFC2(12)` (SXY) / `MFC2(17)` (SZ) -> the bounds. See
`research/visual_gate_plan.md`; infra first (quiet build + framebuffer dumps so
pixels can be checked without a screenshot request).

### 1.0 Session-6 fixes still in place (three faults, verified in the guest)

1. **`PAIR` half-word access was memory-order, not value-order**
   (`include/psx/gtereg.h`). On the big-endian 360 `.sw.l`/`.sw.h` read the
   opposite half of every 32-bit GTE register written by `CTC2`/`MTC2`, so
   `BuildM3x3`'s lcv0 dropped the y/z columns (`m3x3 = (x,0,0,0,0)`) and
   `BuildMvp` did the same. Fixed with an endianness-aware member order
   (`CTR_GTE_BIG_ENDIAN`), repo + tree. Guest evidence:
   `[trace] qd4 f=198 m=00001914,00000000,000040e6,00000000,000034b5
   mvp=14190000,00000000,7edb0000,00000000,4bcbffff` — full diagonal, live mvp.
2. **`mh->scale.z` was read host-order** while x/y go through
   `RenderBucket_ReadPackedWord` (LE); on the 360 that byte-swapped the z scale
   (`m22 = 0xffffb534` for `0x34b5`), which fed garbage through the projected
   depth/OT path and made the first drawn instance write a stray prim tag into
   the model pack (wedge at f=14: `[trace] c1 f=14 j=3 ... atx=00ed71e0`).
   Fixed with `CTR_ReadU16LE` in `RenderBucket_BuildM3x3` (repo + tree); the
   wedge is gone.
3. **The cooked image byte-swapped `ModelHeader.scale`** and left the
   SpawnType1 struct uncooked — both cooker faults fixed (see section 4).

The unit test that found (1) lives in `tools/ctr360/gte_mul_test.c` +
`run_gte_unit_test.sh`: it drives the real scalar GTE and the real matrix
helpers with `BuildM3x3`/`BuildMvp`'s register choreography, compiled once in
the fixed layout and once with `CTR_GTE_BIG_ENDIAN=1` (which on a little-endian
host reproduces the pre-fix 360 symptom exactly — x survives, y/z drop to 0).
Both runs assert their own expectations; the pair is the regression guard.

**The f=205 wedge — FIXED (session 7; fix list above).** Full chain: the
`gte_st*` store-order bug byte-swapped `gte_stopz`'s MAC0, the OT depth bin went
wild, `RenderBucket_LinkPrimRaw`'s `*otEntry = OTAddress(prim)` wrote OT links
into the model pack and instance pool, and one landed on the Jit `taken` list
head's `next` (`0x00ef0458`). Probe trail: `pi`/`pz` -> `cb1/cb2` -> `d1..d4` ->
`qw` -> `lp` -> `or` -> `mf`.

Frames presented are healthy, no `[fault]`, no `*-guard` trips. Audio: the sink
is a deliberate stub, so "no sound" is expected, not a regression.

### 1.1 The "nothing 3D ever renders" root cause — FIXED (session 4)

`game/RenderBucket/RenderBucket_QueueExecute.c` `RenderBucket_QueueDraw()` in the **tree**
copy had a mis-patched guard: an old probe batch had inserted the `q9` trace so that the
`if (inst->model->headers == 0)` body consisted only of the trace block, leaving the
following `{ g_ctr360_qdDrop[2]++; return rbi; }` UNCONDITIONAL for every instance:

```c
	if (inst->model->headers == 0)
	{ static int s_q9 = 0; ... }     /* closes the if body */
	{ ... return rbi; }              /* ran for EVERY instance */
```

Result: the render bucket was always empty (`[probe] rbe ents=0` on every frame,
`[probe] qall att=42 q=0` at frame 13), so no model polygon ever reached the OT, while 2D
screens rendered fine (they bypass the instance path). The repo copy was correct; only the
tree was broken, which is why source review could not see it. A one-shot dump proved the
models were fine: `[trace] qm f=14 ... w5=827780e0` (`headers` non-NULL).

**RULE (learned the hard way): never insert a probe between an `if (...)` header and its
`{`. Always put it inside the body. After any probe batch, re-read the touched blocks.**

### 1.2 Frame-13 wedge + the crash — FIXED (session 4, two cooker passes)

With the guard fixed, instances walked deeper and immediately exposed two uncooked model
data families:

1. **ModelAnim / ModelFrame scalars** — `[trace] qd3 f=13 frame=89a92808 next=00000000`
   (a frame pointer outside guest RAM). Cooked by `dram_model_anim_sites`:
   `ModelHeader.ptrAnimations` -> `ModelAnim { u16 numFrames @0x10, s16 frameSize @0x12,
   frames at +0x18 stride frameSize }`; per frame `pos` (3*s16)+pad @0..7 and
   `vertexOffset` (int) @0x18. Entry 514 (ND crate pack): 21 anims / 1743 frames / 3528 sites.
2. **Model command lists + color layouts** — the Xenia crash
   (`!> F800002C ==== CRASH DUMP ====  PC: 0x82313984  AV: read at 0x000000013483A583`,
   `r4 = r29 = 0x3483A577`): `commandList = [u32 colorCount][u32 command ...][0xFFFFFFFF]`
   with bit-packed command words; un-cooked, the count `9` read as `0x09000000` and
   `RenderBucket_CopyScratchColorCache` copied ~150M words. Cooked by
   `dram_model_cmdlist_sites` (count + command words + `colorCount` color words at
   `ModelHeader.ptrColors`), 178 entries. **No crash since.**

Both passes drop any site overlapping a loader-map word or an earlier cook (the map is
authoritative) and are round-trip + no-overlap gated by `--check`.

### 1.3 Earlier fixes that remain in place (sessions 2-3)

- Frame-13 print-path wedge: `%zx`/`%zu` -> `%08x` behind validating formatters
  (`NativeGpu_ConvertFormat*`); `Platform_LogWrite` writes durable sinks first and routes
  the `stderr` console copy to stdout (stderr's first-ever use wedged the thread).
- Menu model-walk runaway: `dram_level_scalar_sites` skybox/InstDefs optional; animtex
  chain `numFrames` bound 64 -> 255. Walk guards `am/hd/cm-guard` remain as safety nets.

---

## 2. The immediate work (in order)

Per `IMPLEMENTATION_PLAN.md` (the independent audit's plan; its §12 checklist).
**Done:** Phase 0.1 (trace categories + buffered logging), Phase 0.2
(deterministic VRAM captures), Phase 0.3 (the harness), Phase 1.2/1.3 + the
walker bitfield half of 1.4 (the packet ABI), and the first Phase-2 divergence
(the `ModelFrame.pos` cook + its readers). **Remaining, in order:**

1. **Get one run into a 3D frame and judge the pixels** — the acceptance signal
   for the pos fix: `python tools/ctr360/run_harness.py --secs 75 --until-frame
   61 --trace "boot,cull,title,vram,misc,packet" --tag pix --expect-frame 61`,
   then compare `ctr360_crate61_f0061_vram.tga`'s pixelsum with
   `6811c482ead27c0b`. If the run stalls before f=61, chase item 2 first.
2. **The two boot/load stalls** (both upstream of any 3D frame; see §1 blocker
   2): the parked one after `pi done` (stage 0 -> 1; the XA fade wait), and the
   spinning one at f=21 after `g0` (widen the menu-gated `g1m..g7m` sub-phase
   probes so the cutscene frames are covered). Instruments ready: `pi done`,
   `ndbox wait`, `mbank`, `hb`, `[timing] framePeriod`. See
   research/session9_trace_and_frame_pos.md S5.
3. **Why the draw path emits nothing** (once a 3D frame is reachable): at the
   crate frames 22 instances queue/frame and `RenderBucket_DrawFunc_Normal` runs
   4x/frame, but `DrawAllSplits: 0 split(s) at 0 verts` and the OT holds only the
   2D present/pack quads. The `dw` probe (PACKET) prints each call's
   command-list count + first words: empty list, or emission bails.
4. **Frame time**: `[timing] framePeriod=` says 0.7-2.3 s/frame; the platform
   sub-timings are small, so the cost is game/native_gpu side. The OT walk is
   ~8 k entries/frame (the whole 0x8000-byte 1P pool), so oversized per-instance
   ranges (`range = maxDepth - minDepth`) are the first thing to check; a
   saturated SZ (0xffff) gives a ~2048-entry range. `CTR_INTERNAL` would enable
   the per-bucket `NativePerf` capture.
5. **Phase 1.1** - the packet ABI host tests + the `CTR360_SELFTEST` XEX mode.
6. The residual packet anomaly (`db0/db1.prim+0x220`, ~5 reports per run).
7. Then Phases 3-5 (stable title, demo race, hardware validation).

---

## 3. Path to the title screen and beyond (direction)

1. Visible 3D at all: the crate cutscene + menu instances (immediate work above).
2. Title screen IN_MENU with the trophy/ring/letters (`RenderAllTitleDPP` gate is already
   open: `[probe] rf13-open f=...` fires every 30 frames).
3. The 30 s idle timer then leads to a demo race (`MM_EXIT_ROUTE_DEMO`); that track load is
   the next full-level workout: `mesh_info`/BSP/QuadBlock/LevVertex scalars (the old
   "R3-R5" cooker items in `research/data_coverage_matrix.md`).
4. START skip gate: does nothing before `msInThisLEV >= 5792` ms (CS_Thread.c:47,322).
5. XA assets are NOT staged (`assets/ctr-u.bin` only); the script tolerates it
   (`WAIT_XA_DONE` falls through). No action unless AV fidelity is wanted.

---

## 4. Cooker state (tools/ctr360/cook_disc.py)

Passes (all same-length, round-trip + no-overlap gated): bigfile directory; language files;
KART.HWL; VRAM files incl. u16 pixel values; DRAM pointer maps; pack scalars; model-header
scalars; model anims; model command lists + colors; level scalars; InstDef scalars;
level-embedded models (+ their anims/cmdlists); map-only model arrays; AnimTex chains (both
roots); **SpawnType1 scalars + the menu title camera path (session 6)**. Report lines to
grep for: `model anims cooked`, `model command lists cooked`,
`level SpawnType1 cooked`.

**Session-6 changes:**

- `ModelHeader.scale` (0x18..0x1E) is NO LONGER byte-swapped: the reader
  (`RenderBucket_ReadPackedWord` and the `CTR_ReadU16LE` z component) is little-endian, so
  the cooked image keeps the retail LE bytes. The old swap fed the scale path
  `0x1810/0x3b0b/0xc906` instead of `0x1018/0x0b3b/0x06c9`.
- New pass `dram_spawntype1_sites`: cooks `SpawnType1.count` (host-read by
  `MM_Title_Init`'s `count > 2` gate and every spawner) and, for the main menu entry (216),
  the title camera path `ST1_CAMERA_PATH` frames 0..230 (`MM_Title_CameraMove` reads them
  as host s16s). Verified in the guest: `title-init st1=4` (was 0x04000000) and
  `tcp p=0,128,960 r=2168,0,0` (was `p=0,-32768,-16381 r=30728,0,0`).

**NEVER cook:** pointer-map-covered words (the loader adds the base), ModelFrame vertex
bytes, LevVertex pos/color bytes, model names. The matrix axis is a *reader convention*:
cooked fields are BE and read with host loads; anything read via `CTR_Read*LE` /
`RenderBucket_ReadPackedWord` / `DrawLevelOvr1P_ReadPackedWord` / `LevInstDef_Peer` must
stay LE. **Check the reader of every field you swap** — the scale bug above was a
BE-swapped field with an LE reader.

**Verified-outstanding cooker gaps:** `modelPtr[STATIC_RINGTOP]` is non-zero now but
confirm its writer path stays healthy on cold boots; mesh_info/BSP scalars for real tracks
(demo race).

---

## 5. Instrumentation in the build (probe inventory)

Frame loop: `hbm/l1m/l2m/l3m/g1m..g7m/pa/pd/pe/pf/pg` (MainFrame), `rf-in/render-enter/
render-exit/rf13-open` (render), `lg-in/lg-out` (level geometry), `ovr`, `vl`, `tt`,
`jump-to-title-first-time`, `title-init`, `title-menu` (sparse, every 30th).

Render bucket (session 4): `qall att/q/d[]/lodm/L` (QueueAllInstances window, 30 frames),
`rbe ents/ok/disp/cas/setup0/unk/drop[]` (Execute window), `qd1..qd5` (QueueDraw stages,
sparse), `qm` (model dump at the headers==0 site), `qw` (entry write), `d7` (execute-side
mf==0), `bd*` (BuildDepthRange culls: bdx/bdy/bdz/bdx2/bdy2/otnull/otrange/otfull),
`pj/pk` (projection inputs), `rl` (camera rot/pos), `sm` (ViewProj compose). Guards:
`am-guard/hd-guard/cm-guard`. Fault filter: `[fault]` (native_xbox360_fault.c).

Session 6 additions (all tree-only, scripts in `tools/ctr360/`): `mhs` (per-title-model
ModelHeader scale + instance scale), `b3s` (BuildM3x3 lcv0 internals + tuple), `qi/qd6`
(instance identity), `cc` (CopyScratchColorCache bounds), `ota/otd` (OT range allocator +
per-entry range), `dsp` (dispatch cases), `d1..d4` (inside DrawFunc_Normal), `wch/w2/w3/w4`
(field watches), `csb` (CS_BoxScene GHOST walk), `vsw` (PVS list words per phase). Most are
frame-gated (`sdata->frameCounter >= N`) rather than capped — see the rule below.

**Probe-insertion rules (each cost real time):**
- NEVER insert between an `if (...)` and its `{` (this caused §1.1).
- Never write probes via shell heredocs — escapes get mangled; use file-based tool scripts
  (see `tools/ctr360/add_*_probes.py` for the pattern: exact anchors + uniqueness asserts +
  CRLF/LF variants) and run `fix_newline_in_literals.py` after edits.
- Cadence probes miss the frame of interest: print on every call while the menu is active,
  capped (`(mode1 & 0x2000) && !(mode1 & 0x40000000)`), or sparse forever (`% 30`).
- **A cap hides the event.** A probe that prints the first N calls tells you nothing about
  f=205; gate on the frame window instead (`sdata->frameCounter >= 199`), and for value
  watches print only when the watched value is nonzero, so the first hit names the writer.
- Probe bodies are C89: declare locals at the TOP of the probe block (`u8 *w;` before any
  statement) or the XDK rejects the declaration (C2065 'w' undeclared cascades).
- Probes must not fault before the data exists: guard reads of `sdata->ptrMPK` etc. with an
  arena check (`((u32)sdata->ptrMPK >> 24) == 0x82`) — an unguarded early read wedged f=1.
- Generator scripts: never put a bare `\n` escape inside a Python string you later run
  `.replace('\n', nl)` on (it becomes a real newline inside the C literal) — build the C
  escape with `chr(92) + 'n'`.
- One broken anchor poisons every alphabetically-later file in the C89 pass — fix the
  anchor and re-run, don't hand-patch generator output.

---

## 6. Tree vs repo, and reading a run

`build-360/gen` is GENERATED (C89-hoisted, mixed LF/CRLF). Session-4 found the tree holds
probe lines the repo lacks (`q5/q9/q6/q8` in RenderBucket, sparse title probes) — probe
batches were applied to one copy. Until a full regen reconciles them, **treat the tree as
the source of truth for what actually runs**, and note any divergence when editing.

Reading a run: the last non-pump guest line names the stall; `[CTR Audio] pump callbacks`
is the liveness signal; `frame N presented` is NOT the game frame; grep `[fault]` first;
a `*-guard` line means the data behind that walk is still wrong (fix the cooker, not the
guard). CPU ~0.2-0.6 s per 3 s wall = parked, not spinning.

---

## 7. Research reports + debug levers

- `research/visual_gate_plan.md` — **session-7b, read this first** (log-vs-pixels,
  the cull blocker, the ranked plan, the convention table, the verification
  protocol).
- `research/gte_endianness_findings.md` — sessions 6-7 (the `PAIR` half-word bug,
  the scale.z read, the SpawnType1 cook, the f=205 wedge chain, the two
  store-order fixes, the unit test).
- `research/3d_path_findings.md` — session-4 evidence (guard bug, the two cooker passes,
  the projection analysis §5).
- `research/backend_audit.md` — backend audit; the pitch-9552/PM4_DRAW_INDX failures are
  the stock XDK display blit, NOT our draws: do not chase. Ranked backend work unchanged.
- `research/data_coverage_matrix.md` — cooker-vs-consumer matrix + no-cook list.
- `research/xdk_inventory.md` — XDK + Xenia levers (incl. `--debug`, `DbgPrint`,
  `break_on_instruction` with `default.xdb`).
- `research/boot_to_title.md` — the boot/menu-load path detail.
- `research/render_path_map.md` — NOT PRODUCED (subagent output limits); do not re-dispatch.

Debug levers ranked: 1) `[fault]` filter; 2) walk guards + `[probe]` trail; 3) Xenia
`--debug` (guest debugger: break on the culled instance, inspect live GTE/matrix state);
4) `DbgPrint`; 5) `KeBugCheckEx` on invariant violations; 6) `break_on_instruction`;
7) `instrument_call_times` / `trace_gpu_stream`.

---

## 8. Landmines (each cost real time)

- Probe anchors must sit INSIDE statements, never on a function signature (C2449).
- The tree's line endings are mixed; multi-line needles need both LF/CRLF variants.
- The XDK C compiler rejects declarations after statements and for-init declarations
  (C2065/C2061/C2059 cascades) — that is what the hoist pass fixes; match that style.
- `build_xex.sh` FATAL gates are trustworthy: FATAL = nothing staged. ImageXex is
  incremental; grep the built exe for a probe string to confirm identity.
- Staging identity: `prep_test.sh --cooked` + md5sum against the staged asset.
- The `stderr` console stream wedges on first use — it is routed to stdout.
- A guest wedge produces no `xenia.log` error by default; `[fault]` and the probes are the
  instruments.
- **Half-word access to 32-bit data is the standing hazard.** `PAIR`-style unions, `u16`
  struct fields read host-order, and LE reads of BE-written data all bite on the 360. When
  a value looks byte-swapped, find its reader before touching the data (§4).
- **Host pointers must never land in guest memory.** Values like `0x00exxxxx` /
  `0x58xxxxxx` in the 0x82xxxxxx mempack window mean a host-side pointer was stored into
  game data — that is the f=205 suspect class.
- `RenderBucket_GetNormalOTEntry` = `activeRange + (MAC0 >> 17)` and `gte_stopz` reads OTZ
  (clamped 0..0xFFFF), so the OT write target is `activeRange` itself — a stray prim tag in
  the pack means the range pointer, not the depth, went bad.
