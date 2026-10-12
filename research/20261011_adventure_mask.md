# Adventure introduction repair — 2026-10-11

The user reports that saving works in Xenia, but Adventure freezes just before
Aku Aku appears in the starting hub. Their latest stopped run was archived as
`build-360/results/20261011-aku-user/{ctr360,xenia}.log` before launching tests.
Its last main-loop heartbeat is frame 1080, level 26, stage -1. The save write
completed successfully earlier in that run. No player card existed in the
staged dist directory; reproduction uses only the archived test profile A.

## Root cause

`LOAD_TalkingMask` queues a VRAM entry and then a DRAM file whose content starts
directly with `struct Model`. The asset cooker already handles the equivalent
single-model racer files, but omitted the talking masks: DRAM entries 439/441
(akubig) and 443/445 (ukabig), the two VRAM placements for each character.
Relocation pointers were converted, while model/header/animation/command/color
scalars were not. Xenon reads one header as 256, and the polygon color-cache
counts 49/64 as 0x31000000/0x40000000. The first render enters an enormous
color-cache copy. This is a real big-endian hardware problem.

The cooker now includes these four entries in its existing single-model
conversion, checking their expected names and mapped header spans. The normal
animation and polygon-command conversion runs for model offset zero. All
compressed vertex bytes stay unchanged. `test_talking_mask_cook.py` verifies
the actual dump: native header, 13 animation ticks/7 stored keyframes, frame
offsets, color-cache counts, disjoint swaps, byte payload preservation, rejected
wrong names and a complete round trip for all four variants.

The complete corrected cooked image differs from the previous packaged image
in exactly 5,976 bytes, all within those four DRAM entries. The image length and
ISO/BIGFILE layout remain unchanged. New SHA-256:
`1b7ad4e615a5da0e1b3e80f2d7ccf5afb6992fa0e4535e81d70d0c516a335d7e`.
**Existing installations must update assets/ctr-u.bin for this repair.**

## Camera position

The first corrected run progressed through the full hint, but direct 720p
captures showed no mask. `PushBuffer_SetMatrixVP` stores camera rotation as a
packed LE GTE matrix and its translation as native runtime world coordinates.
`AH_MaskHint_SetAnim` incorrectly loaded the latter with the LE matrix loader.
The scoped native branch now transfers these three coordinates numerically
to GTE registers 5–7, preserving the existing rotation representation and PSX
branch. Full absolute-root mirror regeneration/host AST is required for this
newly changed game unit.

## Runs so far

- `20261011-aku-probe-1`: 80 seconds requested, 83.96 wall, minimized. Reproduces
  the stall after the mask model loads. Xenia stopped, zero fault/packet lines.
  Those counts alone do not mean the scene works.
- `20261011-aku-fixed-1`: 110 requested, 113.94 wall, minimized. Cooked-data fix
  only. Mask state reaches talking (5), naturally completes XA, passes return
  transition (7), and reaches idle (0) at hub age 1140. No skip input was sent.
  Zero faults/packet errors. Direct output captures show the mask was off-screen;
  this is incomplete visual acceptance; the camera correction was tested below.

## Final acceptance

`20261011-aku-camera-final`: 105 seconds requested, 109.02 wall, minimized and
awaited to completion. Release XDK has zero errors / 87 warnings. Full absolute
mirror generation passes 2,533 hoists, zero review notes, zero remaining
designators and zero unit syntax failures. The actual generated mask function
contains the scoped numeric camera translation transfers.

Direct post-AA 1280x720 output frames 1170 and 1590 show a coherent, textured
Aku Aku beside Crash, with different mouth animation and vertical hover poses.
His XA state naturally ends at hub age 1194, hint state returns to idle at 1227,
and the driver's position subsequently changes from (-4311808,0,-356608) to
(-5014569,389,-354771) with logged speed 4696. Frames 2250 and 2370 show Crash
driving toward the hub's warp pads with attached wheels and a changing view.
No Triangle/skip input was submitted. A scripted steering pulse ended before
the hint released the driver, so this run verifies post-hint acceleration and
movement; it is not a new steering acceptance test. Zero faults/packet errors.
The speech's normal completion and mouth motion are verified, but no new
speech WAV was captured/listened to in this task. Prior user audio confirmation
still applies to the existing mixer.

The diagnostic hub captures are bounded and opt-in through the existing capture
file. The hint probe is sparse: state transitions and each 120 hub frames.
With a capture enabled, this run measures about 29–29.91 render/simulation FPS
in the hub, whose interpolation is intentionally disabled by the existing HD
guard. Physical performance, Uka Uka's live scene and alternate hub placements
are not claimed; all four files pass the actual asset conversion checks.

Final XEX: 4,206,592 bytes, SHA-256
`961a03feb2515f786db0a23275161f43d9211de1b2cd1f31ed5c4afd0a73af58`.
Cooked/staged image: 605,698,800 bytes, SHA-256 as above. Complete install is
`build-360/xex/dist`; complete package is
`build-360/releases/ctr360-hd-saves-aku-20261011.zip`. Update BOTH `default.xex`
and `assets/ctr-u.bin`, preserving `memcards/` and personal graphics settings.
The old memory-card-only ZIP contains the older image and is historical.
The new ZIP passes CRC and extracted XEX/image SHA-256 verification, contains
363,073,109 bytes and has SHA-256
`1e6fc04655a5d0828df062be4ad338ffc5d03c7e4eeef8997940c469a531bfac`.

Tests snapshot/restore script/capture settings and remove only their temporary
copy of the known archived profile A. They refuse to replace an existing live
player card. The helper is `build-360/results/20261011-aku-run.py`.
Normal player input is restored when each run exits. Physical Xbox testing is
still deferred while the user's controller is under repair.
