# ctr360 continuation checkpoint — 2026-10-11 (paused)

Project: native Xbox 360 source port of Crash Team Racing using the user's own
PSX dump. Workspace: F:\downloads\temp\python\hermes\ctrport\ctr360.
Reference repos under ../repos are read-only. Preserve uncommitted work.

Read the current HANDOFF.md and research/20261011_wheels_scenes.md first, then
research/20261010_flag_loading.md and research/20261009_graphics_debug.md for
prior repairs/contracts. Earlier checkpoints are historical and may overstate
graphics acceptance. Judge actual final display pixels, never counters alone.

The user confirmed all reported fixes, including bursting crate and flyby,
then requested player inputs restored and a pause. The automated test stopped
and the staged ctr360_pad_script.txt is absent. A separate Xenia process
appeared after cleanup (PID 17696, 10:58:15 local) and was left running. No new
test was launched by the agent; normal controls are available on subsequent
launches. Do not launch tests or resume implementation until requested.

Crash Cove Time Trial loads through normal menus and wheels stay attached
while accelerating/turning. Preview texture reads, cutscene scale/matrix/bone
contracts, camera interpolation/vector transfer, particle matrix packing and
split polygon texture fields are repaired. Title/flag/menu text/music and
performance were already user-confirmed. Final minimized 150-second test:
build-360/results/20261011-time-trial-scene-transforms, 154.03 seconds wall,
exit 0, zero faults/packet failures, last 2,000-frame FPS 29.91. Final display
350/370 shows coherent crate burst, 1000 the preview, 1933 attached wheels.
Flyby animation acceptance relies on user live confirmation; selected static
captures 1513/1588 show close track surfaces. Keep that distinction explicit.

Release: zero errors/85 warnings. Full regeneration
20261011-scenes-transforms-mirror.log: 2,532 hoists, zero syntax failures,
manual-review notes or leftover designators. Three actual-function host
fixtures pass, with target behavior validated by Xenia. No source changes
after the final build/run. Assets remain the prior E56 cooked image.

Tested XEX b1c5de4d95fec71350ca8004a7184f9abf65a33c5267067c2b4f9902b3189e74.
PE c15075be610f9006c3cc3edcb55df03cdb5472f96e952423489a62cb51e26471.
Cooked/staged e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0.
Race PCM/playback are captured with zero device failures; detailed sound
quality, full controlled lap, broader tracks/modes/controls and physical 360
hardware have not been separately validated.

Build: bash tools/ctr360/build_xex.sh Release. Broader/header/generator edits
require full mirror regeneration using an absolute source root and host AST
success. Never hand-edit the mirror. XDK files compile directly through MSBuild.
Test: CTR360_READBACK=full bash tools/ctr360/run_xenia.sh <seconds> '<pattern>'.
Always minimized; await completion in tools and archive after stop. Never
repeatedly poll live Xenia, edit the sleeping shell, change live staged assets
or open a PSX reference emulator. Ordinary automated inputs are authorized;
20261011-scripted-run.py installs/restores the opt-in pad file around one run.
Its script loads at initialization; stop the test and remove it before handing
the controller back. No game-state bypasses. Leave the accepted build intact.
