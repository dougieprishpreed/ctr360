# Historical pre-wheel review; superseded on 2026-10-11

The earlier visual assessment missed bare karts and scene faults. Read the current HANDOFF and research/20261011_wheels_scenes.md.

# ctr360 — HANDOFF (current state of work)

## Current checkpoint — 2026-10-11

**Crash Cove Time Trial and the attract demo now work in Xenia.** The user
authorized ordinary automated button inputs for faster Time Trial iteration.
Every test ran minimized. No Xenia process or background build remains active.
The opt-in test pad script is removed; normal physical-controller input is
restored. No menu, loader or gameplay flags were bypassed.

`build-360/results/20261011-time-trial-drive-hud/` completed in 153.96 seconds,
with zero faults and zero packet errors. Final display captures 1523/1643 show
Crash leaving the start line and turning along coherent textured Crash Cove.
Coarse scripted steering drives off course; normal recovery returns the kart
at 1763. Triangle then displays the speedometer at 1883. The HUD/timer advance.
This verifies loading and basic acceleration/steering/recovery, not a full lap.
The last measured 2,000-frame window is 29.91 FPS.

`build-360/results/20261011-demo-racer-hud/` completed in 403.97 seconds,
with zero faults and zero packet errors. The crate-skip-only pad script leaves
the title idle through the normal intro/demo route. Final displays 5801/6041/
6521 show moving, coherent racers and textured Crash Cove from different
cameras. Display 8000 returns to the readable title; 9000/10000 show a moving
Roo Tubes demo. Level 4 (Tiger Temple) also starts, but the test ends before
its next display capture; that track is not visually accepted. Sustained
2,000-frame FPS reports during the later run are 29.90–29.91.

Title, full flag animation, readable menu text, and audible title music were
previously confirmed by the user. The bounded race WAVs contain the game's
own mix, not system audio: ten seconds, 44.1 kHz stereo, 441,000 frames. Time
Trial has 881,210 nonzero samples (peak 6,397; RMS 1,034.08); demo has 881,623
(peak 7,268; RMS 1,124.14). Device playback advances with zero failures. Race
sound quality has not been manually listened to. Full races/lap completion,
other tracks, all controls and physical Xbox 360 hardware remain untested.

The final loading freeze was in the first racer render, not the loader.
Standalone racer entries 242–257/308–323/332–347 start directly with a Model,
without the array head expected by the cooker. Their headers and animation/
frame/command payloads were skipped. Crash's header count became 256 instead
of 1, and an animation count became 5,376 instead of 21. Validated model-relative
sites now cook these 48 regions. The actual current-image contract fixture
passes 48 models, 32,214 scalars and 93,458 changed bytes; all other bytes are
preserved. All 564 asset regions pass the cooker check and conversion.

Once the race rendered, powerslide packets exposed another native boundary:
GetPrimitiveMem's PSX bitfields wrote the packet length into the wrong Xenon
byte, and PrimCode produced 0x11 instead of polygon opcode 0x28. Numeric tag
lengths and explicit opcodes repair allocation, powerslide/speedometer packets
and driver icons. Speedometer controls retain LE command bytes, and driver
icon texture halves/blending use their actual contracts. The actual allocation,
reused-memory, meter, driver-icon and speedometer host fixture passes; the
generated functions compile with the PPC XDK through the Release build.

Release builds with zero errors and 85 warnings. Full mirror regeneration
`20261011-hud-packets-mirror-retry.log` passes 2,532 hoists, zero host syntax
failures, zero review notes and zero leftover designators. The first attempt
caught a legacy initializer; it was replaced by its equivalent word before
retry. There are no untested source edits after the passing runtime build.

Current tested identities:

- XEX: `6bc92ce787b06685ef2807652375889390e85f9f93c64f88f208784eb28ac68f`
- PE: `694c33c5733fb8bc09626a53565cf62824a5ed86d409fb925dd0b6203fcca119`
- Cooked and staged image: `e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0`

Read `research/20261010_flag_loading.md` for the scoped October repairs and
`research/20261009_graphics_debug.md` for representation/capture contracts.
The verbose pre-acceptance checkpoint is preserved in
`research/20261011_checkpoint_history.md`; its active-run/identity statements
are historical. September and October 9 checkpoints below are historical too.
Never accept graphics using only counters/checksums or absence of faults.

Build: `bash tools/ctr360/build_xex.sh Release`. It reuses the mirror and syncs
audited standalone units. Header/generator/broader source edits require full
regeneration with an absolute source root and successful host AST parsing.
Never hand-edit the mirror. XDK-only files compile directly through MSBuild.

Test: `CTR360_READBACK=full bash tools/ctr360/run_xenia.sh <seconds> '<pattern>'`.
Keep launches minimized and await completion inside tools; archive after stop.
Do not repeatedly poll a live Xenia process/log, edit its sleeping shell script,
or open a separate PSX emulator. The final displayed rectangle is ordinary
24-bit `ctr360_display_fNNNN.tga`; a main capture may precede feedback, and full
legacy VRAM dumps include packed textures/CLUTs rather than framebuffer pixels.

For automated iteration, run `python build-360/results/20261011-scripted-run.py
<new-tag> 150 build-360/results/20261011-time-trial-drive-pad.txt`. The helper
stages normal PSX input bytes, invokes the existing minimized archive runner,
then restores/removes the script. `20261011-demo-idle-pad.txt` is the idle-demo
route (400 seconds). Physical input is isolated only while a script is present.

Next milestone: user-controlled complete Time Trial/race lap, then broader
track/mode/input/audio validation and performance profiling if issues appear.
The original working-demo objective is achieved; leave the passing build intact.
