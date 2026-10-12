# ctr360 — HANDOFF (current state of work)

## Current checkpoint — 2026-10-12, real-console performance / hub lifetime candidate

Read research/20261012_hardware_performance.md first. User confirms the prior
candidate boots/runs on real Xbox via Aurora, saves/loads/logs work, and boss 1
was defeated. This supersedes the earlier unconfirmed hardware-startup status.
Individual effects from the prior batch still need visible confirmation.
User reserves gameplay testing; NO Xenia was launched for this candidate.

Their USB log ../ctr360.log is archived unchanged in
build-360/results/20261012-hardware-user/. It ends in an application access
fault during LOAD_Hub_SwapNow, after entering the unlocked N. Sanity Beach
hub door: LibraryOfModels_Store reads 0x616b7562 (ASCII akub), followed by
LevInstDef_UnPack faults. Archived PE/relinked map/disassembly confirm the
relevant function bytes and addresses. Mask/boss assets overwrite the inactive
hub mempack but previously left level2 pointing into it. Native code now
invalidates level2 while retaining its destination ID; matching IDs require a
resident pointer, and SwapNow drains pending loads/reloads before model/mesh
access. Invalid destinations/routes defer or skip. No new asset swaps.

Worst slowdown log samples overlap 12,000 old per-instance probes (~538 lines
per affected simulation frame) accidentally classified as essential/guest stdout.
Also 22,968 VRAM trace lines and forced durable USB flush every rendered frame.
Nested hb probes now require watch; default boot/title mask excludes vram/watch.
Detailed helpers/captures are opt-in; faults/guards/sparse heartbeat stay visible.
No per-frame log flush or routine stdout mirror; periodic batches retain immediate
fault/boot durability. Audio status logging releases the mixer lock first.
UpdateVRAM removes diagnostic RT queries; GPU upload semantics are retained.
Five-second perf period average/max reports help diagnose remaining stalls.
These remove concrete overhead; hardware performance improvement awaits retest.

Actual hub lifecycle fixture passes mask/boss overwrite, destination retention,
queue drain, fresh reload, cached return and invalid destination cases. Previous
policy fails as a negative control. Actual trace/log/BeginScene/audio-thread
fixtures pass, including fault durability and unlocked status logging. Existing
effects/HD and strict Xbox path/disc/missing-image fixtures pass. Source audit:
255 C files, zero hazards, 37 reviewed word sites, 737 inventory entries.
Full absolute-root mirror: 2533 hoists, zero notes/designators/host AST failures.
Release: zero XDK errors / 87 existing warnings. Build now generates a linker map;
boot identifies compile timestamp. Never hand-edit the generated mirror.

Ready-to-copy folder: build-360/releases/ctr360, assets present, no ZIP. Existing
memcards file independently hashed before/after and unchanged. Preserve cards
and personal settings on console/update. Normal player input enabled. Retain
720p/true 16:9, filtering/edge smoothing, 60-render/30-simulation racing;
Adventure hubs retain 30 Hz rendering. No stable 60 FPS or new gameplay claim.
Assets unchanged from the previous effects candidate.

XEX: 6d266d1ed98380970bade70a9d21052100b85b8a6c8f43a213ed93235cdb03d6
PE: bf0598455393195d18e359ce6fab462fdd2d71325209c2dcdfa725b3c68340c3
Image: 4f46a7420687d96bc0ba0a233f46bda2f27c74c2c902fe55d0ae05bd2dd9cfa1
Boot: built Oct 12 2026 10:15:18
Exact map: results/20261012-hardware-perf.map. Detailed evidence/fixtures/build
logs/release identities are in research/20261012_hardware_performance.md.
Previous checkpoint/prompt archived as 20261012_pre_hardware_performance_checkpoint.md
and next_session_20261012_pre_hardware_performance_archive.md in research/.

Next: user's hardware retest through the unlocked door and back, then races and
pause/unpause. Obtain the fresh log if any fault/extreme slowdown remains; inspect
load/perf records before further changes. Do not launch Xenia unless newly
requested. Hardware-test confirmation is required before claiming these outcomes.
../repos is read-only; preserve the extensive preexisting dirty work.
Build: bash tools/ctr360/build_xex.sh Release. Broad/header/generator changes
require full regeneration with an absolute root and --verify-syntax.
Release refresh: tools/ctr360/stage_release.py preserves cards/settings.
Publication prep: end-user README and tracked tools/ctr360/ctr360.vcxproj
bootstrap verified; incremental Release zero errors. XEX repackaged, PE/assets
unchanged. Staging now writes graphics example and end-user release instructions.

---

# ctr360 â€” HANDOFF (current state of work)

## Current checkpoint â€” 2026-10-11, effects / broad endian candidate

Read research/20261011_effects_endian.md first, then the retained hardware
startup and Adventure/HD reports. The user reserved gameplay testing for
themselves and requested a larger batch of repairs. NO Xenia was launched for
this candidate. Do not infer visual success from compilation/audit counts.
The real Xbox startup problem remains unconfirmed; hardware retest is deferred.

Candidate repairs: confetti LE rotation/native clipping bounds; missile-box
native coordinate copy; mask/shield/cloud attachment native world translation;
native particle flags/oscillator fields and field-aware streak RGBC/XY packets;
warpball flags; 77 minimap metadata records cooked. Wider fixes cover rotation
elements in hazards/Adventure/reward/burst models, MatrixToRot, hitbox inverse,
lighting/audio/collision MAC outputs, plant cameras, raw plant/orca delays,
numeric camera IDs/menu state. Native water inherited OT links are bounded.
The water fix is not established as a cure for the user's visible water glitch.

All visible effects need user confirmation: podium confetti, incoming missile
target, invincibility mask/shield, Mystery Caves fireballs, lightning orb and
minimap racer markers, and post-finish Crash Cove water. Retain 720p/true 16:9,
filtering/edge smoothing and 60-render/30-simulation single-player racing.
Normal controller inputs are enabled. No new FPS/hardware/audio acceptance.

Focused actual-function effects and HD midpoint host fixtures pass. Strict
Xbox path/disc/asset fixture passes with the new staged ISO. Source audit:
255 C files, zero high-confidence hazards, 37 reviewed word sites, 737 boundary
inventory entries. New detector rules cover matrix elements/runtime MAC and
translation APIs, particle halfword crossings/streak packets and scalar bytes.
37 individual review rationales: results/20261011-effects-word-review.json.
This is not a full C type checker or proof of all engine formats.

Independent asset checks: Model graph 5,058,863 numeric fields; new Level
audit 9,465,171 fields across 139 levels, 167,810 quads, 897,586 vertices,
77 minimaps and 1,112 EOR cameras. 9,388,660 opaque water/color/UV/draw-order
bytes remain unchanged. Old image negative control fails 640 minimap fields;
new image has zero failures. Only 1,280 minimap bytes changed in the image.
Mapped non-Model entries 220/607 remain outside Model-format coverage.
Both independent audits run after cooking.

Full absolute-root generation: 2533 hoists, zero review notes/designators/host
AST failures. Release: zero XDK errors / 87 existing warnings. Broad/header
changes require full regeneration; never hand-edit the mirror. XDK platform
units compile directly. Build: bash tools/ctr360/build_xex.sh Release.
References ../repos are read-only; preserve the extensive existing dirty work.

Ready-to-copy release: build-360/releases/ctr360, including new assets.
Same folder every release, no ZIP. No old siblings remained. Existing
memcards/slot0/BASCUS-94426-SLOTS was hashed before/after and preserved.
Keep memcards and personal settings. tools/ctr360/stage_release.py refreshes
only distributable files and verifies saves; results/release-current.json.
Update BOTH default.xex and assets/ctr-u.bin in installed copies.

XEX: 0c3fea4f30393b66b2a37ffb59d544f795d43e44c59e8ba7094caa2442ea5b22
PE: fb8a0096260882ef66470c5c865c3583a8c1dffeed70fabcf69e4cbde5398dc6
Cooked/staged/released image:
4f46a7420687d96bc0ba0a233f46bda2f27c74c2c902fe55d0ae05bd2dd9cfa1

Detailed evidence paths are in research/20261011_effects_endian.md.
Prior checkpoint/prompt preserved in research/20261011_pre_effects_checkpoint.md
and research/next_session_20261011_pre_effects_archive.md. Older notes below
are historical. Keep all checkpoint edits UTF-8.

Next: user's gameplay feedback and scoped repairs to what remains. Do not
launch an emulator unless newly authorized. If hardware startup still fails,
obtain the fresh cache:\ctr360.log (fallback game:\, hdd1:\, usb0:\).
The earlier log stopped before platform init; do not blame the exploit without
evidence. Preserve the path/error/checkpoint fixes in improved builds.

---

## Historical checkpoint â€” 2026-10-11, Xbox hardware startup candidate

Read research/20261011_hardware_boot.md first, then the Adventure warp/HD
reports below. The latest actual console launch via Aurora/ABadAvatar returned
to the dashboard after Base: game: / Assets: game:/assets, before any platform
line. The log does not establish the exact failing call or an exploit issue.

NativePath now preserves named-device root separators and uses backslashes
under _XBOX. The fake chdir/GetFileAttributes(root) gate is removed. All asset
validation stderr writes use Platform_LogError; logger batch flushes drain the
CRT buffer. New durable checkpoints cover disc open/root, validation, memcard
root, platform, scratchpad and pointers. Open errors record errno/Win32 values;
early failures close the log and failed platform initialization stops game
entry. No cooked-image changes in this build.

Strict actual path/disc/asset fixture passes with real staged ISO and a missing
image failure, rejecting any forward slash/bare device root at the file API.
Host and Xbox-policy save/reload/failed-write/ghost tests pass in isolated dirs.
Full absolute-root mirror: 2533 hoists, zero review notes/designators/host AST
failures. Release: zero XDK errors / 87 warnings. XDK platform files compile
directly; no mirror hand edits.

Minimized positive run build-360/results/20261011-hardware-boot-1: 24 seconds
requested / 28.07 wall. Correct game:\ and game:\assets paths, disc-ready,
Assets validated, Platform ready and CTR_Main. Zero startup/fault/packet/link/
asset/host-kernel failures. Inspected f0300 main/display captures show coherent
textured crate with sparks. Five-second missing-image run persists open and
validation errors + LOG CLOSED with no game entry; image restored in finally.
Xenia stopped, settings restored, physical inputs normal. These short tests
do not add gameplay/audio/performance/hardware acceptance.

Current ready-to-copy release: build-360/releases/ctr360.
No ZIP; use this same folder every release, with all assets. The user permits
removing older release siblings when a new release is created. Preserve
build-360/releases/ctr360/memcards and personal settings between builds.
The existing save tree was hashed before/after and unchanged. Refresh with
python tools/ctr360/stage_release.py after updating the dist README; it updates
only XEX/README/cooked image/inactive graphics example and verifies saves.
Metadata: build-360/results/release-current.json. There were no old siblings.
XEX: c0c339502a303798bd4a92d7b7fe692eeede26117530a07f802764050ffa5ffb
PE: 2c7712f737e22445d69ad57df839c28942a3e947859e4acd8f9d70ceb3b2ddf6
Cooked/staged/released: 2a8ac32de65e37155024dbf55e7f176d73654965ffc911bd2e2dc38c73704984

Real Xbox boot, performance and saves remain unverified. Next: user's hardware
retest and fresh cache:\ctr360.log if it fails (fallback roots game:, hdd1:,
usb0:). Use the last new checkpoint to scope the next repair. Build/test rules
below still apply. ../repos read-only; preserve existing dirty work. Always use
UTF-8 when editing checkpoint files. Do not infer graphics from counters.

---

## Historical checkpoint â€” 2026-10-11, Adventure portal/race and midpoint HUD fixed

Read research/20261011_adventure_warp.md first, then the Aku, memory-card and HD
reports. Preserve existing dirty changes; ../repos is read-only. Previous top
and prompt are archived in research/20261011_pre_warp_checkpoint.md and
research/next_session_20261011_pre_warp_archive.md. Older notes are historical.

Warp dust now uses field-aware RGBC/XY writers and explicit packed LE rotation
reads, with bounded arena allocation. Native warp metadata/cup IDs and driving
vectors use typed fields. Battle icon packets/default team bytes are repaired.
Model cache counts are bounded. The independent Model-graph audit found 123,612
numeric field mismatches in 100 omitted standalone files. Structural cooker
detection replaces the growing whitelist. Only 391,600 image bytes change in
those files. Current audit: zero mismatches across 366 mapped entries, 3,661
models, 5,058,863 fields and 152 standalone models. Opaque/compressed bytes and
packed LE texture/GTE fields remain intact. Cooker runs this audit; builds run
the native source audit (255 C files, zero hazards / 37 reviewed word sites).
These checks are not a complete C type checker/all-format proof. Entries 220
and 607 have no discoverable Model graph and remain separate format coverage.

Clipboard_10-11-2026_01 (2).jpg shows a later green-light KeBugCheck. The first
warp-fixed/drive/hdtrace runs FAILED despite clean guest packet counts; host
logs report GPU host pointer 00025C18/1C. Extra 60 FPS renders omitted inherited
depth binding for new boost flames. MainHD now binds turbo/burst/blowup ranges
after queueing, before dispatch. It also temporarily hides screenspace models
from the private queue and restores their flags; cached HUD replay supplies
one rank/fruit copy. Actual-function midpoint regression fixture passes fresh
range/HUD flag, matrix/angle, pose/DB/OT/timer and discontinuity contracts.

Final minimized run: build-360/results/20261011-warp-final-1, 115 seconds
requested / 119.04 wall. Zero guest/packet/asset/link/host-kernel failures.
Adventure profile A -> skip welcome -> Crash Cove -> green light -> accelerate
and steer -> pause/Exit to Map -> N. Sanity Beach. Paired post-AA HD frames
1912/2012/2067/2092 show one rank/fruit model, attached wheels and changed driven
views. Frame 2185 selects Exit to Map; 2371 is the returned hub. This verifies
entry, driving/steering and return, not a whole race win/campaign/later portals,
podiums or save-after-victory. Earlier Aku run let welcome finish naturally.
No new audible speech acceptance. Diagnostic readback/ODS race FPS ~45.6â€“51.9;
hubs ~29. No fresh production 60 FPS/hardware performance claim.

Release: zero XDK errors / 87 warnings. Full absolute-root mirror: 2533 hoists,
zero review notes/designators/host syntax failures. MainHD updates use audited
AST synchronization, never hand edits. XDK platform files compile directly.
XEX: 263378758e8b17b58f39287117b875592e9b0fc3f084d9a32321e42a25ba4f35
PE: 12888a729f92c2b4a23751a76310bb793aa634da43ac9862477506073f548296
Cooked/staged: 2a8ac32de65e37155024dbf55e7f176d73654965ffc911bd2e2dc38c73704984
Install: build-360/xex/dist.
ZIP: build-360/releases/ctr360-hd-saves-adventure-20261011.zip.
Update BOTH default.xex and assets/ctr-u.bin; preserve memcards/settings.

Normal physical input restored, script/capture absent, temporary test card
removed, Xenia stopped. Player saves untouched (helper refuses existing card).
Opt-in pad V2 L/G clocks allow paused-menu navigation; V1 unchanged. Completed
run checker tools/ctr360/check_xenia_run.py includes host KeBugCheck/STOP/link
failures and optional minimum race age. Clean counters do not prove graphics.

Build: bash tools/ctr360/build_xex.sh Release. Headers/generator/broader source
changes require full generation with an absolute source root and passing host
AST. Do not change authoritative inputs during generation. Test short/minimized,
await in tools, archive after exit; no live polling or sleeping-runner edits.
Temporary-card helper: build-360/results/20261011-aku-run.py with
20261011-warp-return-pad.txt. Never rerun old checkpoint/package helpers.
HD ctr360_output_fNNNN_i/f.tga is ordinary 24-bit 1280x720 post-AA output;
legacy display is a side channel; whole VRAM includes packed textures/CLUTs.

Real Xbox: an earlier build returned to Aurora after a black screen. This is a
reported hardware launch failure, not merely deferred controller testing.
Candidate boot/playability/card writes remain unverified. Obtain the console
log to establish the cause; logger tries cache:\ then game:\, hdd1:\, usb0:\.
Next: broader Adventure/race completion, production performance and real Xbox
launch/log investigation. Do not infer hardware compatibility from Xenia.

---

## Historical checkpoint â€” 2026-10-11, Adventure welcome fixed

The user confirmed memory cards work in Xenia, then reported a freeze before
Aku Aku's Adventure introduction. Read research/20261011_adventure_mask.md
first, then the memory-card and HD reports for the retained implementation.

The talking-mask DRAM files were missing the existing single-model byte-order
conversion: native header counts, animation fields and polygon commands/colors
are now cooked for entries 439/441 (Aku) and 443/445 (Uka). All four pass actual
asset-contract/round-trip checks. Only 5,976 bytes in those four files differ
from the old image. A scoped AH_MaskHint_SetAnim native branch loads the camera's
native position numerically into the GTE; its packed LE rotation stays intact.

Final minimized test: build-360/results/20261011-aku-camera-final, 105 seconds
requested / 109.02 wall, zero faults/packet errors. Actual post-AA HD captures
1170/1590 show coherent textured Aku and different mouth/hover poses. The hint
finishes naturally (no skip), returns control at hub age 1227, and Crash drives
toward the warp pads in frames 2250/2370. Driver position/speed corroborate the
visible movement. Steering pulse ended before control returned; no new steering
or audible speech acceptance is claimed. No speech WAV was recorded this task.

Release: zero errors / 87 warnings. Full absolute-root mirror regeneration has
2533 hoists, zero review notes, zero remaining designators and zero host unit
syntax failures. Actual generated mask function inspected. References under
../repos remain read-only; preserve the extensive existing working changes.

XEX SHA-256: 961a03feb2515f786db0a23275161f43d9211de1b2cd1f31ed5c4afd0a73af58
Cooked/staged image: 1b7ad4e615a5da0e1b3e80f2d7ccf5afb6992fa0e4535e81d70d0c516a335d7e
Complete install: build-360/xex/dist.
Complete ZIP: build-360/releases/ctr360-hd-saves-aku-20261011.zip.
Update BOTH default.xex AND assets/ctr-u.bin. Preserve memcards/ and personal
graphics settings. The older hd-saves ZIP has the old image and is historical.

The user's latest stopped run was archived before reproduction under
build-360/results/20261011-aku-user. No player save existed in staged dist;
tests used a temporary copy of archived test profile A and removed only that
copy. Normal physical inputs restored, script/capture settings absent, Xenia
stopped. Packages include no cards or test settings. Player saves untouched.

Build: bash tools/ctr360/build_xex.sh Release. Header/generator/broader source
changes require full regeneration with an absolute source root and passing
host AST. Do not hand-edit the mirror or change authoritative files while the
full generator runs. Test runs stay short, minimized, awaited in tools and
archived after exit; no repeated live polling or edits to sleeping runners.
The Aku helper is build-360/results/20261011-aku-run.py (refuses a live card).
Do not rerun old checkpoint/package helpers: they describe older identities.

HD output is ctr360_output_fNNNN_i/f.tga (ordinary 24-bit 1280x720). Legacy
display TGAs are the side channel; whole VRAM remains packed textures/CLUTs.
Inspect pixels; counters/checksums/zero errors alone do not prove graphics.
Adventure hubs retain 30 Hz rendering; the final diagnostic run measures
29â€“29.91 FPS. Prior Time Trial 60 render / 30 simulation evidence remains.
Real Xbox testing is still deferred while the user's controller is repaired.
Next: user Adventure regression/hardware validation, broader hubs/masks/modes
and remaining graphics coverage. Do not claim complete Adventure campaign or
Uka/alternate placement visual acceptance from these scoped runs.

---

## Historical checkpoint â€” 2026-10-11, persistent saves candidate ready

The user reports full playability. Their Xbox controller broke, deferring real
hardware tests. They explicitly authorize persistent memory cards beside the XEX
on writable USB/HDD. Read research/20261011_memory_cards.md first, then
research/20261011_hd_graphics.md for the retained 720p/16:9/filtering/edge-AA/60
rendered FPS (30 Hz simulation) implementation and prior Time Trial evidence.

Memory-card saves are implemented. The Xbox root is game:\memcards, fixing the
relative path on a platform without CWD. Same-directory temporary writes flush
and replace only after completion; failures preserve the old file. CTR's CRC,
normal save/load menus, four Adventure profiles and ghost files remain in use.
Native profile-header and ghost metadata byte-order faults are repaired. The
garage's malformed line RGBC/XY packet caused the older Adventure diagnostics;
that scoped repair now passes the normal save route with zero packet errors.

Final Release: XDK zero errors/87 warnings, full absolute-root mirror AST passes,
audited RefreshCard/CS_Thread AST syncs pass, real file/CRC/native metadata tests
pass. No manual mirror edits or reference repo writes. Preserve existing changes.
XEX SHA-256 5d26ddfed3396747dc4758fc9e26e4e37aeb471701a71bbc464b9829fc09121d, 4206592 bytes.
Cooked/staged image unchanged: e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0.

Minimized final tests: overwrite 65 seconds requested/68.91 wall and restart
55/58.90, both zero faults/packet errors. The normal menus show SAVE COMPLETED,
restart reads/CRC-checks the same file, shows named Crash profile A, and selecting
it requests the saved N. Sanity Beach hub. The short restart stops during hub
asset loading; do not claim full hub entry/play or actual ghost playback.
UI pixels inspected, not just logs. See the card report's artifact paths/results.

Complete hardware ZIP: build-360/releases/ctr360-hd-saves-20261011.zip (CRC and
XEX/image identities verified). Complete current install: build-360/xex/dist.
Replace default.xex to update an existing install; preserve assets/ and memcards/.
Card files are native ctr360 payloads, not PSX card-image imports. Test A save is
archived and removed from dist; the card was initially absent. Normal controls
restored, capture/script settings absent, Xenia stopped. Packages omit test saves.

Build: bash tools/ctr360/build_xex.sh Release. Header/generator/broader changes
require full absolute-root regeneration and passing host AST. Avoid editing
authoritative inputs while the full generator runs; validate actual generated
functions as well as manifests. References under ../repos remain read-only.
Tests are short, minimized, awaited in tools and archived after completion.
Do not poll live Xenia, edit sleeping runners, or replace live XEX/assets.
run_xenia.sh sets allow_game_relative_writes per launch for portable card writes.
The test helpers 20261011-card-run.py and card-*-pad.txt are in build-360/results.
Do not rerun the old HD checkpoint helper; it packages the previous executable.

Actual HD output is ctr360_output_fNNNN_i/f.tga, ordinary 24-bit 1280x720 TGA;
display TGA is the legacy side channel; whole VRAM remains packed texture/CLUT
data. Graphics acceptance requires inspecting pixels. Optional graphics keys
interpolation/texture_filter/edge_aa default 1, restart to change.

Next: real hardware save/create/overwrite/restart and performance testing after
controller repair; then complete hub/race/ghost and broader mode/effect coverage.
Physical save durability/performance are not yet tested. Earlier wheel/HD/save
reports are historical. Previous current checkpoint/prompt are archived in
research/20261011_pre_memcard_checkpoint.md and next_session_20261011_pre_memcard_archive.md.

---

## Historical checkpoint â€” 2026-10-11, player inputs restored; paused

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

## Historical checkpoint â€” 2026-10-09

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

## Historical checkpoint â€” 2026-09-20

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
- Build tree (what compiles): `build-360/gen` (generated from the repo; see Â§6)
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
  --trace "<cats>" --tag <tag> [--expect-frame <N>]` â€” launches Xenia **minimized**
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
     not staged â€” prime suspect.
   - **Spinning** (3.2 s CPU per 3 s): the pre-short-run `cull9` run got past
     the load (`stage=0..9` all printed) and stopped at f=21 immediately after
     the `[trace] g0` marker at the top of `MainFrame`'s game-logic section.
     The `g1m..g7m` sub-phase probes are menu-gated (`gameMode1 & 0x2000`), so
     cutscene frames have no coverage there â€” widen those gates next.
   `[timing] framePeriod=2342.1ms` in the boot; the platform sub-timings are
   small (`endScene` 0.0-0.1 ms, `vblank wait` 16.4 ms). New instruments:
   `pi done`, `ndbox wait` (first-boot song clock; never entered so far),
   `hb` (every 30 frames: ms/state/stage/mode1/lvl), `mbank` (stage-6
   music-bank state), `framePeriod`. With `--trace all` the OT walk (`walk#N`)
   dominates the log: one bin chain is ~1000 entries, bins 11..18 per frame
   â‰ˆ 8 k entries â€” the OT pool is 0x8000 bytes (8192 entries) for 1P.

**Instruments added this session (category CULL, f>=500 gated):** `xq` (identity
of every offered instance: model id, name words, flags, pb, idpp, anim),
`xz` (why `pb == 0` drops happen, with `idpp[0]`/`idpp[1]` push buffers), and
`xs/xs2/xs3/xs4/xs5` â€” one picked instance end-to-end: raw frame-pos bytes + both
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

**Plan checklist status (IMPLEMENTATION_PLAN Â§12):** (1) trace categories +
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
`[fault]`. **But the framebuffer still shows the copyright page** â€” the user
watched a multi-minute run and nothing repainted. Guest-log state is NOT pixels;
the user's screen is the judge (see `research/visual_gate_plan.md`).

**The visual blocker: degenerate projected bounds cull every title-frame
instance.** `rbe ents=150 ok=0 drop=0,0,0,0,150,...` at the title frames (crate
frames get `ok=19..45`); `bdy maxY=-1024`, `bdz maxZ=0`, `pk y=-1024..-1024`,
`pj sxy=fc000100` â€” the projected y sits on the GTE clamp floor (-1024) or
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
   (the `sm t=` reads flipped to the LE artifact) â€” necessary, not sufficient:
   the projected-y blocker persists.

**Checked and clean (offline; retail and cooked images identical at the bytes):**
the cooked `ModelHeader.scale` (`18 10 3b 0b c9 06`) â€” the LE read gives the
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
   mvp=14190000,00000000,7edb0000,00000000,4bcbffff` â€” full diagonal, live mvp.
2. **`mh->scale.z` was read host-order** while x/y go through
   `RenderBucket_ReadPackedWord` (LE); on the 360 that byte-swapped the z scale
   (`m22 = 0xffffb534` for `0x34b5`), which fed garbage through the projected
   depth/OT path and made the first drawn instance write a stray prim tag into
   the model pack (wedge at f=14: `[trace] c1 f=14 j=3 ... atx=00ed71e0`).
   Fixed with `CTR_ReadU16LE` in `RenderBucket_BuildM3x3` (repo + tree); the
   wedge is gone.
3. **The cooked image byte-swapped `ModelHeader.scale`** and left the
   SpawnType1 struct uncooked â€” both cooker faults fixed (see section 4).

The unit test that found (1) lives in `tools/ctr360/gte_mul_test.c` +
`run_gte_unit_test.sh`: it drives the real scalar GTE and the real matrix
helpers with `BuildM3x3`/`BuildMvp`'s register choreography, compiled once in
the fixed layout and once with `CTR_GTE_BIG_ENDIAN=1` (which on a little-endian
host reproduces the pre-fix 360 symptom exactly â€” x survives, y/z drop to 0).
Both runs assert their own expectations; the pair is the regression guard.

**The f=205 wedge â€” FIXED (session 7; fix list above).** Full chain: the
`gte_st*` store-order bug byte-swapped `gte_stopz`'s MAC0, the OT depth bin went
wild, `RenderBucket_LinkPrimRaw`'s `*otEntry = OTAddress(prim)` wrote OT links
into the model pack and instance pool, and one landed on the Jit `taken` list
head's `next` (`0x00ef0458`). Probe trail: `pi`/`pz` -> `cb1/cb2` -> `d1..d4` ->
`qw` -> `lp` -> `or` -> `mf`.

Frames presented are healthy, no `[fault]`, no `*-guard` trips. Audio: the sink
is a deliberate stub, so "no sound" is expected, not a regression.

### 1.1 The "nothing 3D ever renders" root cause â€” FIXED (session 4)

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

### 1.2 Frame-13 wedge + the crash â€” FIXED (session 4, two cooker passes)

With the guard fixed, instances walked deeper and immediately exposed two uncooked model
data families:

1. **ModelAnim / ModelFrame scalars** â€” `[trace] qd3 f=13 frame=89a92808 next=00000000`
   (a frame pointer outside guest RAM). Cooked by `dram_model_anim_sites`:
   `ModelHeader.ptrAnimations` -> `ModelAnim { u16 numFrames @0x10, s16 frameSize @0x12,
   frames at +0x18 stride frameSize }`; per frame `pos` (3*s16)+pad @0..7 and
   `vertexOffset` (int) @0x18. Entry 514 (ND crate pack): 21 anims / 1743 frames / 3528 sites.
2. **Model command lists + color layouts** â€” the Xenia crash
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

Per `IMPLEMENTATION_PLAN.md` (the independent audit's plan; its Â§12 checklist).
**Done:** Phase 0.1 (trace categories + buffered logging), Phase 0.2
(deterministic VRAM captures), Phase 0.3 (the harness), Phase 1.2/1.3 + the
walker bitfield half of 1.4 (the packet ABI), and the first Phase-2 divergence
(the `ModelFrame.pos` cook + its readers). **Remaining, in order:**

1. **Get one run into a 3D frame and judge the pixels** â€” the acceptance signal
   for the pos fix: `python tools/ctr360/run_harness.py --secs 75 --until-frame
   61 --trace "boot,cull,title,vram,misc,packet" --tag pix --expect-frame 61`,
   then compare `ctr360_crate61_f0061_vram.tga`'s pixelsum with
   `6811c482ead27c0b`. If the run stalls before f=61, chase item 2 first.
2. **The two boot/load stalls** (both upstream of any 3D frame; see Â§1 blocker
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
stay LE. **Check the reader of every field you swap** â€” the scale bug above was a
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
frame-gated (`sdata->frameCounter >= N`) rather than capped â€” see the rule below.

**Probe-insertion rules (each cost real time):**
- NEVER insert between an `if (...)` and its `{` (this caused Â§1.1).
- Never write probes via shell heredocs â€” escapes get mangled; use file-based tool scripts
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
  arena check (`((u32)sdata->ptrMPK >> 24) == 0x82`) â€” an unguarded early read wedged f=1.
- Generator scripts: never put a bare `\n` escape inside a Python string you later run
  `.replace('\n', nl)` on (it becomes a real newline inside the C literal) â€” build the C
  escape with `chr(92) + 'n'`.
- One broken anchor poisons every alphabetically-later file in the C89 pass â€” fix the
  anchor and re-run, don't hand-patch generator output.

---

## 6. Tree vs repo, and reading a run

`build-360/gen` is GENERATED (C89-hoisted, mixed LF/CRLF). Session-4 found the tree holds
probe lines the repo lacks (`q5/q9/q6/q8` in RenderBucket, sparse title probes) â€” probe
batches were applied to one copy. Until a full regen reconciles them, **treat the tree as
the source of truth for what actually runs**, and note any divergence when editing.

Reading a run: the last non-pump guest line names the stall; `[CTR Audio] pump callbacks`
is the liveness signal; `frame N presented` is NOT the game frame; grep `[fault]` first;
a `*-guard` line means the data behind that walk is still wrong (fix the cooker, not the
guard). CPU ~0.2-0.6 s per 3 s wall = parked, not spinning.

---

## 7. Research reports + debug levers

- `research/visual_gate_plan.md` â€” **session-7b, read this first** (log-vs-pixels,
  the cull blocker, the ranked plan, the convention table, the verification
  protocol).
- `research/gte_endianness_findings.md` â€” sessions 6-7 (the `PAIR` half-word bug,
  the scale.z read, the SpawnType1 cook, the f=205 wedge chain, the two
  store-order fixes, the unit test).
- `research/3d_path_findings.md` â€” session-4 evidence (guard bug, the two cooker passes,
  the projection analysis Â§5).
- `research/backend_audit.md` â€” backend audit; the pitch-9552/PM4_DRAW_INDX failures are
  the stock XDK display blit, NOT our draws: do not chase. Ranked backend work unchanged.
- `research/data_coverage_matrix.md` â€” cooker-vs-consumer matrix + no-cook list.
- `research/xdk_inventory.md` â€” XDK + Xenia levers (incl. `--debug`, `DbgPrint`,
  `break_on_instruction` with `default.xdb`).
- `research/boot_to_title.md` â€” the boot/menu-load path detail.
- `research/render_path_map.md` â€” NOT PRODUCED (subagent output limits); do not re-dispatch.

Debug levers ranked: 1) `[fault]` filter; 2) walk guards + `[probe]` trail; 3) Xenia
`--debug` (guest debugger: break on the culled instance, inspect live GTE/matrix state);
4) `DbgPrint`; 5) `KeBugCheckEx` on invariant violations; 6) `break_on_instruction`;
7) `instrument_call_times` / `trace_gpu_stream`.

---

## 8. Landmines (each cost real time)

- Probe anchors must sit INSIDE statements, never on a function signature (C2449).
- The tree's line endings are mixed; multi-line needles need both LF/CRLF variants.
- The XDK C compiler rejects declarations after statements and for-init declarations
  (C2065/C2061/C2059 cascades) â€” that is what the hoist pass fixes; match that style.
- `build_xex.sh` FATAL gates are trustworthy: FATAL = nothing staged. ImageXex is
  incremental; grep the built exe for a probe string to confirm identity.
- Staging identity: `prep_test.sh --cooked` + md5sum against the staged asset.
- The `stderr` console stream wedges on first use â€” it is routed to stdout.
- A guest wedge produces no `xenia.log` error by default; `[fault]` and the probes are the
  instruments.
- **Half-word access to 32-bit data is the standing hazard.** `PAIR`-style unions, `u16`
  struct fields read host-order, and LE reads of BE-written data all bite on the 360. When
  a value looks byte-swapped, find its reader before touching the data (Â§4).
- **Host pointers must never land in guest memory.** Values like `0x00exxxxx` /
  `0x58xxxxxx` in the 0x82xxxxxx mempack window mean a host-side pointer was stored into
  game data â€” that is the f=205 suspect class.
- `RenderBucket_GetNormalOTEntry` = `activeRange + (MAC0 >> 17)` and `gte_stopz` reads OTZ
  (clamped 0..0xFFFF), so the OT write target is `activeRange` itself â€” a stray prim tag in
  the pack means the range pointer, not the depth, went bad.
