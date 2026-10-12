# Adventure portal and systematic endian audit — 2026-10-11

The user's latest stopped run is archived at
`build-360/results/20261011-warp-user/{guest,xenia}.log`. After skipping the
welcome hint, Crash reaches the first glowing portal. The last normal
heartbeat is frame 1410, hub 26; the subsequent 72-byte warp-dust packets
have native numeric RGBC stores (`3a000000` in the raw-word diagnostic), so
code byte 7 is zero on Xenon instead of 0x3a. XY words also reverse the
native halfword order. The draw-mode writer already has the right LE byte
image (`200a00e1` when read as a native diagnostic word); it is retained.

## Repairs

- Warp dust uses byte RGBC and native halfword XY writers for both gouraud
  quads. Its camera-transpose rotation is packed LE and is explicitly read
  as such. All six rings must fit the primitive arena before linking any
  packets. The original PSX assembly remains intact.
- Warp champion metadata is native initialized state, so it is read through
  its typed field. Synthetic cup IDs use the existing random fallback rather
  than probing past the metadata array. Cup-track word slots use their native
  numeric low half, not the first two LE bytes of a BE word.
- Driving-physics previous rotation and contact normals are copied as native
  halfwords. The former LE reader/native whole-word store reversed their bytes.
- Battle weapon icons use the existing field-aware RGBC/XY/UV helpers. Default
  player teams are initialized as four byte fields rather than one packed word.
- Model color-cache counts above the command format's 7-bit address space are
  rejected with an asset-contract log before an enormous scratch copy.

## Systematic checks

`tools/ctr360/audit_endian_assets.py` independently discovers Model graphs via
relocation targets and named, mapped header arrays. It compares LE numbers in
this user's dump with BE values in the cooked image, checks animation frame
bounds and command terminators, and verifies compressed vertex/opaque frame
bytes remain unchanged. It runs automatically after a new image is cooked.
An involutive swap-list round trip alone would not detect omitted fields.

Before repair: 123,612 mismatched field values, all confined to 100 previously
omitted standalone files. These include podium, victory/defeat, Tawna, boss
head/body and Dingodile flame models. After repair: zero mismatches across
366 mapped files, 3,661 models, 5,826 headers, 2,658 animations, 57,708 animated
keyframes, 3,699 static frames and 628,071 commands; 5,058,863 numeric fields
checked. All 152 standalone files pass actual staged-byte, disjoint-site,
round-trip and corrupt-graph rejection tests. All four mask tests still pass.
The only changed image bytes are 391,600 bytes within those 100 files.

The standalone cooker now recognizes the format structurally instead of
maintaining a growing entry whitelist. Header pointer mapping, bounded spans,
printable names and mapped command/color pointers are required together.
Names, byte payloads and packed LE texture/GTE fields are preserved.

`tools/ctr360/audit_endian_source.py` inventories native-visible source branches
and fails builds for known mixed-field whole-word stores or LE reads of native
runtime vectors/metadata. Its detector/branch tests pass. The current scan has
255 C files, zero high-confidence hazards and 37 reviewed word-store sites.
Those remaining sites are native OT tags, numeric GTE projection scratch,
opaque copies of native XY halves, numeric shadow scratch, and byte-identical
clear-color copies followed by explicit opcode assignment. The source scan is
a review aid, not a complete semantic C type checker. Asset entries 220 and
607 have no discoverable Model graph and are explicitly listed for other
format coverage; the model audit does not claim all disc/runtime formats.

Cooked/staged SHA-256:
`2a8ac32de65e37155024dbf55e7f176d73654965ffc911bd2e2dc38c73704984`.
Both XEX and assets/ctr-u.bin must be updated in existing installations.

## Green-light crash and midpoint HUD duplication

The user's `../Clipboard_10-11-2026_01 (2).jpg` shows a guest kernel crash
at the green light. Both `20261011-warp-fixed-1` and `20261011-warp-drive-1`
actually called KeBugCheck: their clean guest fault/packet counts were
insufficient. The host log reports an unregistered GPU host pointer
00025C18/00025C1C. The first run proves portal/grid rendering only, not driving.

The scoped `20261011-warp-hdtrace-1` run (95 seconds requested / 99.03 wall)
reproduces this during the midpoint's instance execution, after its queue and
particle rendering. Boost visuals skip allocating their own depth range.
The normal renderer binds their current kart ranges in VehTurbo_ProcessBucket;
the midpoint omitted this phase. Fresh flames at the green light consequently
reach execution without a valid inherited range. MainHD now performs the
render-only turbo, burst and blowup range bindings after queueing and before
dispatch. Simulation/audio/effect ticks retain their original cadence.

`20261011-warp-return-1` (115 seconds / 119.11 wall) passes the kernel-aware
check, drives and steers beyond the green light, pauses, selects Exit to Map
and reloads N. Sanity Beach. Post-AA captures show attached wheels, changed
course views, the selected exit row and the returned hub. The test is scoped
to this route; race completion and the whole Adventure campaign are untested.

That run's paired frame 2021 captures confirm the user's flickering rank/fruit
report: the midpoint has two copies, the regular frame has one. Screenspace
models are also linked into the tail of the world OT, which the midpoint
walks without the normal UI draw environment, then replays cached UI. MainHD
temporarily hides screenspace instances from its private queue and restores
their original flags afterward. The HUD now belongs solely to decoded replay
on that frame. Interpolation also falls back if the instance list exceeds the
pose snapshot capacity, ensuring every modified flag can be restored.

`tools/ctr360/test_hd_midpoint.py` compiles the actual MainHD source and checks
fresh inherited ranges before execution, screenspace suppression/restoration,
LE rotations/native translations, angle wrapping and pose/DB/OT/timer rewind.
`tools/ctr360/check_xenia_run.py` checks completed guest AND host logs for
actual KeBugCheck calls/STOP lines and GPU link failures, plus requested race
progress. It deliberately ignores normal imported kernel symbols. A clean
check remains separate from visual acceptance. It correctly rejects all three
archived crash reproductions.

Opt-in pad script V2 adds L (level age) / G (global frame) clocks. The latter
advances while paused and drives two Down taps followed by Exit to Map.
Existing V1 files retain the level clock. No script means normal physical
inputs; test settings and temporary archived-profile copies are restored.

## Build and final verification

The final absolute-root source mirror passes 2,533 C89 hoists, zero review
notes, zero leftover designators and zero host syntax failures. XDK Release
has zero errors / 87 warnings. No mirror or reference repositories were edited
by hand. MainHD's final scoped changes are regenerated through the audited
AST synchronizer. Final `20261011-warp-final-1` run: 115 seconds requested /
119.04 wall, zero guest faults, packet/asset-contract/link failures and host
kernel failures, race age 588 reached, followed by hub 26. Normal input,
capture and trace settings restored; Xenia stopped and temporary test card
removed. No player save was replaced (the helper refuses an existing card).

Actual post-AA HD pairs 1912/2012/2067/2092 show one rank digit and fruit in
both intermediate and regular frames, with attached wheels and different
driven/steered course views. Frame 2185 shows Exit to Map selected; 2371 shows
Crash back in N. Sanity Beach. The route skips the welcome hint; the earlier
Aku test separately let it finish naturally. No full race completion, later
hub/portal progression, podium rendering or save-after-victory is claimed.
Diagnostic readback/ODS captures measure roughly 45.6–51.9 render FPS during
the race; this is not a fresh production 60 FPS or hardware performance claim.
The previously measured Time Trial production cadence is historical evidence.

Final XEX SHA-256:
`263378758e8b17b58f39287117b875592e9b0fc3f084d9a32321e42a25ba4f35`.
PE SHA-256:
`12888a729f92c2b4a23751a76310bb793aa634da43ac9862477506073f548296`.
Complete install: `build-360/xex/dist`.
Candidate ZIP: `build-360/releases/ctr360-hd-saves-adventure-20261011.zip`.
Update BOTH executable and cooked image; preserve memcards/personal settings.

## Real Xbox status

The user tried an earlier build from Aurora: black screen for a few seconds,
then return to dashboard. Hardware boot/playability is NOT verified. This is
an actual reported launch failure, not merely a deferred controller test.
Its cause is not established without the hardware log. The next console test
will follow Adventure verification in Xenia; preserve cache:\ctr360.log (the
logger also tries game:\, hdd1:\ and usb0:\ if its first root is unavailable)
and verify memory-card behavior. Xenia acceptance cannot establish hardware
compatibility or physical save durability.
