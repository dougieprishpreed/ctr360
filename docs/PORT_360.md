# Crash Team Racing — Xbox 360 Port ("ctr360") — Master Plan

Working document. Kept in-tree so it can evolve with the code.
Status legend: [x] verified, [ ] pending.

## 1. Goal

Produce `default.xex` for Xbox 360 (homebrew-capable RGH/JTAG console, and
playable in Xenia Canary for development) that runs Crash Team Racing from the
ctr-native decompilation source, using **only the user's own retail disc dump**
as data. No retail data is ever committed to the repo.

## 2. Verified facts (evidence-backed)

- [x] Base source: `ctr-native` (CTR-tools) — active (6,679 commits), GPL-3.0,
      unity build: `main.c` includes `platform/native_*.c` + `game/game_unity.h`.
      32-bit build; SDL3 is the only host dependency. Cloned to `ctr360/`
      (origin = upstream GitHub, so future upstream pulls stay possible).
- [x] Reference sources cloned: `repos/CTR-in-C` (PSX rewrite), `repos/MKart360`
      (model 360 port).
- [x] Model port MKart360 proves the toolchain contract: MSBuild + Visual Studio
      2010 + Xbox 360 SDK (XDK 21256.3), `.vcxproj` with `Platform="Xbox 360"`,
      output XEX runs on RGH and Xenia. Seam pattern: `XBOX360_PORT` ifdefs +
      `x360_*` replacement functions (video = D3D9, input = XInput, audio =
      XAudio2, timing = QueryPerformanceCounter, logs/IO on `game:\`).
- [x] Target CPU (Xenon) is big-endian PowerPC (Xenia emulates BE). PSX payload
      data is little-endian → **data conversion is required** (see §5).
- [x] User's dump: `CTR - Crash Team Racing (USA).bin`, 605,698,800 bytes =
      raw 2352-byte sectors, Mode 2 Form 1, volume ID `SCUS-94426` (NTSC-U),
      `SYSTEM.CNF` BOOT = `cdrom:\SCUS_944.26;1`. md5 `ab95bfca8a4bb3d90daa6519acf6e944`.
      This matches exactly what `platform/native_disc_image.c` hardcodes
      ("common NTSC-U raw BIN layout: one MODE2/2352 data track at byte zero").
- [x] Xenia Canary already installed: `F:\downloads\xenia_canary_windows\xenia_canary.exe`
      (Sept 2026 build).
- [x] SDL dependency surface to replace for 360 (full list of non-vendored files
      touching SDL_*): `main.c`, `platform/native_platform.c`,
      `platform/native_renderer.c`, `platform/native_input.c`,
      `platform/native_audio.c`, `platform/native_perf.c`.
      Everything else — all of `game/`, the PSX facades (`native_lib*.c`),
      GPU primitive parser (`native_gpu.c`), GTE core, SPU/XA audio core
      (3,517 lines), CD/disc-image/asset layer — is platform-neutral C.
- [x] Single data ingestion point: the decompiled game reads all disc data
      through the PSX `Cd*` API (`CdSearchFile`, `CdRead`, `CdReadSync`, ...)
      implemented in `platform/native_cd.c` + `platform/native_disc_image.c`
      (+ extracted-file overrides in `platform/native_assets.c`). BIGFILE.BIG is
      read at raw sector offsets; sub-file formats are parsed in place by the
      game (levels `.lev`, models, textures `.vrm`, HWL audio, etc.).

## 3. Toolchain (XDK path — approved by user)

- VS2010 (Ultimate ISO, hash-verified MSDN `.iso`) + Xbox 360 SDK 21256.3
  ("XBOX360 SDK 21256.3.exe"), both from archive.org, downloading to
  `toolchain/`.
- Install order: VS2010 (VC++ component only if possible) → XDK (Full).
  Expected locations: `%XEDK%` = `C:\Program Files (x86)\Microsoft Xbox 360 SDK`.
- Then: hello-world `default.xex` that (a) writes a log to `game:\`,
  (b) clears/presents via D3D9, run in Xenia Canary.
- Build system decision (empirical, after install): either drive the XDK
  tools directly (`cl.exe`/`link.exe`/`imagebld.exe` from `%XEDK%\bin\win32`)
  via a script, or generate a `.vcxproj` + `.sln` exactly like MKart360 and
  build with MSBuild. Direct-tool build is preferred if it works (faster
  iteration); the vcxproj path is the known-good fallback.

## 3.5 C89 mirror pipeline (`build-360/`)

The VS2010-era XDK compiler (`cl.exe` 16.00.11886 for PowerPC) accepts only
C89 + MSVC extensions. Probe results (sources in `toolchain/scratch/probes/`):
rejects designated initializers, compound literals, `inline`, `stdbool.h`,
`_Bool`, declarations after statements, for-loop declarations, VLAs,
`restrict`, empty braces; accepts anonymous struct/union members, `long long`,
`snprintf`, `va_copy`, flexible and zero-length arrays.

`tools/ctr360/build_360_mirror.py` deterministically regenerates the mirror in
`build-360/gen/` from the pristine tree (the source is never edited) using
clang semantic-AST dumps + exact span edits:
- designated initializers -> positional, via a semantic type/member database;
- list-producing macros used inside initializer lists
  (`COLOR_CODE_PACKED_INIT`, `MakeColor`, `MakeColorCode`, `MakePoint`,
  `SET_MDM`, ...) -> dissolved to constant expressions at the use site via
  parameter substitution into the macro body; expression-context uses stay as
  calls and those helpers are emitted as `static __inline` functions;
- compound literals: expression contexts -> statement block + auto temp (exact
  semantics, works for constant and runtime contents); declaration inits ->
  plain brace lists;
- mechanical C89-ification: `inline` -> `__inline`; `stdbool.h` shim emitted;
  declaration hoisting (late declarations become top-of-block declarations,
  scalar initializers become assignments at the original spot; constant
  aggregates move whole); `for (int i = ...)` -> hoisted declaration + `i = ...`;
- verification: every touched unit re-parsed with clang (`--verify-syntax`)
  plus a global leftover scan. Full run:
  `py tools/ctr360/build_360_mirror.py --root . --out build-360/gen --verify-syntax`

## 3.6 Logging and diagnostics policy (Xenia findings)

Evidence from the hello-world probe (M1): under Xenia, `game:\` is the
containing folder of the xex and is READ-ONLY; `cache:\` is writable and
`hello360.log` was created there; `hdd1:`/`usb0:` are not mounted for a loose
xex. On a real console the executable's folder is also not a reliable write
target (retail-style `game:\` is read-only; RGH layouts vary).

Policy:
- Log file roots, in order: `cache:\` (Xenia dev loop - proven), `game:\`
  (opportunistic: RGH setups where the folder is writable), `hdd1:\`, `usb0:\`.
- Secondary channel: `OutputDebugStringA` on every line (cheap; may surface as
  `(DbgPrint)` records in `xenia.log`; Xenia's own log/verbosity settings are
  the debug surface of record for the emulator side).
- Never gate correctness on a log file existing.

## 3.7 Configuration file

`ctr360.ini`, read from the xex folder at boot (defaults when absent):
- `internal_resolution = psx | upscaled` - render at authentic PSX resolution
  and upscale at present (default; cheapest, most faithful), or render at the
  output resolution. The upscaled mode trades fill rate for sharpness and is
  the documented perf-costly variant (see PERFORMANCE_360.md §3.1).
- `widescreen = 0 | 1` - 4:3 (default) or 16:9 presentation.
- `log = 0 | 1` - write the debug log file at all.

## 4. Architecture mapping (PC → 360)

| Module | Current (PC) | Xbox 360 implementation |
|---|---|---|
| `main.c` | SDL base path, stdio | `main()` 360 entry; base path `game:\`; keep unity-include structure |
| `platform/native_platform.c` | SDL window/events/GL swap | Keep the `Platform_*` API & vblank semantics; D3D9 Present; 60 Hz pacing via `KeQueryPerformanceCounter` |
| `platform/native_renderer.c` | OpenGL (glad) + GLSL PSX shaders | NEW `native_xbox360_renderer.c`: D3D9. VRAM = single 1024×512 linear texture (packed 16-bit pairs ≈ D3DFMT_LIN_8_8); CLUT LUT texture; port GLSL shaders → HLSL (vs/ps_3_0); PSX blend modes → D3D9 blend states; mask-bit → stencil; framebuffer feedback via resolve → CPU mirror (keep dirty-rect scheme) |
| `platform/native_gpu.c`, `native_gpu_links.c` | platform-neutral | unchanged |
| `platform/native_input.c` | SDL gamepad + keyboard | XInput (4 pads); keyboard-only dev shortcuts dropped or pad combos |
| `platform/native_audio.c` | SPU/XA emulation + SDL audio stream | Keep full emulation; replace output only: XAudio2 source voice |
| `platform/native_perf.c` | SDL perf counters | `KeQueryPerformanceCounter` |
| `native_assets.c` / `native_disc_image.c` / `native_cd.c` / `native_str.c` | stdio/FILE on host FS | Keep logic; 360 CRT or Win32 (`CreateFileA`) on `game:\`; case-insensitive name lookup via `FindFirstFile` |
| `native_memcard.c` | host save files | `game:\` (or `hdd:\` later) |
| savestate/checkpoint/replay | internal features | compile out for 360 initially |
| `game/SubmitName.c` | SDL comments only | no change |

Constraints to respect (from `docs/MEMORY_MODEL.md`): keep game-visible
primitive packets retail-shaped (24-bit links stay bridge tokens), keep the
scratchpad contract, keep 32-bit PSX-shaped data layout.

## 5. Big-endian strategy (core risk)

Principle: the game code must see all retail data as if it were on a
little-endian PSX. Conversion happens **before the game parses bytes**, never
inside game logic.

Approach: **offline cooking of the user's disc image, in place.**
- Tool (Python): reads `CTR - Crash Team Racing (USA).bin`, writes
  `ctr-u-360.bin` of **identical length/layout** (ISO9660 structure, sector
  numbers, BIGFILE offsets all unchanged — every swap is same-size, in the
  data sectors only).
- Result: every read path the game uses (whole-file reads, BIGFILE
  sector-offset reads, HWL headers, XNF, STR) transparently receives
  converted data. Zero runtime code changes for the disc path.
- Per-format swap knowledge comes from: the game's own loaders
  (`game/LOAD/*.c`, `regionsEXE.h` structs, `LOAD_ModelPtrs.c` pointer swap
  conventions), CTR-in-C, CTR-ModSDK bigfile tooling, CTR-tools parsers (all
  open source) — verified against the retail data we have.
- Explicit non-goals in the cooker: XA audio (raw ADPCM byte stream — no swap),
  overlay binaries (MIPS code — never executed natively, skip), the PSX
  executable on disc (unused), STR video (only swap what `native_str.c`
  actually interprets as LE).
- Saves/memcards written by the 360 build are native-BE of our own making;
  cross-compat with PC builds is out of scope (can be added later).

Verification:
1. Python round-trip tests: swap-convert-back equals original; per-format
   logical parse equality (LE parse of original vs BE-aware parse of cooked).
2. Runtime: game boots and renders through staged format coverage (title
   screen first, then race levels, then everything).
3. User = visual judge in Xenia (per project convention: no trust in
   agent-side rendering claims).

Risk table:
- Unknown/undocumented format fields → visible garbage or crash: mitigate by
  staged coverage + crash-log on 360 (log to `game:\`).
- 32-bit pointer conventions inside cooked data (stored as offsets) — must be
  treated as 32-bit values (swap 4 bytes), not 16-bit pairs.
- Fonts/palettes are easy to get subtly wrong (swap granularity) — covered by
  round-trip tests + early visual check.

## 6. Milestones

> Performance and playability strategy: `docs/PERFORMANCE_360.md` (frame
> budget, workload inventory, risk ranking, backend design decisions taken
> before the 360 backend is written, benchmark ladder).

- **M1 — Toolchain** [x] DONE: VS2010 + XDK 21256.3 installed; hello `default.xex`
  (299 KB) builds with MSBuild and boots in Xenia Canary: D3D9 device OK,
  720p 16:9, QPC = 50 MHz, clean exit. XDK tools run standalone and via the
  MSBuild Xbox 360 integration. Xenia mounts the folder containing the xex as
  `game:\` (read-only there; `cache:\` is writable; `hdd1:`/`usb0:` unmounted).
- **M2 — ctr360 skeleton on 360** [x] DONE (platform backend): the 360 backend
  exists and the whole port compiles+links into a `default.xex` with the XDK
  toolchain. What landed:
  - `platform/xbox360/native_xbox360_video.c` — D3D9 renderer mirroring the GL
    backend function-for-function (VRAM as a 1024x512 linear G8R8 texture,
    pack/present passes, offscreen path, stencil modes, blend modes, y-flip and
    coordinate rules documented in the file header). Shaders are HLSL ports
    validated with the XDK's own `fxc`; the GPU->CPU readback uses the 360
    `Resolve` API on the existing 8x8 tile tracking.
  - `native_xbox360_platform.c` — XTL platform layer: D3D9 device bring-up, the
    VBlank emitter/VSync pacing ported from the SDL backend, Back+Start quit.
  - `native_xbox360_input.c` — XInput pad backend with the same PSX pad-packet,
    multitap, snapshot and analog-toggle behaviour as the SDL backend.
  - `native_xbox360_audio_out.c` + `sdl_shim/` — the SDL3 audio surface
    `platform/native_audio.c` uses, implemented against XTL (milestone 3 scope:
    a silent device that still pulls PCM, so the SPU/XA clocks advance).
  - `main_xbox360.c` — console unity TU (same include order as `main.c`) plus
    `native_xbox360_compat.h` for XDK macro collisions.
  - Build: `tools/ctr360/build_xex.sh` (MSBuild + Xbox 360 platform toolset),
    project at `build-360/xex/ctr360.vcxproj`; mirror is the build tree.
### 4.1 Test build (current)

Build and stage:

```bash
bash tools/ctr360/build_xex.sh Release     # mirror -> MSBuild+XDK -> dist/default.xex
bash tools/ctr360/prep_test.sh             # stages dist/{default.xex, assets/ctr-u.bin, README.txt}
```

`prep_test.sh` hardlinks the user's own dump as `dist/assets/ctr-u.bin` (the
path `NativeDiscImage_FindHostImagePath` looks for, case-insensitive) and writes
a README describing what the build can and cannot do yet.

Where it runs: copy `dist/` to the console or open `default.xex` in Xenia.
Log: `cache:\ctr360.log` (falls back to `game:\`, `hdd1:\`, `usb0:\`), mirrored
to the debug channel so `xenia.log` shows the same lines.

Platform scope that is in this build (verified by compile+link, expected to be
exercised by the first boot): D3D9 device bring-up, VRAM texture + pack/present
passes, PSX shader set (HLSL, fxc-validated), pad input, SPU/XA emulation with a
silent output device, asset/disc file IO through `game:\`.

Known gap for a real boot: the data is still retail little-endian. The cooker
(section 5) is what turns the title screen into something visible; the first
test run is a platform bring-up check and a boot-progress trace.

- **M3 — First user-facing build: title screen** (merged with the old M2/M3):
  disc cooker v1 (fonts, UI textures, logo/title assets converted) + the real
  renderer path; the first `default.xex` handed to the user boots to the title
  screen (stretch: into gameplay if the early builds hold up). No separate
  black-screen boot stub is shipped to the user. The blocker for a meaningful
  handoff is the endianness cooker (§5): the platform layer is ready, the data
  is not yet converted.
- **M4 — Race**: levels (`.lev`), models, textures, collision for one track;
  render a race scene.
- **M5 — Audio/Input**: SPU + XA via XAudio2; XInput mapping; menus navigable.
- **M6 — Perf + hardware**: vblank pacing, render perf, first RGH console test.
- **M7 — Completeness**: all tracks/cutscenes, memcard saves, polish.

## 7. Open questions (resolve empirically)

1. ~~Xenia: exact `game:\` behavior for a loose `default.xex`~~ **Answered
   (M1)**: the containing folder is the `game:\` root, read-only under Xenia;
   `cache:\` is writable there (`hdd1:`/`usb0:` unmounted). Log beside the xex
   on console; fallback chain `game:\` -> `cache:\` -> `hdd1:\` on emulator.
   Also: `VdSet3dVideoFormat` (xboxkrnl ord 873) is unimplemented in Xenia —
   non-fatal; avoid depending on it.
2. ~~XDK tools outside the VS2010 IDE~~ **Answered (M1)**: yes — `cl.exe`,
   `imagexex.exe` and MSBuild's Xbox 360 platform integration all work from
   command line.
3. Xenia D3D9 shader limits (ps_3_0) with the real PSX shaders — test as soon
   as M2; fallback = simplify shader (e.g., precompute LUT) or software
   rasterizer into the VRAM CPU mirror (contingency, not plan A).
4. Disc revision quirks: our dump is SCUS-94426 (single known revision family
   for NTSC-U); validate data-file layouts during cooker development.
5. Whether `ctr-u-360.bin` should be produced at build time (script) or shipped
   as a step the user runs once — likely the same "prepare assets" flow as
   MKart360 (`PUBLIC_BUILD_XBOX360.ps1` analogue).

## 8. Legal / licensing

- ctr360 inherits GPL-3.0 from ctr-native; if distributed, source ships with it.
- No retail data in the repo, ever. The user supplies their own dump; the
  cooker derives everything else locally.
- Xbox 360 SDK usage: user's own responsibility (abandoned tooling, standard
  practice in the 360 homebrew scene; project targets their own console).
