# ctr360 continuation — console performance/hub candidate, 2026-10-12

Workspace: F:\downloads\temp\python\hermes\ctrport\ctr360.
Read the current HANDOFF.md checkpoint and research/20261012_hardware_performance.md.
Older checkpoints are historical. ../repos is read-only; preserve dirty work.

Real Xbox startup, saves, loads and logging are USER CONFIRMED for the preceding
candidate. They defeated boss 1, then froze entering the unlocked N. Sanity Beach
hub door. Their original ../ctr360.log is archived unchanged in
build-360/results/20261012-hardware-user/ with PE/map/disassembly.
First fault LibraryOfModels_Store reads 0x616b7562 (akub), then LevInstDef_UnPack,
from LOAD_Hub_SwapNow. Inactive hub memory reused by masks/bosses left level2 stale.
Native code invalidates that pointer, retains destination ID, drains/reloads before
swapping. Focused actual-function lifecycle test passes; old policy fails.

Extreme slowdown samples overlap old 12,000-line essential instance-probe windows
and per-frame USB log flushes. Nested probes/captures now opt-in, VRAM default off;
no forced frame flush or routine stdout; durable faults/guards/boot stay immediate.
Audio status logs outside mixer lock. No diagnostic RT query in UpdateVRAM.
Five-second perf frame period avg/max; compile timestamp and exact linker map.
Host trace/log/audio-boundary, effects, HD and Xbox asset/path fixtures pass.
Full mirror AST passes (2533 hoists, no notes/designators/failures), Release has
zero errors / 87 existing warnings. Source audit zero hazards across 255 files.

Ready-to-copy: build-360/releases/ctr360. Assets included, unchanged image.
Memcards independently verified unchanged; preserve them and settings each refresh.
No ZIP/old siblings. Normal physical inputs; 720p/16:9/filtering/edge AA remain.
Racing targets 60-render/30-simulation; hubs remain 30-render. No new hardware FPS,
hub traversal or previous individual effects acceptance claim. User reserves
actual gameplay testing; NO Xenia launched. Do not launch unless newly requested.

XEX: 1b81644d4424e8e465ce5308d3f1e18eea2c018b9625de8744f3ab729b2d56b1
Image: 4f46a7420687d96bc0ba0a233f46bda2f27c74c2c902fe55d0ae05bd2dd9cfa1
Boot: built Oct 12 2026 10:15:18
Map: build-360/results/20261012-hardware-perf.map

Next: user's unlocked-door/back traversal, racing and pause/unpause feedback.
If any stall/fault remains, inspect fresh load/perf/fault log before further fixes.
Build: bash tools/ctr360/build_xex.sh Release. Broad/header/generator changes:
full build_360_mirror.py --root F:/downloads/temp/python/hermes/ctrport/ctr360
--out F:/downloads/temp/python/hermes/ctrport/ctr360/build-360/gen --verify-syntax.
Never hand-edit mirror. stage_release.py refreshes only distributables/cards safe.
