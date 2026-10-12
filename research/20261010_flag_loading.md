# Flag/loading continuation — 2026-10-10

## Evidence and repair scope

The October 9 crate milestone is retained. The parent `maxresdefault.jpg`
shows the intended waving gray/white checkered loading flag. The archived
`20261009-clock-display450-aspect.png` instead shows oversized curved regions
without the checker pattern. The October 9 log reaches stage 6 and allocates
bank 32 after bank 0; repeated stage 6 messages alone do not prove deadlock.
That run ends after only nine logged stage-6 calls.

`RaceFlag_DrawSelf` stores its projected coordinates in `u32` scratch banks,
reads those values as numeric packed XY words for clipping, then unpacks them
into native packet halfwords with `CtrGpu_WritePackedXY`. The shared
`CTR_GteStorePositionsXY` helper writes native `s16` pairs. On Xenon a subsequent
`u32` load reverses the halves. The flag now has a local numeric-word store;
the shared helper retains its correct behavior for native halfword consumers.
The existing byte color writers and checker selection are unchanged.

`RenderBucket_StoreInstanceAnimWord` now assigns `animFrame` from the low
half and `vertSplit` from the high half of the retail word. A native whole-word
store had placed the frame in the second field on BE. This automatic path is
skipped in the crate cutscene; its repair is not the cause of the crate fix.

`MainInit_FinalizeInit` copies raw clear-color R/G/B bytes into both draw envs.
Offline retail/cooked inspection confirms Level+0xD8 is not cooked: entry 41
has bytes `63 6c 0a 00` in both images (RGB 99/108/10). A native numeric load
followed by a packed word store over isbg/r0/g0/b0 is incorrect. The crate and
menu clear colors are zero. Existing isbg selection follows the byte copy.

Stage 6 diagnostics now report bank/song/chain substates, bank count, samples,
and sector count for its first 40 calls and every 30 calls thereafter. No loader
state is bypassed. Final display captures are extended through frames 480, 500,
510, 540, 600, 660, 720, 800, 900, and 1000.

## Build and validation

Broader source changes use a full mirror regeneration with the absolute source
root. Windows sandboxing prevented Python's multiprocessing worker pipe, so
the complete generator is run with execution permission. A trial resume was
abandoned because that path does not finalize the mirror manifest. Generated
sources are not manually edited.

Strict host parsing exposed three retail-only memory-card files that were
incorrectly included in the hoist pass despite the native unity source excluding
them. The generator now excludes those exact three files, as it already does
for XDK-specific units. It continues to reject failed AST parses. Worker errors
retain up to 4000 characters to expose the actual diagnostic.

Read-only host preflight: **245 native units, zero failures**. Probe audit:
68 anchors checked, zero problems. Evidence:
`build-360/results/20261010-host-preflight.json`.

A fixture extracted the actual flag/animation helper bodies and compiled them
with the XDK compiler to PowerPC. Its instruction check executes the emitted
stores against BE memory: seven animation boundary values preserve the fields
and adjacent guard bytes; three packed XY values including negative coordinates
round-trip exactly. This is a focused store-contract check, not gameplay
validation. Evidence: `20261010-abi-audit.c`, `.asm`, and `20261010-abi-check.txt`
under `build-360/results`.

Full regeneration completed with 2530 hoist edits, zero manual-review notes,
and zero leftover designators. Release: **zero errors, 81 warnings**. The final
regeneration log is `build-360/results/20261010-flag-mirror-verified.log`.

The first 420-second run is archived in `build-360/results/20261010-flag/`.
Xenia stopped; zero faults and packet reports; the last game heartbeat is frame
81 and audio callbacks continue. CPU over the final three seconds is 0.22 s.
It never reaches the new flag/loader diagnostics, so it does not validate them.
The frame-60 crate display is identical to the October 9 accepted capture.

Added bounded reset-phase diagnostics at frames 70–90 to the audited standalone
MainFrame unit, regenerated it through the normal AST passes, and rebuilt.
The 180-second repeat in `20261010-reset/` reaches frame 345 and continues
advancing (3.27 s CPU over three seconds), with zero faults/packet reports.
Reset completes through every recorded phase; hubSwap and driver step flags
are both zero, including frame 81. The readable frame-120 crate is retained.
These probes do not constitute a repair of the intermittent early wait.

The 480-second run in `20261010-flag-title/` completed and Xenia stopped.
Stage 6 advances after 13 calls: banks 0 and 32 load, song state advances
0/1/2/3, ready becomes 1, and stages 7/8/9 finish. This is evidence that the
October 9 repeated stage-6 messages were an incomplete observation, not a
proven deadlock. The loader was not bypassed or changed to force completion.
Frames 600 and 720 show recognizable Crash, trophy, blue ring, and CTR letters.
The flag/background still shows broad gray regions instead of checks, so the
numeric scratch-word repair alone is not visually sufficient.

At frames 733/734, six packets report malformed lengths or overshoots (the
archive's `packet_failures=16` counts repeated diagnostic matches). Frame 735
reaches a model-header guard (`nh=24576`, model `8270632c`) before its player
model walk finishes; later audio callbacks continue. The title/menu is not yet
accepted as stable. Zero fault lines do not supersede these failures.

The flag matrix has a separate representation fault: `data.matrixTitleFlag`
is a compiled native initializer, while `gte_SetRotMatrix` reads raw LE words.
`RaceFlag_LoadMatrix` now packs the native coefficients directly into GTE
registers. The shared runtime-matrix loader is unchanged. XDK-emitted PPC
instructions execute against BE fixture memory and reproduce all nine expected
coefficients and three translations (`20261010-matrix-box-check.txt`).

The menu box emitters use PSX-order `Tag`, `PrimCode`, and `Texpage` bitfields.
On Xenon they do not produce the required tag high byte and packet command
bytes. `CTR_Box` now writes native numeric lengths, explicit command bytes,
and the control-command LE byte image. Its native control word includes the
existing display-area setting. The retail path retains its command value.
The same PPC fixture verifies lengths 3/5/7/255 and adjacent guard bytes.
The repair is scoped to boxes; other uses of these bitfields still need audit.
The XDK fixture using the original bitfield declarations emits length 7 as
`0x00000007`, clear-box code as `0x51`, and texture-page word as `0x027000E1`.
The code `0x51` matches the malformed composite packets' geometry command.
Evidence: `20261010-legacy-bitfields.c` and `.asm`.

A full regeneration initially rejected a C99 initializer inside the PSX-only
branch because the textual leftover-designator gate sees excluded source too.
The branch now uses the equivalent numeric command value; the gate remains
enabled. The corrected full mirror passes with 2530 hoist edits, zero
manual-review notes, and zero leftover designators. Release has zero errors,
82 warnings (the additional warning is the now-unused retail `primCode` local
in `CTR_Box_DrawWirePrims`). Build log:
`20261010-flag-matrix-mirror-verified.log`. Visual verification: pending.

The first corrected-build run (`20261010-checker-menu/`, 540 seconds) waits
at game frame 27 after its heartbeat, with 0.19 s CPU over the final three
seconds. Audio callbacks continue, zero fault/packet lines are recorded, and
Xenia stops. Only frame 13 is captured; this run does not validate the flag
or box repairs. Its XEX hash is
`4289c3bf2ee70f08738242c5c2ac4ded409c516d0369f3e6a2e5298ddffb9d75`.

The repeat uses the same binary with a temporary `none` runtime trace mask;
the wrapper restores `boot,cull,title,vram,misc` afterward. It runs the same
minimized full-readback runner and archives final display rectangles. The
quiet run is a visual verification experiment, not proof that the intermittent
wait has been repaired. It completed with Xenia stopped and no display capture;
it does not validate the flag or boxes. The trace mask was restored and verified.
Some legacy `[probe] *-guard`
tags currently classify as miscellaneous despite the trace module's comment
claiming guards are essential; quiet counts alone cannot accept runtime health.

Expanded reset markers through frame 120 and frames 730–750. The 90-second
`20261010-reset-early/` run completed with zero fault/packet lines and Xenia
stopped, but waits after frame 11's stage-8 return. All recorded reset phases
finish, hubSwap/driver step flags are zero, and level2 is null. No visual capture
was reached. The last recorded renderer/kernel calls precede the wait; they
must not be interpreted as evidence that rendering or VBlank continues during
it. Only the audio worker demonstrably continues logging. Bounded gamepad
processing phase markers are added next, with full mirror regeneration.

## Connected-pad loop, confirmed flag/title, missing menu text

The user's controller was connected while playing another game. Its inputs
could skip the opening scenes and select menus during our minimized runs.
Normal skipping remains enabled. The `20261010-pad-checker/` run stops inside
`GAMEPAD_ProcessHold`: `pad-enter f=5 connected=1` has no following held marker.
The button map is authored as four raw LE bytes, but the old loop assigned the
array address to `buttonMapRawInput` and never recognized the zero terminator.
`CTR_ReadU32LE(buttonMap->rawInput)` fixes both matching and termination. This
matches the read-only native reference. The actual function passes a host
fixture covering all 65,536 digital and analog button combinations, idle
saturation and disconnected input (`20261010-pad-contract.txt`). This verifies
the mapping contract, not racing or every physical input path.

Full mirror: 2530 hoist edits, zero review notes/designators/parse failures.
Release: zero errors, 81 warnings. The 240-second `20261010-input-fixed/` run
completed, Xenia stopped, and zero fault/packet failure lines were archived.
XEX SHA256: `5d91ec3b14b9d96e6cbb0e7296d4f5a6ce125e4c18438c7d55b540a53db46110`.
Final display 480 shows correctly shaded gray/white checks; 900 and 1000 show
the Crash/trophy/CTR title against the flag with an empty menu panel. The user
also observed full flag animation and good performance, with invisible menu
labels. Those actual pixels now accept the matrix/scratch/box repairs. Later
input or the idle demo advances to level 30; racing is not accepted.

The font failure is asset scalar byte order. Retail and the old cooked MPK
entry 260 both contain group ID bytes `04 00`, glyph count `39 00`; native BE
reads these as 1024/14592. `DecalGlobal_Store` rejects 1024, so font group 4 is
null and glyph drawing is skipped. Icon global IDs also remained LE. The
menu level's lookup count was raw LE 64, read as 0x40000000. The cooker now
normalizes lookup counts, Icon.global_IconArray_Index, and IconGroup.groupID /
numIcons in recognized MPKs/levels, without changing names, mapped pointers or
TextureLayout's existing byte/LE contract. Existing MPK count sites are deduped
explicitly. The whole-disc check and recook each validate 496 regions with
round-trip and overlap gates. The new staged assets read groups 4/5 and counts
57 correctly (`20261010-font-audit.py`). Final display captures 900/1000 in
`build-360/results/20261010-font-audio/` show all six menu labels correctly;
the user also confirmed the menu text is working.

Font palettes are compiled native numeric u32 arrays; the byte-image
ColorCode_Load helper reverses their RGB on BE. DecalFont now constructs Colors
from the numeric palette value. Other packed-color callers are unchanged.

## Audio output and performance validation

The old Xbox device backend discarded PCM and requested 512 frames every 3ms,
over three times the 44.1kHz rate. It also grew its pretend queued-byte counter.
The new XAudio2 source voice queues at most three persistent 512-frame buffers
and drives mixer pulls from device consumption. Source PCM is 44.1kHz native
S16 stereo; the mastering voice is 48kHz. Native BE input matches the XDK ATG
WaveFile::ReadSample PCM contract. The worker waits for Resume before mixing,
and shutdown joins it before freeing state. XDK C API compilation passes
(`20261010-audio-api.txt`). The actual backend also passes a deterministic
queue fixture covering persistent PCM lifetime, rate, queue bounds, repeated
flush with a retained current buffer, failed submission/recovery, and shutdown
(`20261010-audio-queue.txt`). The user confirmed audible playback.

An opt-in `cache:\\ctr360_audio_capture.txt` containing `1` captures ten seconds
of this game's title mix to ordinary LE WAV. It never records system audio.
The run wrapper restores the previous audio/trace settings after completion.
Quiet tracing now retains sparse heartbeats and guard/invalid/overshoot probes
so performance experiments cannot hide known integrity failures. The verified
full mirror has 2530 hoist edits, zero manual-review notes, zero leftover
designators, and zero host syntax failures. Release has zero errors and 81
warnings. XAudio2 also needs `xmcore.lib` (`xmcored.lib` for Debug) for its
lock-free queue imports.

## Confirmed menu/audio; idle intro transition still stalls

Current accepted XEX SHA256:
`22fd67f72d6f5e5a7124b06dff03af56d52c786c18698c6a7a8cd398cff324d9`.
Cooked and staged image SHA256:
`3ac39c576d356bd56f5418b30e254a3775a9969e8a2194acf1b4370a67b5e238`.
The 180-second `20261010-font-audio/` run completed with Xenia stopped and
zero reported fault/packet failures. Actual displayed pixels show the coherent
title, animated flag, and readable gold/orange menu labels. Its title WAV is
441,000 stereo frames at 44,100 Hz (ten seconds), with nonzero PCM. Device
consumption requests about 431 512-frame callbacks per five seconds and the
queue stays at two/three buffers. These measurements support the rate/queue
contract; user listening confirms sound, and user observation confirms good
title performance. Racing is not accepted.

The user then saw a frozen loading screen before pressing A. With idle input,
the first title DEMO route sets `boolSeenOxideIntro` and loads level 30,
`INTRO_RACE_TODAY`, before the later actual attract race. The observed mode is
`60400000` (LOADING | GAME_CUTSCENE | ARCADE_MODE). Do not attribute this freeze
to the still-raw track mesh without locating the stop.

`20261010-attract-load/` (120 seconds) and
`20261010-attract-load-complete/` (200 seconds) both completed with Xenia stopped.
The longer trace reaches `mbank it=20 state=5 ready=1 lvl=30`, proving that this
music-bank/song load finishes. The durable guest log ends partway through that
line because the backend batches writes; this alone cannot locate the next
stalled statement. Xenia's audio-worker log continues but `played=2739140` and
`buffers=3` stop changing. This does not prove continued audible output.
The 200-second `20261010-attract-ods/` run then completed with Xenia stopped,
zero reported fault/packet failures, and the same build/assets. Its direct
Xenia log proves stage 6 returns 7 (`load=1`) at line 60146, then four pending
stage-7 returns at lines 60162, 60190, 60206 and 60222. The stage-7 body is
gated by `load_inProgress`; it has not been reached. After the last pending
return the remaining DrawOTag/present markers finish, then main-thread markers
stop. Audio worker reports remain but its consumption count is static.

The next useful diagnostic is bounded entry/exit markers around
`LOAD_NextQueuedFile` (called at the top of CTR_Main), including queue state,
current type/index/destination/size, and the read/DRAM callback and pointer-map
steps for level 30. Audit the actual intro file representation before changing
the cooker, queue, audio, or mesh. No loading workaround or bypass was added.
The user's break request pauses work here. All tests completed, Xenia process
count is zero, and temporary settings were restored to `boot,cull,title,vram,misc`
with the previous audio-capture setting.

Track mesh payloads remain raw LE. Actual race loading, controls during racing,
race rendering, and race audio remain unverified.

## Resumed toward the demo race — external levels and mesh representation

The user resumed work and requested a working demo race, with every Xenia run minimized. `20261010-external-map-runtime/` completed its 200-second run with Xenia stopped. Its stage-7 body now runs and stages 7/8/9 finish; FinalizeInit reaches the first camera initialization. Audio consumption stops at that boundary. Zero fault/packet markers is not race acceptance.

The first idle route loads intro level 30. BIGFILE LEV 516 has a negative relocation marker and uses following PTR 517. The cooker had skipped these external-map levels, leaving both the PTR byte count and all LEV scalars raw LE. The new structural external-map path validates ascending aligned in-bounds offsets and applies the same level conversions to LEV/PTR pairs. It finds 34 external pairs; check/cook validate 564 regions. The renderer's interpolated animation flag stores `(logicalFrames >> 1) + 1` physical frames; the cooker now uses that count, avoiding the old overlap into unrelated texture data in intro level 540.

The camera search traverses BSP data whose native fields were still raw LE. The new mesh converter covers native mesh counts, quad indices/flags/draw-order bitfield/bounds/normals, native vertex positions/flags, and BSP branch/leaf/hitbox fields, with bounds/reference checks. Vertex colors, four draw_order_high bytes, textures, and PVS/RLE remain their byte contracts. Four 226 GTE loads now pack native vertex coordinate fields explicitly; the native pointer-byte reconstruction reads host-relocated words; scenery animation stores native x/y fields. PVS readers explicitly decode LE words, including RLE output, instead of cooking compressed streams.

Level startup cooking also covers driver spawn positions/rotations, water/scenery counts, scenery numeric animation offsets, configuration flags, rain/stars/split values, checkpoints and SpawnType2 coordinates. AI navigation uses native NavHeader/NavFrame numbers: there are three paths and numPoints is the last frame index, so each path contains numPoints + 1 frames. The `last` pointer is initialized by BOTS_InitNavPath and is not treated as a relative pointer. The cooker now rejects non-level arrays that merely resemble the leading level fields (entry 220).

`20261010-mesh-contract.log` checks actual retail entries 1/13/216/514/516/519: native vertex coordinates/flags, quad indices/bitfields, BSP bounds and driver spawn values equal their retail numeric values; vertex RGB, clear RGB, draw-order bytes and terrain bytes are unchanged. All six pass. `check_probes.py` passes 68 entries. Full mirror regeneration and final asset conversion are underway; runtime race output remains unverified.

The 300-second `20261010-native-mesh-runtime/` run and 120-second `20261010-intro-steps/` run complete with Xenia stopped and zero fault/packet markers. They pass loading/FinalizeInit and produce an intro sky capture at display 1500. No track/race is accepted. A bounded GameLogic trace shows first intro update frame 1427 entering camera bucket 15; the initial diagnostic only accepted level 30, however, and the script sets the level ID to the next preloaded scene (36) in that update. Missing post-camera markers alone therefore do not establish a camera deadlock. New markers cover all nine intro IDs and include queue/ready/load state; bounded CS opcode logging is in the next build. Normal script/loader conditions remain intact.

An independent race startup defect is fixed in VehBirth_SetConsts: MetaPhys.value is compiled native s32, so loading its first byte/halfword selected high bits on BE. Native paths now load the numeric word and truncate to the destination width. The actual extracted function passes all 260 retail engine-class values on the host. Actual XDK PowerPC assembly shows lwzx followed by stbx/sthx for the byte/halfword cases. Windows clang lacks a PowerPC target, so the XDK compiler was used for that validation. Full mirror verification again passes 2530 hoists, zero notes/designators/syntax failures; Release has zero errors and 81 warnings.

## Late intro stall diagnostics

The 120-second `20261010-intro-late/` and 100-second `20261010-intro-late-ods/` and `20261010-intro-present/` runs all completed minimized with Xenia stopped. The all-intro-ID GameLogic trace continues through frame 1713 with queue=0, ready=1, load=0. XA 1/77 starts at frame 1696 and that camera bucket returns, so the playback-start call is not the immediate stall. Its actual source has 41 mono 37800-Hz sectors, about 4.373 seconds. Final display 1500 still shows only intro sky; no race or correct intro mesh is accepted.

The durable Xenia log confirms presentation/storage/swap markers finish at frame 1712. Frame 1713 completes frame reset and reaches the pad-exit GameLogic marker, then no EndScene marker. GPU-thread texture messages are asynchronous and cannot alone locate the game-thread stop. New scoped GameLogic exit, RenderFrame phases, VBlank callback phases and CSEQ note markers cover 1708–1722. Camera opcode markers now track only the camera thread across all intro IDs and log script changes, avoiding the old first-frame static-instance flood. The full mirror `20261010-late-render-mirror.log` passes 2530 hoists, zero review notes/designators/syntax failures; Release passes zero errors/81 warnings. The next run is `20261010-intro-render-vsync/`.

`20261010-cseq-notes.py/.log` parses the actual original and staged cooked HWL: 33 groups, 91 songs, 606 streams and 168304 events. Every note opcode is valid and every note stream is unchanged; native sequence offsets and song offsets numerically match retail. This verifies the on-disc cooking contract, not runtime sequence state or race audio.

### Static intro ModelFrame conversion

The completed minimized `20261010-intro-model161` test narrows the deterministic
frame 1713 freeze to the first `b8010001` vertex command of `intropura`
(runtime model ID 161). Frame preparation, color setup, and instance setup return;
first uncompress entry does not. Its original frame is at entry 516 content
offset 0x4a8fc, matching the runtime command-to-frame distance. Original LE
vertexOffset 0x1c reads as native 0x1c000000 in the previous cooked asset, and
position (-127,0,-110) reads as (-32257,0,-27905).

`dram_model_anim_sites` previously skipped headers with no animation array. It
now cooks loader-mapped static ModelFrame position/pad halfwords and its numeric
vertexOffset. The 16-byte opaque block and packed vertex payload remain bytes.
Valid static offsets include 0x22 (`startbanner`), so validation uses the actual
file bounds rather than assuming every offset is 0x1c. All 564 regions validate
and recook. `20261010-all-frame-contract.py/.log` verifies 41,734 actual frames
in 212 regions against original coordinates/offsets and preserved opaque data
and first vertex bytes. `20261010-static-frame-runtime` is a five-minute
minimized full-readback run awaiting completion; no race acceptance yet.

### Direct model colors beyond the scratch cache

`20261010-static-frame-runtime` completes minimized (303.88 seconds, Xenia
stopped). Display 1800 now contains intro models; no race is accepted. The
frame 1713 first vertex and draw dispatch finish. GameLogic markers reach 1829,
where the script has switched/preloaded later scenes. Malformed GPU packet
reports occur nearby, followed by stopped PCM consumption and no capture 2400.

The intro ship in entries 534/540 declares 26 cached colors but its commands
also directly read ptrColors indices through 63. The cooker incorrectly treated
the leading command-list word as the entire palette size. Original index 46 is
0x0043333d; the uncooked word reads 0x3d334300. The normal GT3 writer ORs its
triangle opcode into that value, giving the observed code 0x3d with length 9,
which the parser consumes as a length 12 GT4. Other uncooked colors make later
packet payloads look like arbitrary commands.

The cook now includes cached words and every direct color reference, matching
GetCommandColor and the two-color command's cache-selector bits. All 564 regions
validate and cook. `20261010-all-command-color-contract.py/.log` compares 636602
model command/color words across 212 actual regions with retail numeric values.
`20261010-command-colors-runtime` is the next five-minute minimized run in
progress. No opcode masking or loader/script bypass was added.

`20261010-command-colors-runtime` completes minimized (303.88 seconds, Xenia
stopped, zero packet/fault reports). Displays2400/3000/4000 show later intro
models; display5000 is the title again. The first real demo requests Crash Cove
(level3); the durable Xenia log reaches frame5550 with stage6, after which main
progress and PCM consumption stop. Run metadata uses the buffered guest log,
so its older final heartbeat4620 is not the actual stopping boundary. The next
300-second `20261010-demo-load-trace` run enables existing boot/geometry markers
to locate that stop. No race is accepted.

### Crash Cove model/instance scalars and viewport clipping — 2026-10-11

`20261011-demo-bank-steps` completes minimized (303.90 seconds, Xenia stopped,
zero packet/fault reports). Its durable Xenia log proves bank transfers and
song-header parsing finish: frame 5557 exits music state 5 and loader stage 7.
Crash Cove VRAM entry 24 and level entry 25 then load. The last loader marker is
stage 7 entry at frame 5561. The old sparse stage-6 tail was incomplete.

An actual asset fixture finds all nine embedded model IDs/header counts in
entry 25 uncooked. The level model cooker rejected valid one-letter names
`r`, `t`, and `c`, returning no scalar sites for the entire level. Model IDs
166/149/etc. become negative or oversized native indices in
LibraryOfModels_Store. Instance validation had the same rejection when its
model target used a one-letter name, leaving all 26 instance records raw too.
The level/instance validators now accept nonempty printable names while keeping
their existing mapped-pointer, alignment, header-count and file-bound checks.
All 564 regions validate and cook. `20261011-all-level-model-contract.py/.log`
checks 69,633 actual model/header/instance scalars: 915 models, 3,969 instances,
139 levels. Names remain unchanged. Existing 41,734-frame and 636,602-command/
color fixtures still pass. Cooked/staged SHA256 is
`8aa43c567a229a46e8191a9f1a2c121a3f5567def0cc8f3945d631692dbe28d2`.

Terrain markers find visible BSP leaves but zero polygon bytes throughout the
intro. Overlay 226 read runtime native RECT w/h as LE bytes. Native dimensions
(512,216) produced clip window 0xd8000002 instead of 0x00d80200, rejecting an
ordinary on-screen quad. Both entry and terminal clipping paths now pack native
w/h explicitly. Projected-center scratch also reads the native s16 values
written by PushBuffer_UpdateFrustum. A numeric fixture accepts the on-screen
quad and continues rejecting quads beyond the right/bottom edges. New bounded
bucket-result and stage-7 markers support runtime verification. Full mirror
generation for these source changes passed. `20261011-track-models-runtime`
completed minimized (303.93 seconds, Xenia stopped, zero fault reports,
266 packet-error report lines). Race stages7/8/9 and driver/instance/camera
initialization finish. Terrain emits polygons, but display5000 is black apart
from DEMO text. Main progress stops near5095; no race is accepted.

### Camera, vehicle matrix, and ground-effect formats — 2026-10-11

The first malformed packet is skidmark POLY_GT4 color `3e1f1f1f` stored as a
native word across byte fields. The parser reads command byte1f. Its view
rotation was also read as native words from the LE view-projection matrix.
Skidmarks now write typed color/coordinate/UV fields, explicitly decode texture
words and retain native OT tags. Shadows use the same color/texture contract,
decode their LE camera/axis rotations, and take camera coordinates from the low
half of native full words instead of the first BE halfword at each address.

CAM chase/follow offset results previously used CTR_GteStoreMAC, which writes
LE matrix payloads, then read those bytes as native Vec3 integers. World
translation inputs had the inverse mistake. Camera vectors now use native
MAC stores and native world-position transfers. Local fly-in rotation remains
LE while its world translation is explicitly native. VehGteSetRotTransMatrix
uses the same instance contract; a separate view-projection helper retains
the all-LE PushBuffer matrix contract.

VehPhysForce_RotAxisAngle wrote native halfwords, while generic matrix/GTE
consumers expect LE rotations. It now encodes its nine final rotation values
as LE, leaving translation untouched. The trig word is rebuilt from native
sin/cos fields. Connected physics/raw-word readers, BOTS normals, tire emitter,
turbo/weapon directions, wake rotations and shadow/camera readers follow that
contract. Vehicle center-offset MACs and upright normal vectors remain native.
Vector_BakeMatrixTable encodes authored scale diagonals before multiplying and
decodes baked matrix normals before forming native offsets. Overlay226's
full-dynamic midpoint reconstructs depth/clip fields and explicitly packs its
native position pair.

`20261011-race-boundary-fixture.py/.log` extracts actual repaired functions.
Host assertions cover four quarter-turn matrices, unchanged native translation,
camera MAC values and skidmark color/code/XY/UV/tpage/OT semantics. PPC XDK
compilation also passes, with assembly retained. Full regeneration is running
in `20261011-race-camera-mirror.log`; next is Release and a completed minimized
run with bounded race-relative captures and world/logic/render markers.

`20261011-race-camera-runtime` completed minimized (403.94 seconds, stopped):
levels3/6/4 and frame10620 advance, but displays5031/5631/6111 show no coherent
track or racers. A later level4 weather E1 command was stored as a native word;
RenderWeather now uses CtrGpu_WriteControlWord. Full regeneration passes2532
hoists, zero syntax failures/review notes/designators, and Release passes with
zero errors/85 warnings.

### Attract cameras and terrain texture words — 2026-10-11

SpawnType1 entry2 contains EOR/attract camera records read as native halfwords
by CAM_ThTick. They were uncooked: count11/mode4 became2816/1024, indexing past
the mode-size table. The cooker validates all record modes/counts/file bounds
and converts the record halfwords. Entry3 segmented paths remain raw LE.
Four files alias the final zero mode with the next path header; those shared
zeros stay unchanged. The actual asset fixture passes7820 scalars/1112records
in72tables. All564regions check/cook. New cooked/staged SHA256:
`c45a692d8d1a16576b48e4d4d7321b903957633b41e7db86d545c18e2daa7832`.

`20261011-demo-eor-asset-runtime` isolates those assets with the preceding XEX.
It completes minimized (303.93seconds, stopped, zero faults/packet errors).
Displays5627/6107 now contain identifiable moving racers, including Crash,
but terrain is blue/missing. This is progress, not demo acceptance.
`20261011-demo-terrain-trace` repeats with the weather repair XEX
`3689ac7cecadfb6ebff3447f3ccacddc270249cd9bd970e748d9d04cf8a978d6`:
303.95seconds minimized, stopped, zero faults/packet errors; display6098 has
Crash and blue terrain. Camera/world/GPU tags were filtered as MISC, so those
absent messages are not evidence about their execution.

Overlay226 still reads raw TextureLayout clut/tpage halfwords as native fields.
Its UV scratch union also names address-order halves low/high; on Xenon those
are reversed relative to the numeric packed word. Native numeric low/high
helpers now replace9writes/14reads, and raw layout halfwords are decoded.
Mosaic texture+0x24 is either raw inline layout bytes or a ptrmap-rebased native
pointer; the reader validates a native level texture pointer before choosing
that format, otherwise retaining the raw word. The actual entry25 audit finds
120layouts,83mapped mosaic pointers and37inline mosaics. Entries43/49 confirm
the same mixed format. `20261011-terrain-uv-fixture.py/.log` tests the actual
functions for normal/mirrored UVs, clip pages, numeric halves, and mixed words,
and compiles them with the PPC XDK. Original memory-pack boundary checks pass
host edge tests; a proposed change based on misreading their span was rejected
by the fixture and reverted before any build/test.

Full regeneration for the supported terrain repairs passes2532hoists,0syntax
failures/review notes/designators in `20261011-terrain-uv-mirror.log`; two
interrupted attempts are preserved. Audited MainFrame/nativeGPU units sync/
verify the bounded diagnostic prefix correction (hb). Release0errors/85warnings.
`20261011-demo-terrain-uv-runtime` completed minimized403.89seconds, stopped,
0faults/packet errors. Display1800 shows textured road/scenery and3000Oxide.
It stops at gameframe3550 during cutscene level33 preload after opcode39(wait
level time140). Audio device consumption freezes at5871298samples, callbacks
11470,3queued; no race capture. NativePerf is gated by CTR_INTERNAL and this
Release produces no CSV; no new performance measurement is available. MainFrame
adds scoped game-step markers for3000..4200 through the audited sync. Release
passes0errors/85warnings. `20261011-intro3550-trace` completes minimized243.89
seconds, stopped,0faults/packet errors. At3548 after the level32->33 request,
all buckets/BOTS/audio/game-exit return (queue3/ready1/load1). The stop follows
game logic, entering rendering. Full regeneration is active for render-frame
and instance fences3500..3600 in `20261011-intro-render-mirror.log`. Xenia is
stopped. Next build/run240seconds; no loader/script flags were bypassed.

`20261011-intro-render-mirror.log` passes2532hoists,0syntax failures/review
notes/designators; Release passes0errors/85warnings. XEX6594e050250c6e6b1d87270f6fcfcfaccdc2e1621a4cb9da1664497021985b34
was tested in `20261011-intro-render-trace`, completed minimized243.92seconds,
stopped,0faults/packet errors. At3550 all queued models finish drawing and
instances-exit returns; level-exit/VSync never appear. New bounded fences cover
each remaining ground effect, terrain setup, DrawLevel/DrawSky and each terrain
bucket. Full regeneration passes2532hoists,0syntax failures/review notes/
designators in `20261011-intro-ground-mirror.log`; Release passes0errors/
85warnings. `20261011-intro-ground-trace` is running minimized240seconds.
That run completes minimized243.95seconds, stopped,0faults/packet errors.
Its buffered guest-log tail misses final markers. The durable Xenia log shows
ground effects and terrain setup returning, then dynamic rendered bucket2
entering at3546 and not returning. The shared deepest mosaic UV reload's source
index0x320 and bias0x3d8 are previous/deepest frame+0xb4 words. SetGridFaceSlotWord
writes LE images, but all three reload paths read native u32 values. On PPC,
slot12 becomes201326592 and slot24 becomes402653184, sending mapped mosaic
reads outside their tables. A shared helper decodes both words as LE, retaining
the mirror-span arithmetic. `20261011-mosaic-offset-fixture.py/.log` passes294
actual function cases and PPC compilation (no PPC execution in the fixture).
Full regeneration passes2532hoists,0syntax failures/review notes/designators in
`20261011-mosaic-offset-mirror.log`; Release passes0errors/85warnings.
`20261011-demo-mosaic-runtime` is running minimized400seconds; await its
completion/stopping before replacing staged XEX/assets. It must test the normal
demo route visually. No race is accepted.

### Manual Time Trial first frame � 2026-10-11

Latest update: `20261011-demo-mosaic-runtime` completed minimized400.85seconds; the user diverted it to Time Trial. The mosaic repair clears the old3546..3550 intro stop (display4000 shows Crash hut). Crash Cove reaches stage9/finalize5862, then stops. Corrected packet-error accounting includes13 invalid OT links from menu packets; the old count0 was incomplete.

`20261011-time-trial-start-trace` completed minimized400.90seconds, Xenia stopped (the user closed it after another freeze). Its first race frame721 completes GameLogic and then hangs inside RenderFrame before setup-exit. Loader/finalize720 complete;9 menu invalid OT links remain. XEX bf75238c3d5e90557fd2b7f6852b4004a76ec243c1e22eef6c03048cbaea9b33. No race accepted. The user authorizes automated button inputs and prefers Time Trial iteration instead of waiting for the idle demo.

Authoritative RenderFrame fences now cover Time Trial as well as demo, including visibility/texture/menu setup. An opt-in Xbox pad script supplies ordinary PSX bytes from staged assets/ctr360_pad_script.txt; absent file preserves physical input. It changes no menu/loader/gameplay flags. Actual parser/pad fixture passes. Full regeneration is running in20261011-time-trial-render-mirror.log; do not edit source while active. Next Release/minimized150-second scripted Time Trial test through20261011-scripted-run.py. Script settings restore after the run.

Full regeneration passes2532 hoists,0 host syntax failures/review notes/designators in20261011-time-trial-render-mirror.log; Release passes0errors/85warnings. Current XEX 14dff3467bfedbf52e73d9f4500f90e6e7be35f9fc99eb23be61d8bd92311415. The minimized150-second20261011-time-trial-render-trace automated test is active through20261011-scripted-run.py; await completion/stopping before replacing staged artifacts.

Newest evidence: automated20261011-time-trial-render-trace completed minimized153.94seconds, Xenia stopped,0fault/packet reports. The normal menu sequence selects Time Trial/Crash Cove. Finalize1161 and GameLogic1162 return; render visibility, texture cycling, menu, rain, setup and effects return. The next call is RenderBucket_QueueAllInstances. The audited RenderBucket unit now logs first-race-frame queue items and substeps. Release passes0errors/85warnings. Minimized150-second20261011-time-trial-queue-trace is active; await completion/stopping before replacing staged XEX/assets.

Latest repair: standalone HI/MED/LOW racer entries242..257/308..323/332..347 start with Model at content0, not a model array. All prior detectors skipped them. Automated20261011-time-trial-player-frame-trace completed153.94seconds, stopped,0fault/packet reports; Crash has256headers and anim2688, projecting frame89af4c00. Raw count21 reads5376 on PPC. The cooker now validates the standalone Model/header span and applies the existing animation/frame/command/color conversions via an explicit model offset0. Actual48-region fixture passes32214 scalars/93458 changed bytes and preservation of all other bytes; --check passes564regions. Recooking is active in20261011-racer-payload-cook.log. Wait for cook completion, stage assets, then minimized automated Time Trial test. No race accepted yet.

Racer recook/staging completed564regions, assetSHA256 e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0. The next minimized150-second automated test is20261011-time-trial-racer-assets.


### Racer payload freeze cleared; native HUD packets - 2026-10-11

The completed minimized 20261011-time-trial-racer-assets run (153.95 seconds, stopped) shows Crash and coherent textured Crash Cove with advancing HUD timer at displays1522/2362/4000. It uses XEX a5588603f6adcdba4d28c3deac07b1e760f901c3c3fe9c273fb89efa7026d713 and cooked/staged e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0. No driving/demo acceptance yet. 2783 packet errors begin at1326, prim+0x3c: ffee8424 00ff0011 01ea00c7 01ea00c7 (len255/code17), matching UI_DrawSlideMeter. GetPrimitiveMem Tag.bits.size writes the wrong Xenon byte; PrimCode produces0x11 rather than0x28. Candidate numeric tag/opcode stores repair allocator, meter, connected speedometer and driver-icon fields. Actual allocation/reuse/meter/icon contract fixture passes. Full regeneration20261011-hud-packets-mirror.log is running. Next Release and ordinary accelerated/steered Time Trial input with a bounded race WAV. The user explicitly authorizes automated buttons; every test stays minimized.


20261011-time-trial-drive-hud completes minimized153.96seconds, stopped,0faults/0packet errors. Displays1523/1643/1763 show Crash driving from the start and turning along coherent textured Crash Cove; display1883 shows the speedometer after Triangle. Coarse steering drives off course and normal recovery returns the kart; no full lap tested. Last2000-frame FPS29.91. Race WAV441000stereo44.1kHz frames,881210nonzero samples, peak6397/RMS1034.08; device0failures, sound quality not manually listened to. XEX6bc92ce787b06685ef2807652375889390e85f9f93c64f88f208784eb28ac68f. AssetsE56 unchanged. Full regeneration retry passes2532hoists/0syntax failures/review notes/designators; Release0errors/85warnings. 20261011-demo-racer-hud is running minimized400seconds with a crate-skip-only script to isolate physical pad input and verify the original idle demo goal.


### Working demo accepted - 2026-10-11

20261011-demo-racer-hud completes minimized403.97seconds, stopped,0faults/0packet errors. Displays5801/6041/6521 show coherent moving Crash Cove racers,8000returns to the readable title,9000/10000show moving Roo Tubes with textured scenery. Tiger Temple(level4) starts but lacks a final capture; no visual acceptance for it. Sustained later2000-frame FPS29.90-29.91. Demo race WAV441000stereo44.1kHz frames,881623nonzero samples, peak7268/RMS1124.14; playback0failures. Race sound quality not manually listened to. Same XEX6bc92ce787b06685ef2807652375889390e85f9f93c64f88f208784eb28ac68f and cooked/stagedE56 as the passing Time Trial test. Normal controller input restored after script removal. Current-image racer fixture now verifies the installed E56 cook against original validated sites and computed pointer-only baseline, passing48regions/48models/32214scalars/93458changed bytes. The original moving coherent demo goal is achieved. Next milestone is a complete controlled lap and broader validation, when requested.
