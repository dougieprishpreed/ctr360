# Real-console hub lifetime / performance candidate â€” 2026-10-12

The user confirms the preceding candidate boots and runs on real Xbox 360
hardware via Aurora, with working saves, loads and USB logging. They defeated
the first boss and unlocked a hub door, but driving through it stopped the game.
The Guide remained usable. They also observed frequent dips and occasional
multi-second frames that recovered after pausing and unpausing.

This supersedes the earlier *unconfirmed hardware startup* status. It does not
confirm each of the graphical effects in the previous batch. The user reserved
gameplay testing; no Xenia was launched for this repair candidate.

## Fault evidence and lifetime repair

Original USB log: `../ctr360.log`, preserved without edits. Archive and symbols:
`build-360/results/20261012-hardware-user/`. Log: 2,582,271 bytes / 50,044 lines,
SHA-256 `0c5635c878b54ef2578afe0da8920d796c2dfe357557c9f2156f0bb39dcf98af`.
The archived PE is the previous effects candidate,
`fb8a0096260882ef66470c5c865c3583a8c1dffeed70fabcf69e4cbde5398dc6`.

The first fault is `c0000005 pc=820c96b8` reading `616b7562` (ASCII `akub`).
Symbolization locates it at LibraryOfModels_Store +0x30. Subsequent faults at
82087750 originate in LevInstDef_UnPack, with LR 8212b7d4 in
LOAD_Hub_SwapNow +0x1b4. The last heartbeat is level 26 (N. Sanity Beach),
load stage -1. This is an application access fault during the hub swap, not
evidence of a system/kernel crash or a failed initial asset open.

Release XDB public symbols omitted the game's own functions. A map was generated
by relinking the archived unchanged object into a separate investigation file.
Bytes at the relevant three functions match the archived PE at the same addresses.
The whole relinked text has 53 byte differences elsewhere (address references),
so it was not substituted for the original build. The map, disassembly and
investigation JSON are archived. Future build_xex.sh invocations enable the exact
linker map without changing optimization. Boot logs include the compile timestamp.

LOAD_TalkingMask and CS_LoadBoss clear/reuse the inactive hub's mempack, but left
gGT->level2 pointing into it. LOAD_Hub_SwapNow considered that pointer proof that
the destination was ready and read overwritten mask/boss bytes as a Level.
The `akub` fault is consistent with the mask reuse. This is a resident-memory
lifetime bug; no additional asset byte swapping is indicated by this evidence.

Native mask/boss loading now clears level2, retaining the destination ID so a
door can reload it without crossing the preload trigger again. A matching ID
is a cache hit only with a resident pointer. SwapNow drains pending loads,
reloads a valid remembered destination if needed, then accesses its models and
mesh. Unknown destinations defer the swap. Hub trigger connection indexes and
unused (-1) routes are bounded. Hub reload/completion messages remain visible.
Retail PSX branches retain their previous behavior.

## Hardware performance repairs

The USB log contains 12,000 detailed instance probes over 24 simulation frames,
with about 538 lines per affected frame. They occur at hard-coded old debugging
windows 1712â€“1714 and 3535â€“3565. The worst 120-render sample reports 1.57 FPS
while this window runs; normal presentation timing lines are often near zero.
The probes were accidentally essential because the classifier treated every
`hb ...` tag as a heartbeat, sending each line to guest stdout. There were also
22,968 UpdateVRAM trace lines, and Platform_BeginScene forced a durable USB
flush every rendered frame. These are concrete avoidable stalls consistent
with the reported behavior, not proof that every possible slowdown is resolved.

- Only the sparse `hb f=` heartbeat remains always on. Detailed nested hb
  probes require `watch`; guards, integrity errors and faults remain unconditional.
  High-volume renderer helpers also check the mask before formatting messages.
- Default tracing keeps boot/title diagnostics, disables VRAM/watch detail.
  Scheduled full legacy VRAM capture files require the VRAM trace opt-in.
  Ordinary launches no longer perform those readbacks and USB image writes.
- BeginScene does not flush the log. The existing one-second / 48-KB batch
  policy remains, with immediate durable boot, fault, guard and error messages.
  Routine essential status lines no longer write synchronously to guest stdout.
- UpdateVRAM removes diagnostic GetRenderTarget/AddRef/Release traffic and
  emits at most one opt-in line describing the actual dirty batch. Texture
  upload and GPU synchronization semantics are unchanged.
- The audio thread snapshots status under the mixer lock, releases the lock,
  then logs. A USB log flush cannot hold that mixer lock during sound updates.
- Frame timing increments once per presentation rather than twice; the old
  double increment made its frame-period sample condition unreachable. Sparse
  five-second `[perf]` reports retain average and maximum presentation intervals.

720p, expanded 16:9, filtering/edge AA, normal player input and the 60-render /
30-simulation racing path remain enabled. Adventure hubs still render at 30 Hz.
No hardware FPS improvement or crash-free hub traversal is claimed until retest.

## Verification and delivery

Actual-entry-point hub fixture passes mask and boss overwrite invalidation,
retained destinations, queue draining, reload before model/mesh access, cached
return traversal and invalid destination deferral. The previous invalidation
policy fails the same fixture. CD transfers and allocator reuse are mocked;
this is a lifetime boundary test, not rendered gameplay or a BE emulator.

Actual trace classifier applied to the console log: 41,722 lines become opt-in
detail; 3,777 remain essential (other enabled boot/title lines remain).
Actual Xbox logger/BeginScene/audio-thread fixture verifies suppressed probes,
no per-frame flush, periodic batching, durable fault output and logging after
the mixer lock is released. Existing effects and HD midpoint fixtures pass.

Full absolute-root regeneration: 2,533 hoists, zero manual notes, zero leftover
designators and zero host AST failures. Release: zero XDK errors / 87 existing
warnings. Logs: `results/20261012-hardware-perf-mirror.log` and
`results/20261012-hardware-perf-xdk.log`; exact map:
`results/20261012-hardware-perf.map`. Source audit still reports zero hazards,
37 reviewed word sites and 737 inventory entries across 255 C files.

Ready-to-copy folder: `build-360/releases/ctr360`. XEX 4,206,592 bytes:
`1b81644d4424e8e465ce5308d3f1e18eea2c018b9625de8744f3ab729b2d56b1`.
PE: `bf0598455393195d18e359ce6fab462fdd2d71325209c2dcdfa725b3c68340c3`.
Boot identity: `built Oct 12 2026 10:15:18`.
Assets retain the previous 605,698,800-byte cooked image:
`4f46a7420687d96bc0ba0a233f46bda2f27c74c2c902fe55d0ae05bd2dd9cfa1`.
No content changes are needed for these runtime lifetime and logging repairs.
`stage_release.py` verified the existing card unchanged; an independent comparison
against the pre-build card hashes also passes. No ZIP or old release siblings.
Normal inputs remain enabled and player settings were not overwritten.
Release identity: `results/20261012-hardware-perf-identity.json` and
`results/20261012-hardware-perf-release.json`.

Prior checkpoint/prompt archived as
`research/20261012_pre_hardware_performance_checkpoint.md` and
`research/next_session_20261012_pre_hardware_performance_archive.md`.

Hardware retest: load the existing Adventure save, drive through the unlocked
N. Sanity Beach door, travel back again, and play long enough to cover races
and a pause/unpause. Keep the fresh ctr360.log, including `[load]` and `[perf]`
lines if a stall remains. Prior graphical effect acceptance remains separate.
