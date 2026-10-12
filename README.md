# CTR360

A native Xbox 360 port of **Crash Team Racing**, based on [CTR Native](https://github.com/CTR-tools/ctr-native) and the [CTR-ModSDK](https://github.com/CTR-tools/CTR-ModSDK) decompilation.

CTR360 runs the game from your own PlayStation disc dump. It includes 1280×720 rendering, an expanded 16:9 view, texture filtering, edge smoothing, controller input, audio, and persistent saves. Single-player races target 60 FPS rendering while keeping the original 30 Hz game simulation. Adventure hubs, menus, and other modes retain their normal cadence.

This is a development build. It has been played on real Xbox 360 hardware, including Adventure mode and saving/loading, but performance, graphics, and stability issues can remain. The latest performance and hub-transition repairs still need further console testing; a locked 60 FPS is not guaranteed.

## What you need

- An Xbox 360 capable of launching unsigned homebrew XEX files, with a compatible dashboard such as Aurora.
- A writable USB drive or HDD for the game folder and saves.
- Your own **NTSC-U (USA), SCUS-94426** Crash Team Racing disc dump: a raw `.bin` with 2352-byte sectors and its data track starting at byte zero. Other regions, compressed images, and extracted ISO files are not supported by this pipeline.
- A Windows PC with the build tools below.

The repository contains source code and conversion tools. It does not include the game disc, textures, music, or the Xbox 360 SDK. The Xbox 360 needs a converted disc image, produced from your dump by the supplied cooker.

## Building on Windows

### Install the tools

The Xbox 360 build uses:

- **Visual Studio 2010**, with Visual C++ installed.
- **Xbox 360 XDK 21256.3**, including the Xbox 360 Visual Studio/MSBuild integration. Obtain and install the SDK separately; it is not distributed here.
- **Git for Windows**, including Git Bash.
- **Python 3.11 or newer**, available as `python` in Git Bash.
- **LLVM Clang**, available as `clang` in Git Bash.

Install Visual Studio before the XDK. The build script expects the standard Windows installation paths for .NET Framework 4 MSBuild and the Visual Studio 2010 C++ targets. Clang parses and converts the modern C source into an XDK-compatible build tree; the XDK compiler then builds the Xbox 360 executable. SDL and a PSX compiler are not required for this target.

Open **Git Bash** and check that the command-line tools are available:

```bash
python --version
clang --version
git --version
```

### 1. Get the source

```bash
git clone https://github.com/dougieprishpreed/ctr360.git
cd ctr360
```

### 2. Generate the XDK-compatible sources

Run these commands from the repository root. `pwd -W` supplies the absolute Windows path required by the generator:

```bash
CTR360_ROOT="$(pwd -W)"
python tools/ctr360/build_360_mirror.py \
  --root "$CTR360_ROOT" \
  --out "$CTR360_ROOT/build-360/gen" \
  --verify-syntax
```

Wait for generation and syntax verification to finish successfully. The first pass takes several minutes. The generated `build-360/gen` folder is a build artifact: edit the original source when making changes, then regenerate it. Do not edit the generated copies.

### 3. Compile the executable

```bash
bash tools/ctr360/build_xex.sh Release
```

The script stages the tracked XDK project automatically. The executable is written to `build-360/xex/dist/default.xex`; the build log is `build-360/xex_build_log.txt`. If the build reports an error or a stale mirror, resolve it before proceeding. A stale mirror is refreshed with step 2.

### 4. Prepare your disc image

Replace the example path with the location of your own original disc dump:

```bash
python tools/ctr360/cook_disc.py \
  --disc "C:/Games/CTR/CTR - Crash Team Racing (USA).bin" \
  --out "$CTR360_ROOT/build-360/ctr-u-360.bin"
```

The cooker writes a separate converted copy and runs model and level byte-order audits. Keep the original dump. Only proceed after cooking and both audits finish successfully. Re-run the cooker when updating to a version that changes asset conversion.

### 5. Create the console folder

```bash
bash tools/ctr360/prep_test.sh --cooked "$CTR360_ROOT/build-360/ctr-u-360.bin"
python tools/ctr360/stage_release.py
```

The ready-to-copy folder is **`build-360/releases/ctr360`**:

```text
ctr360/
  default.xex
  README.txt
  assets/
    ctr-u.bin
    ctr360_graphics.example.txt
  memcards/
```

Here `assets/ctr-u.bin` is the converted image, despite its shorter runtime filename. Copy the whole `ctr360` folder to writable USB/HDD storage, then launch `default.xex` from your dashboard.

## Playing and saving

The Xbox controller follows the original button layout:

| Xbox 360 | Original PlayStation button |
| --- | --- |
| A | Cross — accelerate / confirm |
| B | Circle — use item / back |
| X | Square — brake |
| Y | Triangle |
| LB / RB | L1 / R1 — hop / powerslide |
| LT / RT | L2 / R2 |
| Start | Start — pause |
| Back | Select |

Use the left stick or D-pad to steer. **Back + Start exits the game**, so avoid pressing that combination during play.

Use CTR's normal save/load menus. CTR360 creates its own virtual memory-card files under `memcards/` beside `default.xex`; no Xbox profile or storage-selection dialog is needed. These files are not raw PSX memory-card images. Keep the game on writable storage and back up `memcards/` regularly.

## Updating

When rebuilding after a source update, regenerate the mirror and repeat the build and staging steps. The release staging tool preserves the existing `build-360/releases/ctr360/memcards` folder and personal graphics settings.

On your console, replace the executable and supplied assets while **keeping your existing `memcards/` folder** and `assets/ctr360_graphics.txt`, if present. Do not delete the old game folder before copying an update unless you have backed up its saves.

## Graphics settings

Defaults are enabled. To change them, copy `assets/ctr360_graphics.example.txt` to `assets/ctr360_graphics.txt` in the installed game folder and edit the values:

```text
interpolation 1
texture_filter 1
edge_aa 1
```

Each value accepts `0` (off) or `1` (on). Restart the game after changing settings.

- `interpolation`: intermediate render poses for the single-player 60 FPS target. Set this to `0` for the 30 FPS rendering fallback; 720p and widescreen remain enabled.
- `texture_filter`: smooths world textures.
- `edge_aa`: smooths polygon edges.

World geometry uses an expanded 16:9 projection. The original HUD and menu layout retain their authored proportions. Texture filtering improves sampling; it does not replace the original textures with higher-detail artwork.

## Troubleshooting

**The build cannot find MSBuild or the Xbox 360 platform.** Check the Visual Studio 2010 C++ and XDK integration installations. A current Visual Studio installation alone does not supply the legacy Xbox 360 toolset.

**The generator fails to parse a source file.** Check that Clang is on `PATH`, use the absolute paths in step 2, and resolve the reported syntax error. Do not compile a partially generated mirror.

**The game will not boot or assets appear corrupt.** Copy the entire staged folder and verify that `assets/ctr-u.bin` is the successfully cooked NTSC-U image. A raw PSX image has the wrong byte order for this build.

**Saving fails or reports a full card.** Check that `memcards/` can be created and written beside `default.xex`, and that the drive has free space. Back up existing saves before investigating or replacing card files.

**Performance is uneven.** Try `interpolation 0`. If reporting a problem, include the course, mode, how to reproduce it, and the build used. The game writes `ctr360.log` to the first writable location among `cache:\`, `game:\`, `hdd1:\`, and `usb0:\`; include that log when available.

For optional Xenia Canary testing, launch the staged XEX with `--allow_game_relative_writes=true` so saves can be written beside it. Console testing remains necessary for performance and compatibility.

## Credits and license

Thanks to CTR Native, the CTR-ModSDK contributors, PsyCross/Psy-X, and PSn00bSDK. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the source license and component notices. Crash Team Racing and its original assets belong to their respective owners.

This repository focuses on the Xbox 360 target. Inherited PC platform sources and development notes are included for reference; the large PC/PSX toolchain bundles are omitted. For the upstream PC build and its dependencies, see [CTR Native](https://github.com/CTR-tools/ctr-native).
