# ctr360 continuation checkpoint — 2026-10-09

Project: native Xbox 360 source port of Crash Team Racing using the user's own
PSX dump. Workspace: F:\downloads\temp\python\hermes\ctrport\ctr360.
The reference repos under ..\repos are read-only.

Read the current checkpoint at the top of HANDOFF.md and
research/20261009_graphics_debug.md. Older September notes are historical.
Do not infer graphics success from frame counters or checksum changes.

Current Release builds with zero errors and renders a coherent Naughty Dog
crate with readable textures beyond copyright. Evidence is in
build-360/results/20261009-clock-display*.png and the corresponding guest log.
The old malformed control commands and tangled animation geometry are fixed.
An old logging insertion had detached clockSend-- from its conditional,
wrapping zero to 255 and causing persistent blur; that is also fixed.

Build: bash tools/ctr360/build_xex.sh Release. The build reuses the mirror and
syncs audited changed units. Headers/generator/broader source changes require
full regeneration using an absolute source root; do not hand-edit the mirror.
Host AST parsing must succeed. XDK files are compiled directly by MSBuild.

Test: CTR360_READBACK=full bash tools/ctr360/run_xenia.sh <seconds> '<pattern>'.
Launch minimized, archive results, and await completion inside a tool call.
Do not repeatedly poll the process, edit its sleeping shell script, or open a
separate PSX reference emulator. The user's two reference JPEGs are in the
parent workspace. ctr360_display_fNNNN.tga is the final displayed VRAM
rectangle decoded to ordinary 24-bit TGA. Main-target captures can be taken
before a feedback effect. Whole legacy VRAM dumps include packed textures and
CLUTs and are not ordinary viewable framebuffer images.

The 250-second verification run completed with zero faults/packet errors and
Xenia stopped. The later flag lacks correct checker coloring, and the loader
repeatedly stays at stage 6. Next: fix those graphics/loading issues, then title,
performance, audio, input, and racing.
Specific remaining faults: track mesh fields are still raw LE; animation-word
stores span animFrame/vertSplit with BE semantics; packed clear-color writes
span byte fields incorrectly. Check evidence and scope each repair. The crate
level has zero mesh, so the track mesh issue does not explain the fixed crate.
Do not claim gameplay/audio/input success without testing them.

Previous prompt archived at research/next_session_20260920_archive.md.
