# Xbox hardware startup investigation — 2026-10-11

The user launched the Adventure/HUD candidate from Aurora via ABadAvatar.
It showed black then returned to the dashboard. The supplied console log was:

```
[boot] trace mask=00000019 (0=essentials-only)
[CTR Native] top-level exception filter installed
[CTR Native] Starting (Xbox 360)
[CTR Native] Version: 0.0.0-dev (unknown)
[CTR Native] Base: game:
[CTR Native] Assets: game:/assets
```

The XEX reaches main and asset path initialization. No platform/renderer line
or fault appears. The log does not identify the exact failing call. Following
these messages the old main calls a chdir macro (GetFileAttributesA on game:)
then NativeAssets_Validate. Treat the path/error-reporting defects as a scoped
candidate repair, not a proven explanation for every real-hardware failure or
an exploit incompatibility claim.

## Repairs

- NativePath preserves root separators for named devices (game:, hdd1:, usb0:)
  as it already did for C:. Parent extraction preserves those roots too.
- Under _XBOX, path joining/normalization emits backslashes. The desktop path
  policy remains forward slashes. Asset index keys retain their own portable
  lowercase/forward-slash representation. The installed XDK GameDiscCaching
  sample uses game:\media\... for device file paths.
- Xbox main omits the fake chdir/root-attribute gate. XDK has no process CWD;
  actual required-file validation already checks absolute paths.
- All fourteen direct asset-validation fprintf(stderr, ...) diagnostics use
  Platform_LogError. This preserves the diagnostic in ctr360.log and uses the
  Xbox logger's existing stdout routing for an unsupported/wedged stderr sink.
- The logger now fflush-es its CRT FILE at each existing batch flush, including
  immediate startup/fault/error messages. It still buffers normal trace output.
- Startup logs begin/end checkpoints for disc opening/ISO root reading,
  validation, memory-card root, platform, scratchpad and pointer setup. Open
  failure records errno/GetLastError before logging performs more file I/O.
  Early main failures close the log, and platform initialization failure stops
  before entering CTR_Main.
- The archived-run checker now counts explicit startup/required-asset failures;
  clean GPU packet counts alone cannot accept a returned-to-dashboard startup.

The cooked image remains unchanged (SHA-256
2a8ac32de65e37155024dbf55e7f176d73654965ffc911bd2e2dc38c73704984).
Player saves, settings and input behavior are unchanged.

## Independent checks

python tools/ctr360/test_xbox_asset_paths.py passes real-header device-root,
parent, separator and buffer-bound cases for Xbox and desktop. Its second
fixture compiles the actual native_disc_image.c and native_assets.c with a
strict Xbox file API boundary: every host path must start game:\ and contain
no forward slashes. It maps that prefix to the staged directory, validates the
real cooked ISO and required audio/data, then forces a missing image and
verifies failed validation through the logger. Direct fprintf is deliberately
forbidden in those included source files. This fixture does not emulate Xbox
hardware, FATX, D3D or the exploit.

python tools/ctr360/test_memcard.py and --xbox-paths pass isolated cross-process
save/reload, two-slot isolation, failed pending writes/replacements, checksum
rejection and ghost enumeration. The restricted sandbox initially denied the
native executable access to its temporary directory; the same host test passes
when run with the established compiler/test permission. No staged player card
was opened or changed. test_memcard_metadata.py also passes.

## Candidate verification and release

Full absolute-root mirror generation: 2533 hoists, zero manual review notes,
zero leftover designators and zero host syntax failures. Release: zero XDK
errors / 87 warnings. XDK platform units compile directly. No mirror edits.

Minimized positive run: build-360/results/20261011-hardware-boot-1, 24 seconds
requested / 28.07 wall, with full readback and temporary captures. All startup,
guest-fault, packet, link, asset-contract and host-kernel counters are zero.
The log shows corrected game:\ and game:\assets paths, successful disc root
(LBA 22, size 2048), asset validation, platform and game entry. Main-target and
legacy-display f0300 images were inspected: coherent wood crate, readable
Naughty Dog texture and attached sparks. This is a startup regression check,
not new gameplay/audio/hardware acceptance or a production FPS measurement.

Minimized negative run: build-360/results/20261011-hardware-missing-image-1,
five seconds requested. Only the staged image directory entry was temporarily
renamed (no content changes); the helper restores it in finally. The real
file logger persisted disc-open FAILED (errno and Win32 value), both missing
required assets, asset-validation FAILED and LOG CLOSED. No platform/game
entry or guest fault. Xenia stopped. The run checker should reject this
expected validation failure; a missing optional image alone is not fatal when
extracted overrides satisfy all required assets.

Capture, trace and audio-capture settings were restored. Physical inputs remain
normal; Xenia is stopped. No staged or release player save was changed. A
pre-stage snapshot plus the release refresh hashes confirm that the existing
one-file release memcards tree is intact.

The user's release convention is now a single ready-to-copy folder:
build-360/releases/ctr360, including default.xex, README.txt, assets/ctr-u.bin
and the inactive graphics example. No ZIP. Preserve this folder's memcards
and personal settings between builds. tools/ctr360/stage_release.py updates
only those four distribution files, verifies the saves, and records
build-360/results/release-current.json. The releases folder already contained
only ctr360 when refreshed, so there were no obsolete siblings to delete.

XEX (4,206,592 bytes):
c0c339502a303798bd4a92d7b7fe692eeede26117530a07f802764050ffa5ffb
PE (4,242,944 bytes):
2c7712f737e22445d69ad57df839c28942a3e947859e4acd8f9d70ceb3b2ddf6
Cooked/staged/released ISO (605,698,800 bytes), unchanged:
2a8ac32de65e37155024dbf55e7f176d73654965ffc911bd2e2dc38c73704984

Real Xbox startup still requires the user's console test. Save a fresh
cache:\ctr360.log (else game:\, hdd1:\, usb0:\ roots) before another launch
if it exits again. New checkpoints distinguish missing/unreadable image,
invalid ISO root, required-asset failure and platform/renderer initialization.
Do not claim the console crash is solved solely because Xenia boots.

