# ctr360 implementation plan: visible title screen to playable demo

**2026-10-11 memory-card candidate:** persistent game:/memcards files, flushed
temporary writes/replacement, native header/ghost metadata and garage packets
are repaired. Normal menus create/overwrite and restart/reload a named profile;
final minimized runs have zero faults/packet errors. Physical testing is deferred
until the controller is repaired. Read research/20261011_memory_cards.md and the
current HANDOFF. Earlier open-save and garage-diagnostic notes are superseded.

**2026-10-11 HD candidate:** the user reports full playability and requests
graphics enhancements. Native 1280x720, expanded 16:9 world view, centered 4:3
UI, decoded texture filtering and edge AA are implemented. Single-player race
presentation targets 60 FPS through midpoint poses while simulation remains
30 Hz. Short minimized visual and production runs load/drive Crash Cove with
attached wheels; production measures 59.14–60.01 render FPS/~30 simulation Hz,
zero faults/packet errors. XDK/AST/actual-function/shader checks pass. Hardware
package is ready for the user's console test; physical compatibility/performance
and broader tracks/modes/effects remain unverified. Memory-card full remains open;
an unintended Adventure run's packet errors need baseline isolation. Read the
current HANDOFF and research/20261011_hd_graphics.md. Older assessments below
are historical; the previous pause was superseded by this user request.


**2026-10-11 wheel/scene checkpoint:** the user confirmed all reported fixes,
including bursting crate and flyby. Crash Cove Time Trial has attached wheels
during acceleration/turning and a visible track preview. The final minimized
test completed with zero logged faults/packet failures and sustained 29.91 FPS.
Player inputs are restored, the automated test stopped, and work is paused at
the user's request. A separate Xenia launch after cleanup was left running.
Read HANDOFF.md and research/20261011_wheels_scenes.md for current
identities and the precise scope of visual acceptance. Earlier broad graphics
assessments missed bare karts and are superseded; full controlled lap and
physical Xbox 360 acceptance remain future milestones.

**Historical pre-wheel 2026-10-11 checkpoint (superseded):** the working demo milestone is achieved. Completed
minimized runs verify coherent moving Crash Cove and Roo Tubes demos, plus
Crash Cove Time Trial loading, acceleration/steering/recovery and HUD. Both
runs have zero faults/packet errors and measured sustained performance around
30 FPS. Title/menu text and audible title music are confirmed; race PCM is
captured, while its sound quality and a complete controlled lap still need
validation. Read HANDOFF.md for current tested identities and evidence. The
assessments below are historical.

**2026-10-09 checkpoint:** coherent crate graphics have been verified in final
display captures beyond copyright. Camera/sky/delta endian reads, GPU control
commands, shader dither, and an unconditional clock-timer decrement introduced
by old logging probes were repaired. Read `research/20261009_graphics_debug.md`
and the current HANDOFF checkpoint before using this historical assessment.
Title/gameplay, performance, audio, and input remain to be verified.

_Prepared 2026-09-20 from an independent read-only audit of the repository, the
retail/cooked data checks, the current XEX and guest log, the two reference
repositories, and the existing research notes. `NEXT_SESSION_PROMPT.md` and
`HANDOFF.md` were treated as evidence, not as instructions or ground truth._

## 1. Executive assessment

The port is on a viable architectural path. The game reaches the title sequence
in guest state, the XDK build produces a working XEX, the D3D9 backend presents,
the cooked disc validates, and substantial PSX data/loading behavior has already
been reproduced. Replacing the approach or restarting from a different port is
not justified.

The current debugging strategy, however, is too narrow and too expensive. The
remaining problem is not proven to be only a projected-Y cull bug. The latest
guest log contains three simultaneous failures:

1. Every title instance is rejected before RenderBucket execution (`rbe ...
   ok=0`, mostly `drop[4]`, with saturated/degenerate projected bounds).
2. The native GPU walker sees malformed packets throughout the run and near the
   final stall (`invalid tag length`, negative packet-size differences, and
   unhandled tagless primitives).
3. The main frame stops at game frame 735 while the audio thread continues. No
   `[fault]` or guard line is emitted, so absence of an exception is not proof of
   a healthy render path.

There is also a concrete, code-proven endian mismatch in the render-bucket
primitive path:

- `RenderBucket_LinkPrimRaw()` writes an OT tag through
  `RenderBucket_WritePackedWord()`, which emits little-endian bytes.
- `CTR_GPU_ReadTagWord()` and the native packet walker read the tag as a native
  `u32` (`memcpy` into a host word).
- On big-endian Xenon a semantic tag such as `0x06abcdef` is therefore observed
  as `0xefcdab06`; its packet length becomes `0xef`. This matches the class of
  invalid lengths in the guest log.

The same boundary must be audited for SXY, UV/tpage, clut, colors, custom ghost
packets, runtime matrices, and animation fields. A blanket rule such as “all GTE
stores are host order” or “all PSX words are little-endian” is incorrect. The
representation is determined by the destination and its consumer.

The shortest credible path to in-game is therefore:

1. make runs fast and make pixels/packet validity directly observable;
2. fix and test the runtime packet ABI and writer/reader conventions;
3. localize and fix the title cull using a single-instance trace and a PC
   reference trace;
4. prove a visible title and stable idle loop;
5. cook the real-track data families and enter the demo race;
6. validate on hardware only after Xenia passes deterministic gates.

## 2. Audit facts and corrections to the current handoff

### Confirmed healthy foundations

- Git worktree was clean at the time of this audit; HEAD was `144dd3f`.
- `python tools/ctr360/check_probes.py` reports 101 entries and zero problems.
- `python tools/ctr360/cook_disc.py --check` validates 496 regions and writes
  nothing.
- `build-360/ctr-u-360.bin` and the staged
  `build-360/xex/dist/assets/ctr-u.bin` have the same MD5:
  `FED8081697E06E4785608AED72BE9270`.
- The latest audited XEX was built at 2026-09-20 05:55 and the latest guest log
  ended at 06:02.
- The renderer reaches `PresentVRAMRect`, draws the full-screen present quad,
  and calls `IDirect3DDevice9_Present`. The known Xenia pitch/PM4 messages are
  not the immediate game-draw blocker.

### Statements that must not be treated as established

- “The game reaches the title screen” currently means only that title logic and
  camera counters advance. It does not mean title pixels were produced.
- “Zero faults” does not mean the render pipeline is valid. The GPU walker is
  explicitly reporting malformed packets, and the main thread later stops.
- “The projected-Y bug is the blocker” is incomplete. It is one blocker, while
  packet ABI errors are another independently demonstrated blocker.
- “The `CTR_GteStoreMAC` fix solved the matrix translation” was not visually or
  numerically verified after the fix. It may be correct for the packed-LE
  `matrix_ViewProj` readers, but direct native readers of related `MATRIX`
  fields still need auditing.
- The current host GTE test is not a sufficient cross-endian proof. Its runner
  currently ends with `Access is denied`, and changing `PAIR` member order on a
  little-endian process is only a symptom simulation, not execution under a
  big-endian C ABI.

## 3. Non-negotiable engineering rules

### One source of truth

`game/`, `include/`, `platform/`, and `tools/ctr360/` are authoritative.
`build-360/gen` must become a disposable generated artifact. Do not make a fix
only in `build-360/gen`, and do not accept a run whose generated tree cannot be
reproduced from the repository.

Before behavioral work, add a mirror manifest containing the source commit,
generator version/hash, generation time, and hashes of the critical generated
files. Make `build_xex.sh` fail if the mirror is stale relative to authoritative
sources or if the manifest is absent. A temporary developer-only incremental
mirror command is acceptable, but the final verification build must regenerate
from scratch.

### Name representations by contract

Do not use a generic “packed word” helper at unrelated boundaries. Establish and
use explicit helpers for these domains:

| Domain | Stored representation | Typical consumer |
|---|---|---|
| Runtime C scalar/pointer | host endian | plain C load |
| GTE logical register | host numeric value | `MFC2`/`CFC2`, arithmetic |
| Runtime GPU tag/link | native `u32` semantic word | native OT walker |
| Runtime GPU XY | native `s16 x`, native `s16 y` | `MakeVertex*` |
| Runtime GPU UV/tpage | byte `u/v`, native `u16 clut/tpage` | native primitive structs |
| Runtime GPU color/code | byte `r/g/b/code` | native primitive structs |
| PSX packed stream kept raw | explicit LE bytes | `CTR_Read*LE` or byte decoder |
| Cooked host-loaded field | BE/native bytes | plain C struct load |
| Pointer-map slot after load | host pointer | plain C pointer load |

Every fix must name the domain, writer, reader, and expected byte layout. Avoid
changing a shared helper until all callers have been classified.

### Every milestone has three gates

1. Structural: no faults, guards, malformed packets, or stale artifacts.
2. Numeric: expected counters/transforms/bounds are in range.
3. Visual: a captured frame differs from the previous screen in the expected
   region. Guest state alone is never a visual milestone.

## 4. Phase 0 — create a fast, trustworthy experiment loop

Do this before another projection hypothesis.

### 0.1 Replace always-on probes with categories

Add compile-time and runtime categories, for example:

- `CTR360_TRACE_BOOT`
- `CTR360_TRACE_PACKET`
- `CTR360_TRACE_CULL`
- `CTR360_TRACE_TITLE`
- `CTR360_TRACE_VRAM`

The default diagnostic build should emit only: build identity, phase changes,
frame heartbeat, `[fault]`, guard failures, packet-integrity failures, and dump
results. A targeted category may be enabled for one experiment. Remove the
hundreds of per-frame `hbm/l*m/g*m/w2/BeginScene/pack/pvr` lines from the default
run.

Change `platform/xbox360/native_xbox360_log.c` so ordinary lines are buffered.
Flush on fatal/fault/guard/packet-integrity events, explicit phase boundaries,
and shutdown. Keep `OutputDebugStringA` optional under the same category switch.
Do not remove durable logging; make its flush policy intentional.

Success gate: a 90-second Xenia run reaches title logic at normal game speed,
with a small enough log to inspect manually. Record wall time to frames 13, 205,
503, 734, and 800.

### 0.2 Add deterministic visual capture

The Xbox renderer already has `NativeRenderer_SaveVRAM()` and a GPU-to-CPU
Resolve path. Reuse it rather than inventing a second readback stack.

Add a diagnostic scheduler that captures once at named transitions, not on
every frame:

- first copyright frame;
- first crate frame after load;
- first menu frame;
- title intro frames approximately 0, 60, 120, 210, and IN_MENU;
- first demo-race frame.

Write full 1024x512 PSX VRAM TGAs to `cache:\\ctr360_fNNNN_vram.tga` and, if
needed to distinguish VRAM from presentation errors, add one final-backbuffer
capture. Log the file name, display rectangle, and a lightweight checksum of the
captured pixels.

Fix the existing `NativeRenderer_SaveVRAM()` contract while doing this: it
currently writes `VRAM_WIDTH × VRAM_HEIGHT` pixel rows regardless of its
`width/height` header. Either require full-VRAM dimensions with assertions or
honor the requested rectangle consistently.

Add a host-side converter under `tools/ctr360/` that converts the 16-bit TGA to
PNG without modifying the source image. The automation should print the paths
of both files.

Success gate: two captures from known different 2D pages have different hashes
and visibly different PNGs. This independently proves the dump path before it
is used to judge 3D.

### 0.3 Make runs reproducible

Extend the run script to write a result directory containing:

- XEX hash and build identity;
- cooked and staged asset hashes;
- enabled trace categories;
- guest log and relevant Xenia log excerpt;
- frame captures and hashes;
- a one-line outcome (`PASS`, `FAULT`, `PACKET_INVALID`, `STALLED`, or
  `TIMEOUT`).

Do not use “last log line” alone to classify a stall. Track main-frame heartbeat,
audio heartbeat, and Xenia process CPU separately.

## 5. Phase 1 — repair the runtime GPU packet ABI

This is the first correctness change. Complete it before interpreting rendered
coordinates or title pixels.

### 1.1 Add packet contract tests first

Create a small host test for each primitive family currently emitted by
RenderBucket: G3, GT3, FT3, split variants, and ghost packets. Given semantic
values, the test must verify what the native walker sees:

- tag length and next-link token;
- command code;
- x/y for each vertex;
- u/v and clut/tpage;
- colors;
- exact primitive size and walker advance.

Because the development host is little-endian, also test explicit byte buffers
with simulated big-endian 16/32-bit loads. Do not claim big-endian coverage from
preprocessor member reordering alone.

Add a minimal `CTR360_SELFTEST` XEX mode that constructs the same packets on the
actual Xenon ABI, parses them without starting the game, writes a concise PASS/
FAIL log, and exits or idles. This is the authoritative endian test and should
also be runnable in Xenia.

Repair `tools/ctr360/run_gte_unit_test.sh` so it executes reliably on Windows;
its current `Access is denied` result must be a hard test failure. Update its
wording so the two simulated layouts and their limitations are explicit.

### 1.2 Fix the proven OT tag mismatch

In `game/RenderBucket/RenderBucket_QueueExecute.c`, make
`RenderBucket_LinkPrimRaw()` use the same tag representation as the walker and
all other native emitters (`CTR_GPU_WriteTagWord()` or a single typed
`CtrGpu_Link...` helper). Do not use the matrix/PSX-stream LE writer for runtime
OT tags.

Audit every direct `poly->tag`, packet tag, and OT entry store. A packet and its
walker must use one representation end-to-end. Add range assertions for both
the OT entry and primitive-memory cursor in diagnostic builds.

Success gate: zero invalid tag lengths, zero packet overshoots/undershoots, zero
unhandled tagless primitives, and all constructed-packet tests pass on host and
the self-test XEX.

### 1.3 Fix typed primitive fields

Audit and split these helpers/call sites:

- `CTR_GteStoreSXY*`: when the destination is a runtime primitive or a struct
  later read as `s16[2]`, store native x and native y separately (the semantic
  equivalent of `CtrGpu_WritePackedXY`), not four LE bytes.
- `CtrGpu_WritePackedUVWord`: retain `u/v` as bytes but store `clut/tpage` so a
  native `u16` reader gets the intended value on Xenon.
- custom ghost/split packet `u32 xy*` fields: either give them typed x/y
  subfields or ensure their parser uses the exact same word accessor.
- color/code helpers: byte-oriented `r/g/b/code` storage is appropriate, but
  verify custom packets that assign the whole word directly.
- `RenderBucket_WritePackedWord`: retain it only for true LE matrices/streams;
  replace its tag and runtime-scalar uses with domain-specific helpers.
- `RenderBucket_StoreInstanceAnimWord`: classify every later read of
  `animFrame/vertSplit`; change the writer or readers together.

Do not globally change `CTR_GteStoreU32` or the entire `gte_st*` macro family.
Classify their destinations first. Scalar locals, packed matrices, and GPU
primitive fields require different stores.

### 1.4 Harden the walker as a validator

For diagnostic builds, stop the current frame on the first malformed packet and
emit one compact record containing producer category, OT index, packet address,
tag, expected size, actual advance, and primitive-memory bounds. Continuing
after a malformed packet creates misleading downstream symptoms.

Resolve the documented `len==2` zero-packet contract with a unit test: the
parser return value and the walker's addition of `P_LEN` must advance exactly to
the tag boundary. Rate-limit repeats only after the first complete report is
durably flushed.

## 6. Phase 2 — isolate and fix the per-instance cull

Begin this phase only with a packet-clean build. Packet cleanup may expose 3D
primitives immediately, but it will not by itself fix instances rejected before
emission.

### 2.1 Establish a little-endian reference trace

Build/run the current authoritative source as the supported 32-bit PC native
target with the same legal retail dump. Capture one known crate instance and one
title model (IDs `0x66..0x6b`) at the same logical animation/camera frame.

Record semantic values, not raw host words:

- model ID/name, instance flags, selected LOD/header/frame;
- frame `pos.x/y/z` and next-frame interpolation;
- instance position/rotation/scale;
- push-buffer rect, geom offset, `H`, camera position/rotation;
- view position;
- unpacked 3x3 and translation components of `m3x3`, composed MVP, and GTE
  RT/TR registers;
- all eight projected bounding-box corners as x/y/z before folding;
- final min/max and the exact reject predicate.

If the PC target does not render the same path, use the retail Ghidra listing in
`../repos/CTR-in-C/reference/ghidra/zzz_Rest_Of_94426.c` as the instruction-level
oracle. The relevant retail sequence is `0x80070950` through the bbox projection
at `0x80071054..0x80071164`, plus helper `0x80071524`.

### 2.2 Trace exactly one Xbox instance end-to-end

Select a stable title object by model ID and instance pointer. Emit one structured
line per stage for one frame; do not sample “first N calls,” because that mixes
different models and cameras.

At every mixed-width boundary print:

- semantic value read by the production helper;
- raw four bytes;
- native value and LE-decoded value only when they differ.

Trace this chain:

`ModelFrame.pos` → interpolated/shifted bbox corners → view position → selected
model scale → `m3x3` → composed projection MVP → GTE RT/TR/OFX/OFY/H → each
`MTC2` input → each `RTPT` SXY/SZ output → folded bounds → reject reason.

The current aggregate logs are insufficient because they mix valid and invalid
instances and some probes read packed fields through plain native loads.

### 2.3 Compare in semantic space and fix the first divergence

Compare PC/retail and Xbox traces stage by stage. Fix only the first divergent
stage, rerun the focused tests, and then capture a frame. Likely classes, in
priority order, are:

1. runtime/persisted matrix translation representation;
2. `ModelFrame.pos` or interpolation mixed host/LE reads;
3. matrix halfword packing or GTE transfer helpers;
4. push-buffer geometry values;
5. incorrect model/header/frame identity;
6. only then, a transcription error in the bbox corner choreography/fold.

Do not bypass `RenderBucket_AcceptProjectedBounds()` as a fix. A temporary
diagnostic “force accept one instance” switch is permissible only to separate
cull correctness from draw-path correctness, and it must never be enabled in a
milestone build.

Success gate for one instance: finite/non-saturated corner projections, positive
depth beyond `H/2`, viewport-overlapping bounds, QueueDraw success, execution of
the expected draw function, valid emitted packets, and visible pixels in the
capture.

Success gate for the title set: all six intended title models are observed by
identity; visible ones pass the cull and off-camera ones fail for explainable
geometric reasons. Do not require every queued instance to pass.

## 7. Phase 3 — stable visible title and menu handoff

With packet and cull paths correct:

1. Verify the crate scene changes the copyright framebuffer.
2. Verify title intro captures change across frames 0/60/120/210.
3. Verify the title state reaches `TITLE_MENU_STATE_IN_MENU` through the normal
   230-frame handoff and `RenderAllTitleDPP` contributes valid primitives.
4. Let the title idle for at least 60 seconds beyond IN_MENU. The main frame must
   continue monotonically; audio-only liveness is a failure.
5. Reproduce the historical frame 91..111 and frame 735 stalls with the quiet,
   packet-valid build. If a stall remains, add phase markers around the last
   completed main-thread subsystem and use Xenia's debugger at that boundary.

Title milestone acceptance:

- no `[fault]`, guard, packet-integrity, or primitive-memory-bound failures;
- no main-thread stall;
- title geometry is visibly recognizable in captured pixels;
- the displayed image changes after copyright and during the intro;
- a user visual check agrees with the capture;
- a clean mirror regeneration produces the same behavior.

Only after this milestone should obsolete probe generators and tree-only probes
be removed or archived.

## 8. Phase 4 — enter a demo race

The 30-second idle demo is the best next target because it exercises a real
track without requiring input mapping or menu navigation.

### 4.1 Complete track data coverage before the load

Implement cooker work in dependency order, with round-trip/no-overlap/no-cook
assertions for every pass:

1. `mesh_info` counts (`numQuadBlock`, `numVertex`, `numBspNodes`);
2. BSP node flags, boxes, child IDs, and leaf counts;
3. QuadBlock scalar/index/draw-order/bbox fields, preserving pointer slots and
   explicitly LE-consumed streams;
4. remaining required Level scalars;
5. only the LevVertex fields proven to have host-load consumers.

Use `research/data_coverage_matrix.md` as a starting inventory, but re-check each
consumer before cooking. In particular, do not cook command streams, texture
layouts, delta arrays, or LevVertex position/color bodies whose consumers are
explicit LE readers.

Add validation against a real track such as Tiger Temple:

- counts within file-derived bounds;
- every BSP child index in range;
- every leaf quad range in range;
- every QuadBlock vertex index below `numVertex`;
- every pointer-map word excluded from scalar swapping;
- cooked pass is idempotent and same-length.

### 4.2 Run the demo transition

Verify, in order:

- title idle selects `MM_EXIT_ROUTE_DEMO`;
- requested level ID and loading stages advance;
- BSP/visibility initialization finishes without billion-iteration swapped
  counts;
- at least one BSP leaf and level-geometry batch are drawn;
- kart/track packets are valid;
- the first race frame is visibly captured;
- main loop remains alive for at least 1,800 game frames or 60 wall-clock
  seconds, whichever is longer.

Demo milestone acceptance is a recognizable track/kart frame, not merely a
successful level load.

## 9. Phase 5 — hardware validation and portability cleanup

After Xenia passes the title and demo milestones:

1. Produce a clean Release XEX from a fresh generated mirror.
2. Stage only the XEX, XDB if desired, cooked image, and diagnostic config.
3. Start with buffered file logging and sparse fault/phase markers; avoid the
   Xenia-scale trace volume on FATX/USB storage.
4. Capture VRAM on the console at the same named transitions and compare hashes
   or PNGs with Xenia.
5. Verify controller input, timing, cache paths, and memory bounds.
6. Keep emulator-specific switches out of gameplay code. Any Xenia workaround
   must be isolated and disabled on hardware.

Do not begin audio/XA fidelity work until a stable demo race exists. The silent
audio sink is acceptable for the current milestone.

## 10. Recommended change sequence and commit boundaries

Keep each step bisectable:

1. `infra: generated-tree manifest and stale-mirror gate`
2. `infra: trace categories and buffered Xbox logging`
3. `infra: deterministic VRAM capture and PNG conversion`
4. `test: runtime GPU packet ABI host tests and Xbox self-test`
5. `fix: native OT tag writer/reader agreement`
6. `fix: typed SXY and UV/clut/tpage stores`
7. `fix: custom packet and anim-word representation mismatches`
8. `test: focused PC/Xbox projection trace`
9. `fix: first proven title-cull divergence`
10. `milestone: visible stable title screen`
11. `data: mesh_info and BSP cooker coverage`
12. `data: QuadBlock and required Level scalar coverage`
13. `milestone: visible stable demo race`

Each correctness commit should include its unit/self-test and before/after guest
evidence. Do not combine speculative endian changes across unrelated domains.

## 11. Standard verification commands

Use these gates for every XEX candidate:

```text
python tools/ctr360/check_probes.py
python tools/ctr360/cook_disc.py --check
python tools/ctr360/build_360_mirror.py --root . --out build-360/gen
bash tools/ctr360/build_xex.sh Release
bash tools/ctr360/prep_test.sh --cooked build-360/ctr-u-360.bin
```

Then assert the cooked/staged hashes match and record the XEX hash. Run the
quiet harness long enough for its named milestone, not an arbitrary duration.
The harness should fail automatically on any of:

- stale mirror/build identity;
- asset hash mismatch;
- `[fault]` or guard line;
- invalid packet length/link/advance;
- primitive-memory or OT-range violation;
- main-frame heartbeat timeout;
- missing expected capture;
- unchanged capture where a transition should repaint.

## 12. First work session checklist

The next implementation session should stop after the following bounded goal:

1. Add trace categories/buffered logging.
2. Wire the existing VRAM save path to two deterministic early captures and
   prove their hashes/images differ.
3. Add the packet ABI tests and Xbox self-test.
4. Fix only the proven RenderBucket OT-tag mismatch.
5. Run to at least the crate scene and require zero packet walker errors.

If packet errors remain, continue the typed packet-field audit before returning
to projected bounds. If packets are clean, proceed to the single-instance
PC/Xbox projection comparison in Phase 2. This ordering prevents another long
cycle in which cull logs are debugged on top of a corrupt primitive stream.

