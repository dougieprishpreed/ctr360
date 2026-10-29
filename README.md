# CTR360

A native Xbox 360 port of **Crash Team Racing**, based on [CTR Native](https://github.com/CTR-tools/ctr-native) and the [CTR-ModSDK](https://github.com/CTR-tools/CTR-ModSDK) decompilation. It is built entirely with open tools: [xSDK](https://github.com/xenosworks/xsdk) and [vulkan4xenon](https://github.com/xenosworks/vulkan4xenon), without the Microsoft Xbox 360 SDK.

CTR360 runs the game from your own PlayStation disc dump. It includes 1280×720 rendering, an expanded 16:9 view, texture filtering, edge smoothing, controller input, audio, and persistent saves. Single-player play targets 60 FPS rendering, in races and throughout the adventure hub, menus, and cutscenes, while the game simulation keeps its original 30 Hz rate.

CTR360 is fully playable on real Xbox 360 hardware. Development continues; if something goes wrong, see [Troubleshooting](#troubleshooting).

The earlier Microsoft XDK build is kept on the [`xdk`](https://github.com/dougieprishpreed/ctr360/tree/xdk) branch. It is superseded by this build and no longer maintained.

## What you need

- An Xbox 360 capable of launching unsigned homebrew XEX files, with a compatible dashboard such as Aurora.
- A writable USB drive or HDD for the game folder and saves.
- Your own **NTSC-U (USA), SCUS-94426** Crash Team Racing disc dump: a raw `.bin` with 2352-byte sectors and its data track starting at byte zero. Other regions, compressed images, and extracted ISO files are not supported.
- To convert the disc image: 64-bit Windows 10 or 11 with the downloadable package, or Python 3.11 or newer on any system.
- To build the executable yourself: Linux, or a Linux distribution under WSL on Windows.

The repository contains source code and conversion tools. It does not include the game disc, textures, music, or any SDK files.

## Getting default.xex

### Download a build

Download `CTR360-Xbox360-<version>.zip` from the repository's latest **Release**. On Windows:

1. Unzip it and double-click `Convert disc image.bat`.
2. Choose your disc image, the `.cue` or the `.bin`, or drop it onto the `.bat`. Your image is only read; the converted copy is written to `apps\ctr360\assets\ctr-u.bin`. Conversion takes a few minutes and about 700 MB of free space.
3. Copy the `apps` folder to the root of the console's hard drive, the drive FTP shows as `Hdd1`; if an `apps` folder is already there, copy `ctr360` into it instead. A folder on USB storage works too. Then start `apps\ctr360\default.xex` from your dashboard.

The converter needs no installation: it includes the official Python embeddable package.

Each release also carries `ctr360-<version>.zip`, the package the [Homebrew App Store](https://github.com/xenosworks/homebrew-app-store) installs into `hdd:\apps\ctr360\`. When the store installs CTR360, convert your image with the release zip as above and copy only `assets\ctr-u.bin` to `hdd:\apps\ctr360\assets\` on the console. Back + Start then returns to the store.

Every update to `main` is also built by GitHub Actions. Open the repository's **Actions** tab, choose the latest successful **xSDK build** run, and download its artifacts (downloads require a GitHub login): `ctr360-xex` contains only `default.xex`, its license notices, and an example configuration, for staging the folder yourself as described below; `ctr360-release` contains both release zips and the store's catalogue entry.

### Build it yourself

Install the toolchain prerequisites, then fetch and build the pinned dependencies:

```bash
sudo apt-get install build-essential bison flex texinfo libgmp-dev libmpfr-dev libmpc-dev \
  curl xz-utils patch python3 cmake ninja-build git ca-certificates
git clone https://github.com/dougieprishpreed/ctr360.git
cd ctr360
bash tools/xsdk/bootstrap.sh
```

Builds default to one compiler job to limit CPU and memory use; set `JOBS` to use more. The first toolchain build takes time and several gigabytes. Under WSL, builds are faster when the dependency and compiler directories are on the Linux filesystem; `CTR_XSDK_DEPS` and `XSDK_TOOLCHAIN` override their default locations. Then build with the paths the bootstrap script prints, or these defaults:

```bash
export XSDK="$PWD/build-xsdk/deps/xsdk"
export VULKAN4XENON="$PWD/build-xsdk/deps/vulkan4xenon"
export XSDK_TOOLCHAIN="$PWD/build-xsdk/toolchain"
export XSDK_GLSLANG="$PWD/build-xsdk/deps/glslang-xenon/build-host/StandAlone/glslang"
bash tools/xsdk/build.sh
```

The executable is written to `build-xsdk/output/default.xex`.

## Preparing the game folder yourself

Without the Windows package, convert your own original disc dump with Python. The converter writes a separate copy and validates it; keep the original dump and always convert from it, never from an already converted image:

```bash
python3 tools/ctr360/cook_disc.py --disc "/path/to/CTR-USA.bin" \
  --out "$PWD/build-xsdk/ctr-u-360.bin"
```

Then stage the console folder:

```bash
python3 tools/xsdk/stage.py --xex "$PWD/build-xsdk/output/default.xex" \
  --cooked "$PWD/build-xsdk/ctr-u-360.bin" --out "$PWD/build-xsdk/releases/ctr360"
```

The ready-to-copy folder is **`build-xsdk/releases/ctr360`**:

```text
ctr360/
  default.xex
  ctr360.ini
  ctr360.example.ini
  assets/
    ctr-u.bin
  memcards/
```

`assets/ctr-u.bin` is the converted image. Copy the whole `ctr360` folder to writable USB/HDD storage, then launch `default.xex` from your dashboard. With a downloaded build, stage the folder the same way, passing the downloaded `default.xex`.

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

Replace `default.xex`, and the converted image if you created a new one, while **keeping your existing `memcards/` folder** and `ctr360.ini`. With the release zip, copy its `apps\ctr360` folder over your game folder, including a `ctr360-xsdk` folder from an earlier release. It contains neither saves nor `ctr360.ini`, so both are kept, and you only need to convert your image again when the release notes say so. The Homebrew App Store updates its install the same way. Rerunning `stage.py` on an existing folder preserves both as well. Do not delete the old game folder before copying an update unless you have backed up its saves.

## Configuration

Edit `ctr360.ini` beside `default.xex` to change graphics and controller bindings. If it is missing, copy `ctr360.example.ini` to `ctr360.ini`. Restart after changes. The defaults are:

```ini
[graphics]
interpolation = 1
texture_filter = 1
edge_aa = 1
widescreen = 1
```

Missing or invalid settings keep their defaults.

- `interpolation`: `1` renders intermediate poses for 60 FPS throughout single-player play, `2` only in races, and `0` renders at 30 FPS. Game logic and timers keep their original rate either way; 720p stays enabled.
- `texture_filter`: `1` smooths world textures, `0` keeps them sharp.
- `edge_aa`: `1` smooths polygon edges, `0` turns this off.
- `widescreen`: `1` shows more of each course in 16:9, `0` keeps the original 4:3 view. On a widescreen TV, 4:3 is shown with black bars at the sides; on a 4:3 TV it fills the screen.

Frame rate varies with the scene. To reduce graphics cost, try `edge_aa = 0`, then `texture_filter = 0`. Texture filtering improves sampling; it does not replace the original textures with higher-detail artwork. In widescreen, world geometry uses an expanded 16:9 projection; the original HUD and menu layout keep their authored proportions, and in three- and four-player races each player's HUD reaches the outer edges of their view.

The `[controls]` section maps original PlayStation buttons to Xbox controls for all controllers. For example, `cross = RT` moves accelerate/confirm to the right trigger, and `r2 = A` moves R2 to A. Available buttons are `A B X Y LB RB LT RT LS RS START BACK DPAD_UP DPAD_DOWN DPAD_LEFT DPAD_RIGHT NONE`. Stick axes use `LEFT_X LEFT_Y RIGHT_X RIGHT_Y`; prefix an axis with `-` to invert it. The supplied example lists every destination and default. Names are case sensitive. The **Back + Start** exit shortcut stays active regardless of remapping.

## Troubleshooting

**The game will not boot or assets appear corrupt.** Copy the entire staged folder and check that `assets/ctr-u.bin` is a successfully converted NTSC-U image. An unconverted PSX image has the wrong byte order for this build.

**Saving fails or reports a full card.** Check that `memcards/` can be created and written beside `default.xex`, and that the drive has free space. Back up existing saves before investigating or replacing card files.

**Performance is uneven.** Try `interpolation = 2`, then `0`. When reporting a problem, include the course, mode, how to reproduce it, and the build used. The game writes `default.log` beside `default.xex`; include it when available.

**Taking screenshots.** Add a `[debug]` section with `screenshot = 1` to `ctr360.ini`. Back + LB + RB then writes the current frame, 1280×720 before edge smoothing, to `screenshot_NNN.bmp` beside `default.xex`.

**Graphics look wrong.** Add a `[debug]` section with `self_test = 1` to `ctr360.ini`. The game then checks the console's rendering at startup and records the results in `default.log`; include that log in your report, then remove the setting again.

The display path needs a console; emulators cannot validate this build's presentation.

## Credits and license

Thanks to CTR Native, the CTR-ModSDK contributors, xSDK and vulkan4xenon, PsyCross/Psy-X, and PSn00bSDK. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the source license and component notices. Crash Team Racing and its original assets belong to their respective owners.

This repository focuses on the Xbox 360 target. Inherited PC platform sources are included; the large PC/PSX toolchain bundles are omitted. For the upstream PC build and its dependencies, see [CTR Native](https://github.com/CTR-tools/ctr-native).
