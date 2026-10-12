# Wheel and scene repairs — 2026-10-11

The user confirmed: “All fixes confirmed. Bursting crate and flyby are normal.
Restore player inputs and let's pause here.” This is the current accepted stop
point. The final minimized test completed and Xenia stopped; the opt-in staged
pad script is absent. Physical controller input is ready for the next launch.
No further source edits or tests were made after that acceptance.

## Scope and corrected assessment

The earlier `20261011-time-trial-drive-hud` and `20261011-demo-racer-hud`
captures proved loading, movement, HUD and about 30 FPS, but closer review
confirmed the user's report: karts lacked attached wheels and displaced wheel
textures/spikes moved across the display. The earlier broad visual acceptance
was too strong. Their result metadata now preserves this subsequent correction.
Crate burst, track preview and flyby required additional scoped repairs.

## Representation repairs

- `game/DrawTires.c`: both solid and reflection rotation-register words read
  explicitly as LE. Instance translation stays native. Wheel center Z uses the
  numeric signed low 16 bits instead of a union half selected by BE placement.
  Hazard animation updates that low half while preserving the upper word.
- `game/CAM.c`: start-line path interpolation reads signed raw LE coordinates
  before Q12 interpolation. Its interpolated runtime SVECTOR transfers through
  `CTR_GteLoadSV0`, rather than the raw-LE `gte_ldv0` path used by RotTrans.
  Numeric GTE results and flags return through the runtime store contract.
- `game/230/MM_TrackSelect.c`: the preview icon tpage is raw LE; its read now
  uses `CTR_ReadU16LE` before calculating preview upload coordinates.
- `game/233/CS_Instance.c`: authored matrix scale diagonals are stored LE for
  MatrixRotate. ModelHeader scale remains raw LE, so bone placement reads its
  three signed scales explicitly. The cooker's docstring describes more fields
  as cooked than its implementation actually converts; verify actual sites.
  In particular, model header scale at 0x18 is not converted to native here.
- `game/Particle.c`: projection scratch word 4 is assigned numerically from the
  LE r33 halfword, rather than stored via the BE-sensitive low-half union.
- `game/RenderBucket/RenderBucket_QueueExecute.c`: normal and depth-faded split
  polygons read the raw texture layout's CLUT/tpage halves explicitly as LE.
- `platform/xbox360/native_xbox360_video.c`: bounded dense final-display
  captures cover the burst, adjacent menu buffers, flyby and driving/turning.
  These are diagnostic capture points, not gameplay changes.

Rotations and texture layouts are generally LE image data, runtime vectors and
instance translations are native, and native packet field stores must follow
their own declared contract. Do not apply a blanket swap to mixed structures.
No cooker or asset change was needed for this wheel/scene repair.

## Fixtures and builds

The actual-function host fixtures and logs are in `build-360/results/`:

- `20261011-wheel-contract`: solid/reflection matrix loads, signed wheel corner
  halves and hazard update preservation, 6,240 corners across both paths.
- `20261011-scene-contract`: signed LE path interpolation at boundary ratios,
  and all 190 authored kart scales passed to the LE-reading matrix operation
  with padding/offsets preserved and one-time bake respected.
- `20261011-scene-transform-contract`: native camera vector/GTE result transfer,
  signed LE model scales in bone placement, frame clamp and odd-frame blend.

All three pass. The host is LE; these fixtures are not BE emulation. XDK PPC
compilation and Xenia exercise the target implementation.

Full regeneration `20261011-scenes-transforms-mirror.log` completes 2,532 hoists,
zero manual-review notes, zero leftover designators and zero host AST failures.
Release compiles with zero errors and 85 warnings. Audited RenderBucket sync
regenerates/verifies the split-polygon unit after the full mirror pass. Xbox
video is copied verbatim by the build. The mirror was never hand-edited.

## Completed minimized tests

| Archive under build-360/results | Scope and reviewed outcome |
| --- | --- |
| `20261011-time-trial-wheels` | Wheel repair: attached wheels in displays 1518, 1548, 1593, 1608, 1638, 1668, 1788 and 1878, including acceleration/turning/recovery. Burst and flyby still failed at this build. |
| `20261011-time-trial-scenes` | First scene repair: preview visible in adjacent displays 1000/1001 and wheels still attached at 1930. Burst 350/370 and flyby 1510/1570 still failed; this build was not accepted for those scenes. |
| `20261011-time-trial-scene-transforms` | Final camera/bone/split-texture repairs: user confirms all reported fixes. Burst 350/370 is coherent, preview 1000 is visible, and driving capture 1933 shows attached wheels. |

Each requested 150 seconds, exited 0, stopped Xenia and recorded zero faults or
packet failures. The final run took 154.03 seconds wall time; sustained final
2,000-frame FPS is 29.91. All launches were minimized. The helper supplies only
ordinary PSX pad bytes through the real menus/loading/race state machines.
The preview-dwell script is `20261011-time-trial-scenes-pad.txt`; there are no
menu/loader/gameplay flag bypasses.

The final static flyby captures 1513/1588 show close track surfaces. They are
not independent acceptance of the whole flyby animation; the user supplied
live confirmation that the flyby is normal. Preserve that evidence distinction.
Do not use counters or absence of faults as proof of graphics correctness.

Final race WAV: 441,000 frames, 44.1 kHz stereo, 881,235 nonzero samples, peak
6,622, RMS 1,032.77. Device playback reports zero failures. This is the game's
own mix, not system audio. Detailed race sound quality was not separately
listened to during this checkpoint; title music was already user-confirmed.

## Tested identity and input restoration

- XEX SHA-256: `b1c5de4d95fec71350ca8004a7184f9abf65a33c5267067c2b4f9902b3189e74`
- PE SHA-256: `c15075be610f9006c3cc3edcb55df03cdb5472f96e952423489a62cb51e26471`
- Cooked/staged SHA-256: `e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0`

The final XEX is 4,206,592 bytes; cooked/staged assets are 605,698,800 bytes.
The current staged XEX hash matches the archived final test. No source edits
followed the final build/run; checkpoint and evidence metadata were updated.

`20261011-scripted-run.py` restores/removes the staged script in `finally`.
`NativeInput_LoadScript` clears script rows at initialization and returns when
the file is absent. The final post-run check finds no script and zero Xenia
processes, so the next launch uses normal player input. Removing a script from
an already-running scripted XEX would not alone restore physical input.
A separate Xenia process appeared after cleanup (PID 17696, started at
10:58:15 local on 2026-10-11). The agent did not launch a new test and left
that later session running. The test script remains absent.

Work is paused. A complete controlled lap, broader track/mode/control coverage
and physical Xbox 360 validation remain possible future milestones when the
user requests them. Preserve the accepted build and all uncommitted work.
