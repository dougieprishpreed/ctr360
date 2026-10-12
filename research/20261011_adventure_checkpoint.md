## Current checkpoint — 2026-10-11, Adventure portal/race and midpoint HUD fixed

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
No new audible speech acceptance. Diagnostic readback/ODS race FPS ~45.6–51.9;
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
