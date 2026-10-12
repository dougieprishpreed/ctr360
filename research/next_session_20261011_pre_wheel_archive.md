# Historical continuation prompt; superseded by the wheel/scene checkpoint

# ctr360 continuation checkpoint — 2026-10-11

Project: native Xbox 360 source port of Crash Team Racing using the user's own
PSX dump. Workspace: F:\downloads\temp\python\hermes\ctrport\ctr360.
Reference repos under ..\repos are read-only. Preserve uncommitted work.

Read HANDOFF.md's current checkpoint, research/20261010_flag_loading.md, and
research/20261009_graphics_debug.md. Older checkpoints are historical. Judge
graphics by actual final display pixels, never counters/checksums alone.

The working-demo goal is achieved. Minimized20261011-time-trial-drive-hud
(153.96 seconds) passes normal automated Time Trial menus, Crash Cove loading,
acceleration/steering/recovery, HUD and speedometer, with zero faults/packet
errors. Displays1523/1643/1763/1883 are reviewed. Last2000-frame FPS29.91.
Minimized20261011-demo-racer-hud (403.97 seconds) passes moving coherent Crash
Cove attract racers (5801/6041/6521), title return8000, then Roo Tubes9000/10000.
Zero faults/packet errors; later sustained FPS29.90–29.91. Tiger Temple starts
but has no final capture. Xenia stopped. Physical input restored.

The loading freeze was uncooked standalone racer Model files242..257/308..323/
332..347. Their validated header/frame/animation/command sites now cook.
Current actual-image fixture passes48regions/48models/32214scalars/93458changed
bytes with all other bytes preserved; all564regions check/cook. Native numeric
tag lengths/opcodes and explicit control/texture fields fix allocator, meter,
speedometer and driver-icon packets. Actual HUD fixtures pass. Full regeneration
20261011-hud-packets-mirror-retry.log passes2532hoists/0syntax failures/review
notes/designators; Release0errors/85warnings.

Tested XEX6bc92ce787b06685ef2807652375889390e85f9f93c64f88f208784eb28ac68f.
Cooked/stagede56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0.
The ten-second title and race WAVs are archived. Race PCM is nonzero and playback
advances with0failures; race sound quality has not been manually listened to.
User confirmed title/full flag/menu text/audible title music/good performance.
No complete lap, all modes/controls/tracks or physical360 acceptance yet.

Build: bash tools/ctr360/build_xex.sh Release. Audited changed units sync;
headers/generator/broader source changes require full regeneration with an
absolute source root and host AST success. Never hand-edit the mirror.
Test: CTR360_READBACK=full bash tools/ctr360/run_xenia.sh <seconds> '<pattern>'.
Always minimized; await completion inside a tool call and archive after stop.
Never repeatedly poll live Xenia, edit its sleeping shell, or open a PSX emulator.

User explicitly authorizes ordinary automated pad inputs for fast Time Trial
iteration. python build-360/results/20261011-scripted-run.py <new-tag> 150
build-360/results/20261011-time-trial-drive-pad.txt installs/restores the opt-in
script around a minimized archived test. Physical pads are isolated only while
the script is active; no menu/loader/gameplay flags are bypassed. The idle-demo
script20261011-demo-idle-pad.txt takes400seconds.

Next milestone, when requested: a complete user-controlled Time Trial/race lap,
broader track/mode/input/audio validation, and profiling if problems appear.
Earlier prompt and verbose checkpoint archived in research/next_session_20261011_archive.md
and research/20261011_checkpoint_history.md. Leave the passing build intact.
