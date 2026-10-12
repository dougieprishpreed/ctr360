# Graphics debugging checkpoint — 2026-10-09

## Visual evidence and capture rules

The acceptance condition is recognizable, correctly rendered game graphics after
copyright (the racing flag or Naughty Dog crate). Frame counters, nonzero pixel
checksums, and reaching a title state are not sufficient.

A full PSX VRAM dump contains packed indexed textures, CLUTs, and framebuffers.
Displaying all its words as 16-bit RGB produces misleading noise. The old Xbox
`SaveVRAM` file has a TGA header but big-endian PSX words; it is not ordinary TGA.
`tools/ctr360/decode_psx_texture.py` explicitly decodes 4-bit indices and a CLUT.
The page-30 crate texture, CLUT 29180, UV rectangle (0,192,64,32), is grayscale
wood grain tinted orange by vertex colors.

The new `ctr360_main_fNNNN.tga` captures are ordinary 24-bit, top-origin images
of the resolved main target. The target is tiled: resolve into its tiled texture,
then use XGUntileSurface before writing pixels. The old linear-resolve hash
probe returned zeros and was invalid evidence. Xenia CPU readback must also be
enabled for these captures: `CTR360_READBACK=full` on `run_xenia.sh` supplies a
per-launch override without editing the persistent configuration. Its default
configuration was `readback_resolve = "none"`.

Window captures now reject minimized or covered windows, preventing desktop or
chat pixels from being mistaken for Xenia output. Keep tests minimized normally.
Do not open a separate PSX emulator. The user's two reference JPEGs are sufficient
to judge the crate/flag visually.

## Confirmed repairs

- Xbox pixel shader dither values were added to normalized RGB as -4..+3;
  divide them by 255, as the original renderer does.
- Segmented cutscene camera nodes remain raw little-endian. Read their counts,
  positions, rotations, and flags explicitly. The camera now advances from
  index 1 at game frame 13 to index 108 at frame 120.
- Sky vertices, face indices/counts, and colors remain raw little-endian.
  A count of 44 was read as 11264, walking past faces and corrupting OT links.
  DrawSky now reads those fields explicitly; the subsequent OT walk is clean.
- Model animation delta words also remain raw little-endian. A first lid delta
  word `ff 01 00 00` is 0x000001FF, not native BE 0xFF010000. The wrong read
  changed three full 8-bit/reset fields into 1-bit deltas with bad offsets.
  Both current-frame and next-frame decoders now use CTR_ReadU32LE. A CPU dump
  of emitted wood triangles changed from tangled geometry to a coherent box
  and lid (`20261009-delta-wireframe.png`).
- The blur initialization packet needs byte RGBC and native halfword XY writes,
  rather than whole native u32 stores over those fields.
- BM_AVERAGE must use 0.5 RGB blend factors. The Xbox backend used 0.25 because
  it copied GL's constant color while GL actually selected constant alpha.
- Restore the original renderer's stencil clear for isbg frames and reenable
  stencil after a framebuffer load. This repair alone made no visual difference
  to the tested crate sequence; it was not the cause of its remaining seams.

## GPU packet representation

The remaining blur corruption exposed a shared control-command boundary fault.
P_TAG.code reads byte 3 of a command payload. A native BE store of E1000A20 puts
0x20 there, so the parser treats a draw-mode command as a polygon. Full draw
environments and mixed control/geometry packets were affected.

The corrected contract is:

| Payload | Representation |
| --- | --- |
| OT tag/link token | native numeric u32 |
| E1..E6 GPU control command | PSX little-endian byte image |
| polygon RGBC | explicit byte fields |
| polygon XY | native x/y halfwords |
| polygon UV | explicit bytes; CLUT/tpage native halfwords |
| compressed animation bits/delta words | raw little-endian reads |
| cooked frame position/color words | native fields/words |

CtrGpu_WriteControlWord/CTR_GPU_WriteControlWord encode controls, including
SetDrawEnv and SDK facade macros. ProcessDrawEnv and ParseTaglessPrimitive read
their semantic values with CTR_ReadU32LE. Raw control writers in blur, fades,
particles, ghost masks, stars, spiders, cutscene lines, rain, HUD arrows, and warp
dust use the same helper. This avoids guessing a command type from RGB bytes.

## Build workflow

`build_xex.sh` reuses a valid generated mirror. It can synchronize the Xbox video
unit verbatim and regenerate an audited small set of standalone units through
the normal AST passes, checking all source/output hashes. Other changes or a
generator/header change require a full regeneration. Do not hand-edit generated
files. This command-boundary change requires one full regeneration.

The full generator previously accepted clang errors and transformed a partial
AST, which could erase initializers. It now aborts on any failed AST parse.
`common.h` provides native log declarations; `native_gpu.c` includes common.h so
its tracker initializer is parsed correctly. Incremental sync already refuses
invalid parses and rolls back its affected units.

Use tool-side completion waits for long builds/runs. Do not edit a shell script
while an invocation is sleeping inside it: bash can resume reading at stale
offsets in the modified file. One test required explicit cleanup after this
happened; Xenia was stopped and its log archived.

## Next concrete faults to address after the visual gate

The crate level (BIGFILE entry 514) has no level mesh, so these did not explain
its distorted animated models:

- Populated mesh payloads are still raw LE but level code reads native fields.
  Entry 41 has 1379 quadblocks and 8593 vertices. First quad indices should be
  973..981; a native BE read yields out-of-range values. Vertex positions also
  need an explicit representation decision before racing levels can work.
- RenderBucket_StoreInstanceAnimWord writes a native u32 over animFrame and
  vertSplit. Those are two s16 fields; on BE the frame lands in vertSplit.
  This automatic advancement path is skipped in the current cutscene mode.
- MainInit writes a packed clear-color word over isbg/r0/g0/b0; inspect its
  byte-field semantics before relying on colored level clears.

## Verified command/timer checkpoint

Earlier `delta-*`, `stencil-*`, and `blur-*` captures still show corruption and
do not pass the visual gate. The subsequent control-word repair removed the
phantom geometry and strips, leaving coherent crate geometry but strong trails.
Its log is `build-360/results/20261009-control-guest.log`.

The crate's raw segmented camera path has 401 nodes and flags 0: it requests
no clock blur. An old instrumentation insertion in MainFrame placed two probe
blocks between `if (clockSend)` and the original decrement block. The first
probe became the conditional body and `clockSend--` became unconditional.
This u8 field wrapped zero to 255, repeatedly enabling the blur path. The
active reference source retains the original conditional. Removing the two
misplaced probes restores it. The probe audit found no other such misplaced
branches/loops; existing texture-walk caps remain explicit runaway guards.

The corrected build produces final display captures with a coherent open crate
at frame 60 and a clean readable Naughty Dog front face at frame 120. The
repeated-image trails disappear. These satisfy the user's initial graphics
gate beyond copyright; they do not establish title/gameplay, performance, audio,
or input correctness.

`ctr360_display_fNNNN.tga` now captures the exact VRAM rectangle consumed by
presentation, after final scene storage. It untile-reads the GPU texture,
decodes PSX low-bit-red RGB555, and writes ordinary 24-bit top-origin TGA.
`ctr360_main_fNNNN.tga` can be an earlier intermediate image because a feedback
barrier also calls StoreFrameBuffer. Prefer final display evidence.

Mirror recovery: stricter AST checks revealed three standalone files relied on
unity headers: native_cd/libapi used stdint names without declarations, and
native_libgpu used a DB helper without game layout definitions. The first two
now use project types and libgpu includes common.h. A recorded three-unit
repair (`build-360/results/repair_control_mirror.py`) verified unchanged outputs,
reran 22 normal hoist edits, checked syntax, and refreshed the manifest. Hoist
failures now abort instead of being skipped; XDK-only C89 sources are explicitly
excluded from host parsing and validated by MSBuild. Final Release: zero errors,
81 warnings. Later mirror syncs took seconds and needed no full regeneration.

The final 250-second minimized full-readback run completed and Xenia stopped.
Nine final display frames were archived (13, 60, 120, 205, 300, 360, 400, 420,
450). The log contains zero fault lines and zero packet errors. Result metadata:
`build-360/results/20261009-clock-result.json`; XEX SHA256
`d0ebc86039a052d4f1fa280e78fb424d9e068e477fd1e0161b4c4baccc0590ab`.
The crate moves through multiple coherent poses and retains readable texture
mapping. Frame 120 is also provided at the presentation's 4:3 aspect ratio as
`20261009-clock-display120-aspect.png` (raw target is 512x216).

Later output is not fully validated: frame 400 contains green/white fragmented
geometry after the crate, frame 420 is background, and frame 450 shows flag
geometry with missing/incorrect checker coloring. The loader repeatedly stays
at stage 6 with mode1=40002000. These are the next graphics/loading issues; the
initial crate milestone is achieved, but there is no working title/gameplay yet.
