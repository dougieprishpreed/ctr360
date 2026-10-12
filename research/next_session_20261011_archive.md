# ctr360 continuation checkpoint — 2026-10-11

Project: native Xbox 360 source port of Crash Team Racing using the user's own
PSX dump. Workspace: F:\downloads\temp\python\hermes\ctrport\ctr360.
Reference repos under ..\repos are read-only. Preserve existing uncommitted work.

Read HANDOFF.md's top checkpoint, research/20261010_flag_loading.md and
research/20261009_graphics_debug.md. Older notes are historical. Never infer
graphics success from counters/checksum changes; inspect final display pixels.

Current goal: continue until the demo race works. The user explicitly resumed
work after the break and requires every Xenia run to be minimized. Title, full
flag animation, menu text, audible title music and good title performance were
confirmed by the user; race rendering/controls/audio are not yet accepted.

Latest user steering: automate ordinary button inputs and test Time Trial/Crash Cove for faster iteration. The first-render freeze is cleared by cooking standalone racer Models in entries242..257/308..323/332..347. The completed minimized20261011-time-trial-racer-assets run shows Crash, textured Crash Cove and an advancing race timer, but2783malformed HUD packets. Native numeric lengths/opcodes now repair the allocator/meter/driver-icon/speedometer boundary. Actual host packet fixtures pass; full regeneration20261011-hud-packets-mirror-retry.log passes2532hoists/0syntax failures/review notes/designators; Release0errors/85warnings. Minimized150-second20261011-time-trial-drive-hud is running via20261011-scripted-run.py and20261011-time-trial-drive-pad.txt. Await completion/archive before further runtime work. No driving/demo/race-audio acceptance yet. See HANDOFF's latest block; older active-run statements below are historical.

The original idle route loads Oxide intro level 30 before a later real demo.
External LEV/PTR entries 516/517 were uncooked. Their repaired data lets the
200-second 20261010-external-map-runtime run pass stages 7/8/9 and enter camera
initialization. The camera searches raw mesh/BSP numeric fields, exposing the
next scoped format fault. That run completed and Xenia stopped.

The cooker now handles 34 external LEV/PTR pairs and 564 regions, and uses the
renderer's physical keyframe count for interpolated animations. Mesh counts,
quad indices/bitfields/bounds/normals, vertex positions/flags, BSP branch/leaf/
hitbox fields, driver spawn positions, startup/scenery/rain/stars/checkpoint/
spawn numbers and AI navigation headers/frames are native numeric values.
PVS/RLE, vertex RGB, draw_order_high's four bytes, clear RGB, TextureLayout,
OVert samples, skybox and segmented camera paths retain byte/LE contracts.
Consumers pack native vertex coordinates explicitly and read visibility words
as LE after any RLE decoding. Actual cooked entries 1/13/216/514/516/519 pass
numeric and byte-preservation fixtures. Navigation numPoints is a last index,
so paths store numPoints + 1 frames; BOTS rewrites the retail `last` pointer.

Full mirror regeneration with an absolute root passes: 2530 hoists, zero manual
review notes, zero leftover designators, zero host syntax failures. Release
builds with zero errors and 81 warnings. Current candidate identities:
Last tested ground-render diagnostic XEX:
b7c4f4f8a19d125294dc317640fe77ca1507e3ec6c0e48a5153aed080a3492d3
Cooked/staged: c45a692d8d1a16576b48e4d4d7321b903957633b41e7db86d545c18e2daa7832

The native-mesh run completed without reaching a race. Scoped diagnostics
located the frame 1713 stop at static `intropura`'s first vertex: its raw LE
vertexOffset 0x1c read as 0x1c000000. Static ModelFrame coordinates/offsets now
cook alongside animated frames. All 564 regions validate; 41,734 frames in 212
asset regions preserve numeric values, opaque blocks, and packed first vertices.
Static frame repairs clear the 1713 freeze. Direct model colors beyond the
scratch cache now cook from actual command references: the ship caches 26 but
uses indices through 63. 636,602 command/color words in 212 regions match retail.
The completed minimized 300-second 20261010-command-colors-runtime run plays
later intro models, returns to the title, and requests Crash Cove (level 3).
It then stalls during the demo-track load near frame 5550. Zero packet/fault
reports are not race acceptance. 20261010-demo-load-trace completed minimized,
reaching frame 5561 at stage 6. New bank/song/file/init and terrain markers pass
full regeneration and Release. 20261011-demo-bank-steps is their minimized
five-minute run completed. Music finishes at frame 5557; the loader's last
marker is stage 7 entry at frame 5561, after the level file loads. Valid
one-letter track model names caused model and instance scalar cooks to be
skipped for the whole level. Their validators now accept nonempty names.
69,633 model/header/instance scalars across 139 levels match original values;
all frame and command/color fixtures still pass. Overlay 226 now packs native
viewport w/h and reads native projected-center fields. The bad LE viewport
read rejected visible terrain; the completed trace has visible leaves and
zero emitted polygon bytes. Full regeneration and Release pass. The minimized
300-second 20261011-track-models-runtime verification completed minimized;
Xenia stopped after 303.93 seconds. The race loader and driver/instance/camera
initialization finish. Terrain emits polygons, but display5000 is black apart
from the DEMO label. 266 packet-error report lines start at skidmarks; game
progress stops near5095. No race is accepted.

The next candidate fixes camera runtime vectors/native world translations,
LE vehicle rotation matrices and their connected physics/model readers, BOTS
normal extraction, baked animation scale matrices, skidmark/shadow packet
fields, and overlay226's mixed depth/clip midpoint and native position transfer.
Actual function host fixture and PPC compilation pass. Full mirror regeneration
passes (2530 hoists, zero host failures/review notes/designators); Release has
zero errors and85 warnings. 20261011-race-camera-runtime completed minimized
(403.94 seconds, Xenia stopped,0 faults,174 packet-error reports). Progress
continues through3/6/4 to10620 but captures5031/5631/6111 show sky and missing
track/racers. No race accepted. The late malformed packet is a raw weather
draw-mode write, now repaired in source.

Attract/EOR camera records (SpawnType1 entry2) were still LE while CAM_ThTick
reads native halfwords, indexing outside the mode-size table. Their cooker now
validates and converts those halfwords, preserving segmented entry3 paths.
The actual fixture passes7820 scalars/1112 records/72 tables; four shared zero
path/EOR headers stay unchanged. All564 regions check/cook and new assets are
staged. 20261011-demo-eor-asset-runtime is a300-second minimized run using the
previous verified XEX to isolate this repair. That test completed minimized:
303.93seconds, stopped, zero faults/packet errors. It shows moving recognizable
racers with bad blue/missing terrain. The weather/diagnostic mirror passed2532
hoists,0syntax failures/review notes/designators; Release0errors/85warnings.
XEX3689ac7cecadfb6ebff3447f3ccacddc270249cd9bd970e748d9d04cf8a978d6 was
tested in20261011-demo-terrain-trace:303.95seconds minimized, stopped,0faults/
packet errors, same bad terrain. Camera/world/GPU tags were filtered as MISC.

Overlay226 now decodes raw texture clut/tpage and replaces9numeric UV-half
writes/14reads with explicit masks/shifts. Mosaic+0x24 chooses a validated
native ptrmap pointer or raw inline UV word; entry25 has83mapped/37inline.
The actual function fixture20261011-terrain-uv-fixture.py/.log passes UVs,
clip pages, mosaic words and original pack bounds; PPC compilation passes.
A proposed bounds change failed the fixture and was reverted before build.
Full regeneration passes2532hoists,0syntax failures/review notes/designators
in20261011-terrain-uv-mirror.log. Audited MainFrame/nativeGPU units then sync/
verify bounded diagnostic prefix fixes; hb now makes those tags visible.
Release0errors/85warnings. 20261011-demo-terrain-uv-runtime completed minimized
403.89seconds, stopped,0faults/packet errors. Display1800 shows textured road/
scenery,3000Oxide. It stops at cutscene gameframe3550 after requesting/preloading
level33(op39 wait140); audio played5871298 then staysconstant. No race capture.
NativePerf is CTR_INTERNAL gated; this Release creates no timing CSV.
Audited MainFrame adds scoped game-step markers for3000..4200; Release passes.
20261011-intro3550-trace completed minimized243.89seconds, stopped,0faults/
packet errors. Frame3548(level32->33 request) returns all buckets/BOTS/audio and
game-exit withqueue3/ready1/load1. Stop follows game logic, entering rendering.
Full regeneration for render/instance fences passes2532hoists,0syntax failures/
review notes/designators; Release0errors/85warnings. 20261011-intro-render-trace
completes minimized243.92seconds, stopped,0faults/packet errors. Models all
finish; the stop lies before level-exit. Expanded ground/terrain fences pass
full regeneration/Release. 20261011-intro-ground-trace completes minimized
243.95seconds, stopped,0faults/packet errors. Its buffered guest tail misses
markers; durable Xenia log shows ground effects/terrain setup returning, then
dynamic rendered bucket2 entering at3546 without returning. Deepest mosaic
source index0x320 and bias0x3d8 are frame+0xb4 words stored LE but read natively.
Slot12 becomes201326592 on PPC. All three reload paths now decode those words
through a shared helper. 20261011-mosaic-offset-fixture.py/.log passes294 actual
function cases and PPC compilation; inspected assembly reconstructs LE bytes.
Full regeneration is active in20261011-mosaic-offset-mirror.log; do not edit
source until it ends. Xenia is stopped. Next build/run400seconds minimized;
must inspect moving, coherent actual race output. No race is accepted yet.
Bounded race-entry-relative display captures and GameLogic/render/world-state
markers support the next minimized run.
No loader stages or game flags were bypassed.
Later display captures include 1200/1500/1800/2400/3000 and 4000..10000,
12000/15000 so intro/race output can be judged directly.

Build: explicit C:/Program Files/Git/bin/bash.exe tools/ctr360/build_xex.sh Release.
Audited units sync; header/generator/broader units require full regeneration
using an absolute source root. Never hand-edit the mirror. Host AST failure is
fatal; XDK files compile directly through MSBuild.

Test: CTR360_READBACK=full bash tools/ctr360/run_xenia.sh <seconds> '<pattern>'.
Launch minimized, await completion within tools, archive captures/logs/identities.
Do not repeatedly poll Xenia, edit its sleeping runner, or launch a reference
PSX emulator. The helper 20261010_font_audio_run.py restores trace/audio flags
and 20261010_archive_run.py verifies Xenia stopped. Final display TGAs are normal
24-bit images; whole legacy VRAM contains packed textures/CLUTs. Main captures
may precede feedback effects. Controller input from another game can skip
scenes/select menus while Xenia is minimized; keep normal skipping enabled.

Previous prompts: research/next_session_20261009_archive.md and
research/next_session_20260920_archive.md.
