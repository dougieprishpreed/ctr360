# ctr360 continuation checkpoint — 2026-10-11 (HD candidate ready)

Workspace: F:\downloads\temp\python\hermes\ctrport\ctr360. The reference repos
under ../repos are read-only. Preserve existing uncommitted work.

Read the top of HANDOFF.md and research/20261011_hd_graphics.md first. Earlier
wheel/scene, loader/flag/audio and September checkpoints are historical.

The user reports full playability; memory-card saves say full and are still
unfixed. Their new request is 720p smoothing, true widescreen, a 60 FPS target
and good native Xbox 360 performance. The hardware candidate ZIP is
build-360/releases/ctr360-hd-720p-20261011.zip; the tested complete staged folder
is build-360/xex/dist. The user will test it on a real console.

Implemented: native 1280x720 main target/direct full-color presentation,
horizontal 16:9 projection/frustum expansion, centered 4:3 UI, decoded-world
bilinear filtering preserving nearest alpha/STP classification, and edge AA.
Single-player racing adds render-only camera/instance midpoint frames for 60 FPS
presentation with the original 30 Hz simulation. Loading/menu/pause/end-of-race,
adventure and split-screen keep their original route. Midpoints restore OT/DB
cursors/poses/flags and do not overwrite the legacy feedback image. Countdown
visuals and idempotent texture selection keep both renders coherent.

Release: zero errors, 85 warnings. Full absolute-root regeneration and audited
unit AST parsing pass; actual midpoint fixture and Xbox 360 fxc shaders pass.
EDRAM layout: 1856/2048 tiles. Do not hand-edit the generated mirror.

Visual 70-second minimized test: build-360/results/20261011-hd-candidate-3.
Actual final 1280x720 captures show attached wheels during acceleration/turning,
coherent HUD/countdown/banner and different intermediate/current world poses.
Production 70-second minimized test: 20261011-hd-production, zero faults/packet
errors, captures disabled, sustained 59.14–60.01 render FPS/~30 simulation Hz.
Only an aspect comment/rebuild separates those tests. Physical hardware is
unverified. An accidental Adventure test logged packet errors; compare that
route against the saved baseline before attributing them to HD.

Tested XEX SHA-256: 0941d2682d5c150ba63ea9abeb916f8816b7f80e087b117bdff2fa2b9a0837c8
Cooked/staged image: e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0
Prior accepted playable XEX preserved at
build-360/results/20261011-playable-baseline/default.xex.

Normal player input is restored, capture/script files absent, and Xenia stopped.
Build: bash tools/ctr360/build_xex.sh Release. Header/generator/broad changes
require full regeneration with an absolute root and successful host AST parsing.

Use short minimized runs only as required, await completion in a tool call,
archive after shutdown and restore controls. 20261011-hd-run.py stages ordinary
menu/pad inputs and restores settings in finally; capture mode 2 captures only
enhanced output, 0 disables captures. Never poll live Xenia, edit its sleeping
runner, replace live staged assets/XEX or open a separate PSX reference emulator.

ctr360_output_fNNNN_i/f.tga is the actual post-AA enhanced backbuffer, ordinary
1280x720 24-bit TGA. Its PNG preserves native dimensions. ctr360_display_fNNNN
is only the legacy framebuffer side channel. Packed whole VRAM is not an ordinary
framebuffer. Judge pixels, never counters/checksums alone. Graphics settings
interpolation/texture_filter/edge_aa default to 1; interpolation 0 retains
720p/widescreen with the original 30 FPS route. Restart to apply settings.

Next: the user's physical-hardware feedback, broader tracks/modes/effects and
save failure. Do not claim console performance, full race coverage or saves
without testing them. Previous prompt archived at
research/next_session_20261011_pre_hd_archive.md.
