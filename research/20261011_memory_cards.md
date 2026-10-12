# Persistent native memory cards — 2026-10-11

The user reports full playability and card-full save failures. Their real Xbox
360 controller broke, so hardware testing is deferred. They explicitly approve
save data beside the executable on writable USB/HDD storage. This checkpoint
supersedes the HD report's open memory-card item; HD rendering is retained.

## Implementation

The existing file-backed card adapter used relative `memcards`. Xbox has no CWD;
`chdir` is intentionally an existence-check shim. `main_xbox360.c` now explicitly
sets `game:\memcards`, anchored to the launched XEX. The existing card filename,
icon and CRC contract is retained: slots/progress/options in BASCUS-94426-SLOTS,
separate BASCUS-94426G...... ghost files, slot0/slot1 directories. No signed Xbox
content container, gamer profile or storage chooser is required. Back up the
whole memcards directory and retain it during executable updates. These opaque
native ctr360 payloads are not PSX card-image imports; cross-endian imports are
not implemented. The game UI still provides four Adventure and seven ghost slots.

`NativeMemcard_WriteSaveData` writes a same-directory `.tmp`, checks all writes,
flushes (`FlushFileBuffers` on Win32/XDK), closes and publishes through
`MoveFileExA(REPLACE_EXISTING|WRITE_THROUGH)`. Failure preserves the previous live
file and removes the incomplete temporary file. POSIX uses flush/fsync/rename.
Ghost discovery/clone ignore pending files and admit only exact CTR names;
an existing regular file cannot masquerade as a card directory. Invalid buffers,
sizes and path overflow fail cleanly. OPEN_FAILED now maps to CTR I/O timeout,
not the misleading FULL result. Ordinary card data still uses the original CRC.

The main profile header is constructed as native fields (-18, sizeof profile).
The old LE whole-word comparison rejected a valid BE Xbox save after restart.
RefreshCard now compares the native header fields. Ghost runtime counts, full
alwaysOne/index stores and decoded trackID also use native fields; the old byte
clear erased the low byte of a BE track ID, and LE count reads could overrun lists.

The save route isolated the previously unclassified Adventure packet errors to
the garage's CS_Thread_InterpolateFramesMS line effect. Its RGBC was written as a
native packed word (opcode byte became 0x3f instead of 0x42) and XY as raw LE
words. It now uses byte RGBC and native XY halfwords; drawMode remains explicit
LE control data. This is a scoped packet repair, not proof of all Adventure modes.

## Build and tests

Full absolute-root mirror regeneration passes host AST verification: 246 units,
2533 hoists, zero manual-review notes, zero leftover designators, zero failures.
RefreshCard and CS_Thread were then regenerated through the audited standalone
AST pipeline (no site patches/static fixups), never edited inside the mirror.
Final XDK Release: zero errors, 87 warnings (two new const-qualifier warnings from
the generator's pointer hoists). XEX 5d26ddfed3396747dc4758fc9e26e4e37aeb471701a71bbc464b9829fc09121d; PE identity is in each run result.json.
The cooked/staged image remains e56cdeed96904ae83febce3b8fa86457bb25bb61537c82102a6dc4596acf6af0.

`tools/ctr360/test_memcard.py` compiles real 32-bit Win32 file functions and real
CRC functions. Separate writer/reader processes verify persistence, absolute
roots despite CWD changes, both slots, failed temp writes and final replacement
without clobbering the old save, overwrite, sorted ghost enumeration ignoring
pending files, deletion, short-read and CRC rejection. Isolated temporary roots
never touch player saves. `test_memcard_metadata.py` checks actual decoded ghost
track/character/time/index, native count/reset and seven-entry bounds.

All game tests launch minimized, await termination inside tools, and archive
logs, images, file identities and card bytes after exit. Pad/capture/trace options
are restored in finally. `run_xenia.sh` sets writable game paths per launch;
the emulator's persistent global configuration is unchanged.

- `20261011-card-save-1`: 50 requested/53.97 wall. Too short to reach Save;
  399 garage packet diagnostics, zero faults. Not a successful save test.
- `20261011-card-save-2`: 65/68.96, pre-garage repair. Normal Adventure/New,
  Crash/name A, first card slot; write result 0 and visible SAVE COMPLETED at
  display f1220. 408 garage packet diagnostics, zero faults. Card is 6016 bytes,
  payload 5760, native header ffee1600.
- `20261011-card-load-1`: 45/48.96, final candidate. Restart reads the same file,
  CRC result 0, menu visibly shows Crash/name A at f0920. Zero faults/packets.
  Run ended before the scripted profile confirmation.
- `20261011-card-overwrite-1`: 65/68.91, final candidate. Restart read/CRC 0,
  Adventure/New/name A, overwrite prompt Yes, write result 0 and visible SAVE
  COMPLETED f1260. Zero faults/packets; garage effect now parses cleanly. Card
  CRC16 over the complete payload is 0. The live file was replaced even though
  the deterministic new profile has identical content.
- `20261011-card-load-final`: 55/58.90, final candidate. Restart read/CRC 0,
  named profile visible, normal A at f962 selects it and requests its saved
  N. Sanity Beach (LEV26). Stopped while hub assets/audio banks are still loading;
  this does not verify full hub entry or play. Zero faults/packets, unchanged
  card SHA-256 bd24cbde6e15d9a9dd92f44f80a06dd7e91be919dbb66f83a9fdd4dced619883.

Inspect actual UI pixels, not only file/checksum/log success. Save completion:
`build-360/results/20261011-card-overwrite-1/ctr360_display_f1260-aspect.png`.
Reloaded profile: `build-360/results/20261011-card-load-final/ctr360_display_f0920-aspect.png`.
Those are decoded legacy UI captures; HD raster quality uses the post-AA output
captures defined in the HD report. Full VRAM is still packed data, not a frame.

## Delivery and remaining scope

Complete staged installation: build-360/xex/dist. Complete ZIP:
build-360/releases/ctr360-hd-saves-20261011.zip. It includes the final XEX,
unchanged user's cooked image, README, manifest and inactive graphics example.
Its files/CRC and XEX/image SHA-256 are verified after compression. No test saves
or input/capture scripts are included. The standalone release folder only holds
the executable/documents; use the ZIP or complete dist for a fresh installation.

The single generated A test save is archived in all test directories and removed
from dist after hash verification. The card was initially absent; no player save
was removed. Normal controls restored, captures disabled, Xenia stopped.
Previous HD checkpoint/prompt are archived in research/20261011_pre_memcard_checkpoint.md
and research/next_session_20261011_pre_memcard_archive.md.

Next: real Xbox save/create/overwrite/restart and HD performance testing once
the controller is repaired. In-game ghost recording/playback and complete hub,
race, high-score/options variation, broader modes and power-loss behavior on
physical FATX remain unverified; avoid broader acceptance claims. The known
garage packet issue is repaired, not an unresolved HD regression.
