# Effects and wider byte-order repair candidate — 2026-10-11

The user reported corrupted podium confetti, missile target lines, displaced
invincibility masks, partial water corruption after Crash Cove, missing Mystery
Caves fireballs, missing minimap racer markers and an invisible lightning orb.
They explicitly requested a larger candidate and reserved gameplay testing for
themselves. **No Xenia run is authorized for this candidate.** Visual acceptance,
race completion, audible output, performance and real Xbox boot remain untested
for the new build. Retain the earlier hardware startup repairs.

## Repairs and representation contracts

- DrawConfetti now loads the packed LE view rotation through the shared GTE
  loader and packs native width/height numerically for clipping. Its primitive
  allocation checks the complete next packet against the guard.
- Instance rotations remain packed LE, but instance translations are native
  world coordinates. LHMatrix_Parent now loads/stores native translation rather
  than using the projection-image APIs. This is the mask/shield/cloud attachment
  path. Shared CTR_GteSetRuntimeTransMatrix and CTR_GteStoreRuntimeMAC make
  this distinction explicit.
- Particle active/oscillator flags and oscillator configuration are native
  fields. Get/set now packs/unpacks numeric halfwords and copies the oscillator
  payload fieldwise without touching pool links. Scale/color/frame axes are
  consequently visible to the update/render paths with matching flags.
- Special particle streaks now write RGBC bytes and native XY halfwords through
  the packet helpers. Previous color stored across velocity/acceleration is an
  intentional opaque LE word; its decoded startVal is native numeric state.
- Missile tracker fill polygons copy native border x/y fields directly, rather
  than interpreting their native halfword bytes as a LE word.
- Warpball path-mode selection reads native tracker flags directly, replacing a
  LE word spanning velocity.z and flags.
- Minimap bounds, scale, origin, rotation mode and top-half mode are ten native
  halfwords. The cooker omitted all 77 UIMapSpawnMetadata records. They are now
  bounded/validated and converted. Original image size/sector layout is retained.
  Only 1,280 bytes in those records differ from the previous cooked image.
- The rotation review also repairs Armadillo, Snowball, Teeth, FlameJet, Plant,
  Adventure Sign/SaveObj, shield, burst, warp-pad, credit and reward matrix
  element access. MatrixToRot uses explicit LE reads, retaining the existing
  retail index/8-byte offset arithmetic. Hitbox inverse matrix rotation reads
  and writes use LE words; its inverse translation remains the packed projection
  image consumed by LinkedCollide.
- Reflective lighting (Vector and title trophy), audio direction vectors and
  collision wobble now store native numeric MAC results. Plant-eaten player/bot
  cameras and the existing bot missile path load native world translation.
- Plant/orca spawn delay/side metadata stays raw LE; consumers now decode those
  halfwords explicitly, like the existing armadillo/flame-jet consumers.
- PushBuffer camera IDs use numeric stores/reads instead of address-order bytes
  of native ints. Menu border state tests similarly use a numeric low-byte cast.
- Water list/rendered inherited draw links clamp to the same native OT range as
  other level paths. Saturated far depth and negative bias cannot overwrite
  adjacent OT memory. This is a concrete bounds repair, **not a confirmed cure**
  for the user's visual water issue. Water samples and vertex color/UV bytes
  retain their existing representation.

These are portable source/Xenon representation repairs, without emulator-only
behavior. They add no per-pixel processing or extra simulation ticks. Existing
720p/true widescreen, texture filtering, edge smoothing and 60-render/30-simulation
racing settings remain. No new 60 FPS or hardware performance claim is made.

## Verification

The focused fixture extracts the actual source helper bodies and enum constants.
It exercises particle flag/config values, oscillator link preservation, rotated
attachment world translation, hitbox transpose/inverse, native versus packed MAC
results, streak packet bytes/XY, four minimap orientations and the 3-player offset,
and far/negative/inherited/recursive water OT cases. It uses a small GTE register
fixture: it validates boundaries, not pixels or the full GTE implementation.
The existing actual-function HD midpoint regression also passes.

The source audit scans 255 native-visible C files. It now rejects direct packed
rotation evaluation (with two documented numeric staging/constant exceptions),
native-vector packed MAC stores, instance projection translation loads, particle
flag word crossings, streak packet whole-word stores and native scalar byte
aliasing, alongside the previous packet/runtime rules. Current result: zero
high-confidence hazards, 37 word sites retained for manual review, 737 boundary
inventory entries. It remains a review aid, not a complete C type checker.

The independent Model graph audit passes 5,058,863 numeric fields across 366
mapped entries, 3,661 Models, 5,826 headers, 628,071 commands, 57,708 animation
frames and 152 standalone models. Mapped entries 220/607 remain unidentified by
the Model format audit.

The new independent level audit follows runtime field layouts, independently
of cooker swap lists after structural discovery. The old image fails 640
minimap fields. The new image passes 9,465,171 numeric fields across 139 levels,
167,810 quadblocks, 897,586 vertices, 18,804 scenery vertices, 20,623 water
vertices, 77 minimaps and 1,112 EOR cameras. It also confirms 9,388,660 opaque
color/UV/draw-order/water-sample bytes are unchanged. Empty SpawnType1 tables
are legal. Both asset audits now run after cooking. This is coverage of these
formats, not a proof of every engine asset.

Full absolute-root source regeneration completed: 2,533 hoists, zero review
notes, zero leftover designators and zero host AST failures. Xbox Release
compiled with zero errors and 87 existing warnings. Generated effect helper
bodies were inspected. The staged new ISO passes the strict Xbox asset/path
fixture (including its missing-image error path). No emulator was launched.

Release refreshed in build-360/releases/ctr360, with its existing card hashed
before/after and unchanged. Player input remains enabled; there is no scripted
input/capture file in the release. No ZIP and no obsolete release siblings.
The temporary cooked image was promoted atomically to build-360/ctr-u-360.bin
and staged as assets/ctr-u.bin. Install both the new XEX and asset image.

XEX: 4,206,592 bytes, SHA-256
0c3fea4f30393b66b2a37ffb59d544f795d43e44c59e8ba7094caa2442ea5b22

PE: 4,243,456 bytes, SHA-256
fb8a0096260882ef66470c5c865c3583a8c1dffeed70fabcf69e4cbde5398dc6

The 37 remaining word-write inventory sites were reviewed as native tags,
numeric scratch/state copies, matching native XY byte copies or matching RGB
byte copies with an overwritten code byte. Their individual rationale is in
20261011-effects-word-review.json; they remain visible in the source inventory.

## Evidence

- build-360/results/20261011-effects-source.json
- build-360/results/20261011-effects-word-review.json
- build-360/results/effects-contract.log
- build-360/results/hd-midpoint-contract.log
- build-360/results/20261011-effects-map-retail.json
- build-360/results/20261011-effects-level-before.json
- build-360/ctr-u-effects-20261011.endian-audit.json
- build-360/ctr-u-effects-20261011.level-audit.json
- build-360/results/20261011-effects-image-delta.json
- build-360/results/20261011-effects-cook.log
- build-360/results/20261011-effects-mirror.log
- build-360/results/20261011-effects-build.log
- build-360/results/20261011-effects-xdk.log
- build-360/results/20261011-effects-build-identity.json
- build-360/results/release-current.json

Cooked image: 605,698,800 bytes.
SHA-256: 4f46a7420687d96bc0ba0a233f46bda2f27c74c2c902fe55d0ae05bd2dd9cfa1

## User test priorities

Podium confetti; incoming missile target box; Aku/Uka invincibility orbit and
shield; Mystery Caves fireballs; lightning orb/glow/streak and minimap target;
opponent map markers; Crash Cove water from the post-finish camera. Also check
plant hazards/camera, bursts/rewards and normal Adventure save/load. All fixes
are candidates until the user confirms their visible behavior.

Real console boot remains a separate deferred test. If it returns to Aurora,
retain the fresh ctr360.log from cache:\ (fallback game:\, hdd1:\, usb0:\).
The previous console log stopped before platform initialization; its exact
failing call remains unconfirmed. See research/20261011_hardware_boot.md.
