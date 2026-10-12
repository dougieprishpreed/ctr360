# ctr360 continuation — effects/endian candidate, 2026-10-11

Workspace: F:\downloads\temp\python\hermes\ctrport\ctr360.
Read the top of HANDOFF.md and research/20261011_effects_endian.md first.
Older checkpoints are historical. ../repos is read-only; preserve dirty work.

The current larger candidate fixes confetti/target-box/mask attachment/particle
and warpball boundaries, cooks 77 missing minimap records, and repairs additional
matrix, lighting, collision, audio-vector, hazard metadata and camera/menu bugs.
Water OT links are bounded, but its appearance still needs confirmation.
All visible effect outcomes remain untested in this candidate. The user explicitly
reserved gameplay testing; do not launch Xenia unless newly authorized.

Ready-to-copy folder: build-360/releases/ctr360. No ZIP; same folder every build.
Preserve memcards and settings. Existing card was verified unchanged.
Update XEX AND assets/ctr-u.bin on installed copies. Refresh via
tools/ctr360/stage_release.py after updating the dist README.
Normal physical input is enabled; no active pad/capture files in release.

XEX: 0c3fea4f30393b66b2a37ffb59d544f795d43e44c59e8ba7094caa2442ea5b22
Image: 4f46a7420687d96bc0ba0a233f46bda2f27c74c2c902fe55d0ae05bd2dd9cfa1
Release: zero XDK errors / 87 warnings. Full absolute-root mirror verified AST:
2533 hoists, zero notes/designators/failures. No mirror hand edits.
Build: bash tools/ctr360/build_xex.sh Release. Broad/header/generator changes
require full regeneration using the absolute project root and --verify-syntax.
Do not change authoritative inputs during generation.

Source audit: 255 C files, zero high-confidence hazards; 737 boundary sites.
37 word-write review rationales saved. Model audit passes 5,058,863 numeric
fields; Level audit passes 9,465,171 fields and 9,388,660 opaque bytes.
The old image fails 640 minimap fields; only 1,280 minimap bytes changed.
These are format/source coverage, not full engine proof or visual acceptance.
Focused effects/HD host fixtures and strict staged Xbox ISO/path checks pass.

Retain 720p, true widescreen, filtering/AA and racing's 60 render/30 simulation.
No new production FPS, hardware, save-on-console or audio acceptance.
Hardware startup remains a separate deferred test: earlier Aurora/ABadAvatar
launch returned to dashboard after Base/Assets, before platform initialization.
Path/logging/checkpoint fixes are retained; exact failure remains unconfirmed.
If it fails again, obtain fresh cache:\ctr360.log (fallback game:\, hdd1:\, usb0:\).

Next evidence: user's podium confetti, missile target, Aku/Uka orbit/shield,
Mystery Caves fireballs, lightning orb/glow/streak, minimap opponent markers,
and post-finish Crash Cove water tests. Preserve progress, scope any remaining
repair to evidence, and never infer pixels from counters/checksum changes.
