# ctr360 continuation checkpoint — 2026-10-11 (persistent saves)

## Current checkpoint — 2026-10-11, persistent saves candidate ready

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
