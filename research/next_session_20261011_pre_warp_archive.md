# ctr360 continuation checkpoint — 2026-10-11 (Adventure welcome)

## Current checkpoint — 2026-10-11, Adventure welcome fixed

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
29–29.91 FPS. Prior Time Trial 60 render / 30 simulation evidence remains.
Real Xbox testing is still deferred while the user's controller is repaired.
Next: user Adventure regression/hardware validation, broader hubs/masks/modes
and remaining graphics coverage. Do not claim complete Adventure campaign or
Uka/alternate placement visual acceptance from these scoped runs.

