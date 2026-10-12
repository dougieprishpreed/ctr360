# 720p, widescreen and race interpolation candidate — 2026-10-11

The user reports the previous build fully playable and asks for improved
graphics, a 60 FPS target, true widescreen and Xbox 360 hardware compatibility.
Memory-card saves were implemented in the subsequent checkpoint; see
research/20261011_memory_cards.md. Open-save/garage notes below describe this
earlier HD checkpoint and are superseded there.
This candidate is ready for the user's real-console test, not yet validated
on physical Xbox 360 hardware.

## Rendering changes

`platform/xbox360/native_xbox360_video.c` now rasterizes the main scene at
1280x720 instead of 512x216. Presentation uses the resolved full-color target
before the legacy framebuffer's five-bit quantization. Packed PSX VRAM remains
a side channel for screen copies, framebuffer feedback and game CPU reads.
Intermediate frames resolve for presentation but never publish a new legacy
framebuffer. Offscreen texture pages and CLUT sampling retain their native
dimensions and point sampling of the packed VRAM representation.

`game/PushBuffer.c` scales the world ViewProj X row and X translation by 3/4,
leaving vertical projection unchanged, and expands the horizontal visibility
frustum by 4/3. This reveals more horizontal geometry instead of stretching
the existing 4:3 view. Explicit LE loads/stores preserve mixed matrix layout.
UI PushBuffer packets carry reserved E5 bit 23; decoded GPU split state retains
the marker. The shader centers authored UI in the middle 960 pixels of the
1280-pixel output. World and UI clips scale to the physical render target.

World texture filtering decodes four PSX texels and interpolates their colors,
never their palette indices. Transparent texels do not introduce black fringes;
nearest-texel coverage and STP classification preserve the game's transparent
and semitransparent passes. UI and offscreen texture-page draws use point
sampling. Dither is disabled on the enhanced main raster and retained for
offscreen PSX operations. A directional FXAA-style presentation shader smooths
polygon edges. Hardware bilinear filtering is used only on decoded full-color
presentation data and restored to point sampling afterwards.

This improves rasterization and filtering of the original assets; it does not
replace low-resolution textures, increase model detail, or implement PGXP-style
subpixel/perspective correction.

## 60 FPS target and state boundaries

`game/MAIN/MainHD.c` adds a render-only midpoint between successive single-player
race simulation states. Camera position/rotation and dynamic instance matrices
interpolate; rotation halfwords remain LE while instance translations are
native. It rebuilds visibility and renders the world, wheels and shadows,
then replays decoded UI from the last complete frame. Countdown visuals are
drawn without their audio trigger or previous-timer write. Texture selection
is an idempotent function of the current timer and matches both renders.

Simulation, input processing, race timing, animation updates and audio retain
the existing cadence. VBlank input/audio callbacks still run at their existing
rate. Midpoint presentation consumes one of the normal two VBlanks. Menus,
loading, pause, adventure hubs, end-of-race menus and split-screen retain the
original route. Level changes, large camera cuts and teleports suppress
interpolation. This is 60 FPS presentation with 30 Hz simulation, not a full
60 Hz physics conversion. The partial reference FPS macro set was audited
read-only and not applied.

The pass appends primitive bytes after any existing packets, backs up/restores
the OT and DB cursors, and restores dynamic instance matrices/flags and camera
state. It does not run GameLogic, menus, pickups or particle ticks twice.
Rendering effects beyond the tested Time Trial route still need broader
validation; the midpoint uses a bounded set of rendering calls rather than
repeating the full stateful MainFrame_RenderFrame.

## Xbox 360 constraints and validation

The XDK's `XGSurfaceSize` returns EDRAM tiles, not bytes. The explicit layout
uses 416 tiles for the packed-VRAM bridge, 720 for main color and 720 for main
stencil/depth: 1856 of 2048 tiles. Small offscreen color/stencil targets reuse
the bridge reservation after resolving, keeping the live main target separate.
An offscreen surface whose combined color/stencil exceeds that reservation
is rejected with an error. Broader preview/effect dimensions remain to be
tested. No multisample tiling or duplicate geometry passes are required for AA.
Four vertex buffers use synchronized locks instead of repeatedly issuing
NOOVERWRITE against offset zero while prior GPU draws may still consume it.

The real Xbox 360 `fxc.exe` compiles the geometry, edge-AA and all three PSX
texture-format shaders successfully. Release MSBuild passes with zero errors
and 85 warnings. Full regeneration from the absolute source root passes 246
units, 2532 declaration hoists, zero manual-review notes, zero remaining
designators and zero host AST failures (`20261011-hd-mirror.log`). Later MainHD
changes use the audited standalone AST transform; XDK-only code is compiled
directly by MSBuild. The mirror was never hand-edited.

The actual-function fixture `20261011-hd-contract.py` checks mixed-endian pose
interpolation, angle wrapping, preservation of prior packet allocation,
pose/flag/DB/OT/timer restoration, pause/level/camera/split-screen guards and
EDRAM capacity. It passes. Device compilation remains essential: the first
build caught incorrect SVec3 member assumptions and a C89 declaration-order
error in diagnostic code; both are corrected.

Primary guidance consulted: Microsoft's
[bilinear filtering documentation](https://learn.microsoft.com/en-us/windows/win32/direct3d9/bilinear-texture-filtering),
NVIDIA's [color-key filtering guidance](https://developer.download.nvidia.com/assets/gamedev/docs/ColorKey.pdf),
and the local XDK `xgraphics.h` and `CustomEDRAMAllocation` sample. The local
Xbox shader compiler, allocation API and actual console device path drive
implementation; emulator tolerance is not evidence of real-console performance.

## Short minimized tests and visual evidence

All runs were launched minimized, awaited through the runner, stopped and
archived. No live XEX/assets were replaced, no sleeping runner was edited and
no separate PSX emulator was opened. Tests use ordinary menu/controller input.

- `20261011-hd-candidate-1`: 65 seconds requested. The early down input was
  ignored during title animation, selecting Adventure instead of Time Trial.
  That route logged 1375 packet failures. This is not a passing race test;
  isolate whether those Adventure packet faults also occur on the saved
  baseline before attributing them to HD. They remain a follow-up finding.
- `20261011-hd-candidate-2`: 65 seconds, corrected menu timing, zero faults or
  packet errors; Crash Cove loads. Actual midpoint captures revealed missing
  countdown lights and a stale animated banner texture, despite clean logs.
  The pure countdown draw and idempotent texture selection repair those.
- `20261011-hd-candidate-3`: 70 seconds (74.04 wall), zero faults/packet errors.
  Final post-AA captures at 1280x720 show coherent crate characters, race HUD,
  attached wheels, acceleration and steering. Frame 1368's midpoint retains
  the countdown and CTR banner. Frames 1568, 1623 and 1648 show driving; the
  `_i`/`_f` pairs contain different camera/geometry poses with coherent wheels
  and stable HUD placement. Capture readbacks cause temporary stalls, so its
  rates are not production performance evidence.
- `20261011-hd-production`: 70 seconds (73.98 wall), video/audio file captures
  disabled, zero faults/packet failures. It loads normal Crash Cove Time Trial
  and drives using the same script. Eight steady 120-present windows report
  59.14–60.01 render FPS and 29.57–30.00 simulation FPS. The initial level
  window is 48.81/29.69 while midpoint history and camera guards settle.
  Audio device output has zero failures. This validates emulator pacing only;
  the user must measure/assess the console candidate.

**Capture contract:** `ctr360_output_fNNNN_i/f.tga` is the actual final enhanced
backbuffer, post-AA, 1280x720 ordinary 24-bit TGA. Its PNG conversion preserves
native dimensions. `ctr360_display_fNNNN.tga` is now only the legacy displayed
VRAM rectangle and must not be used to judge HD output. Whole packed VRAM dumps
remain unsuitable as ordinary framebuffer images. Frame counters or checksums
alone never establish visual acceptance.

The final production XEX differs from candidate-3 only by the corrected
presentation-aspect comment and its rebuild. No rendering behavior changed
after the candidate-3 visual inspection. See current HANDOFF for identities.

## Controls, diagnostics and next test

Physical controller input is restored: test script and capture file are absent
after shutdown. `ctr360_capture.txt` is opt-in: 1 includes legacy diagnostics,
2 captures only enhanced output, 0/absent disables GPU capture readbacks.
The hardware package contains neither that file nor a controller script or
audio capture settings. Optional `assets/ctr360_graphics.txt` accepts:

```
interpolation 1
texture_filter 1
edge_aa 1
```

Defaults are all enabled; restart to change them. Set interpolation to 0 for
a 30 FPS fallback while retaining 720p/widescreen, or individually disable
filtering/AA when isolating hardware issues. The package includes an inactive
example file. Preserve the prior accepted XEX in
`build-360/results/20261011-playable-baseline/default.xex`.

Next: the user's real Xbox 360 test of loading, driving, geometry, smoothing,
audio/input and pacing. Broader tracks/modes/effects and a complete lap remain
untested for this candidate. Memory-card full is still open; do not claim saves
or physical hardware compatibility/performance have been verified.
