# ctr360 data-coverage matrix: the in-level draw path vs the endianness cooker

_2026-09-19. Read-only audit. Sources: `tools/ctr360/cook_disc.py` (the cooker),
the draw-path consumers (`game/RenderBucket/RenderBucket_QueueExecute.c`,
`game/RenderLevel/RenderLists.c`, `game/226/226_00_DrawLevelOvr1P.c`,
`game/MAIN/MainFrame_RenderFrame.c`, `game/RenderBucket/*`, `game/CTR/CTR_CycleTex.c`,
`game/LevInstDef.c`), the native GPU parser (`platform/native_gpu.c`),
the struct definitions (`include/namespace_Level.h`, `include/namespace_Instance.h`,
`include/namespace_Decal.h`, `include/psx/libgpu.h`, `include/gpu.h`, `include/macros.h`),
and **byte-level comparison of the user's retail dump against the current cooked
image** (`build-360/ctr-u-360.bin`, read-only; helper scripts `tools/ctr360/_audit_*.py`
were used and are scratch, deletable). No builds, no cooks, no image writes._

---

## 0. TL;DR

1. **The single most important correction to the current mental model:** the cooked
   image already contains **BIG-ENDIAN numeric words** for every cooked field, and the
   draw-path code reads most of those fields with **native host loads** (not `CTR_Read*LE`).
   That combination is correct. So the coverage question is *not* "is this field
   LE or BE" — it is **"does the consumer use a host load (needs the cook) or an
   explicit LE read (must NOT be cooked)"**. The game sources are full of explicit
   LE reads (`CTR_ReadU32AlignedLE`, `RenderBucket_ReadPackedWord`,
   `DrawLevelOvr1P_ReadPackedWord`, `CtrGpu_WritePackedUVWord`) precisely for the
   data the cooker does *not* touch.
2. **`ModelHeader.ptrCommandList` (0x20) contents are NOT numeric fields — they are a
   packed bit-stream / command encoding and must NOT be swapped** (evidence §3.1).
   The pointer *word* at 0x20 is a map-listed pointer and is cooked (correct); the
   **body it points at is uncooked today and must stay uncooked**. It is currently
   read with a host load, which is the correct pairing.
3. `ModelAnim.numFrames` / `ModelAnim.frameSize` are **uncooked LE u16/s16** and the
   consumer reads them with a **host load** → they read byte-swapped
   (`115 → 29440`, `188 → -17408`). This is a real, live defect class on the
   instance-draw path (proof: §3.2), currently masked because `RenderBucket_*` bails
   out early on the driver instances (`ptrFrameData == 0`, `RenderBucket_GetFrame`
   returns 0 under `CTR_NATIVE`).
4. `ModelFrame.vertexOffset` (always `0x1C` on disc) is **uncooked** and read with a
   host load → `0x1C000000`; `RenderBucket_PrepareDrawContext` line 5235 does
   `(char *)nextFrame + mf->vertexOffset`. Same class as (3).
5. `mesh_info` is **cooked as a by-product** (it sits inside the level file, its
   pointer words are map-listed, and the DRAM map cook covers `ptrQuadBlockArray`,
   `ptrVertexArray`, `bspRoot`). Its scalars `numQuadBlock`/`numVertex`/`numBspNodes`
   are **not** cooked, and the consumer (`MainFrame_OrPackedVisList`, `LevInstDef_*`)
   uses host loads → **live bug, but currently latent** because the ND-crate level
   (514) has `numQuadBlock == 0` (its mesh is a 4-quad stub).
6. `BSP` nodes, `QuadBlock`s, `LevVertex` arrays and PVS bodies are **entirely
   uncooked** (byte-identical retail↔cooked, verified). For entry 41 (Tiger Temple)
   that is 1379 quadblocks × 0x5C, 8593 vertices × 0x10, 907 BSP nodes × 0x20 —
   the whole visible level. `RenderLists_Walk1P2P` reads `bsp->flag` (u16),
   `box` (s16×6), `childID[0..1]` (u16) with host loads → the walk decides garbage.
7. **The 2D/UI path (`game/226` DrawLevelOvr1P) is the only in-level geometry path
   that was designed for uncooked data**: every read of a level-file byte
   (`quadblock->index[]`, `draw_order_low/high`, texture words, `LevVertex` words) goes
   through an explicit LE accessor. So it is *byte-order-consistent by construction*
   and needs no cook for those fields — but its **command-table walk (0x10..0x1F) is
   cooked, and 0x18/0x1A are read with a host byte load (`*((const s8*)block + off)`)**
   → that is the one place in 226 that needs the cooker's help, and it already has it.

Bottom line: the cooker's *pointer* coverage of the level file is complete and correct;
the frontier is **scalar coverage of the mesh/BSP/quadblock/vertex bodies plus the
ModelAnim/ModelFrame body words**, and the draw path is split between consumers that
need cooks (RenderLists, DrawLevelOvr) and consumers that must never be cooked
(the packed command/UV/colour streams).

---

## 1. Cooker inventory (what is cooked today)

`cook_disc.py` is a single-pass, same-length, in-place converter with a
round-trip + no-overlap gate per entry (`cook()`, lines 935–1120). Passes:

| # | Pass (function) | Target | Fields swapped | Gate |
|---|---|---|---|---|
| 1 | `convert_bigfile_directory` (:351) | BIGFILE.BIG header+entry table | `cdpos`, `numEntry`, every entry `{offset,size}` | round-trip |
| 2 | `convert_language_file` (:310) | entries 234–241 | `numStrings`, `offsetToPtrArr`, ptr table | round-trip + in-file offsets |
| 3 | `hwl_swap_sites` (:109) | `SOUNDS/KART.HWL` | header ints, SPU/OtherFX/EngineFX u16s, bank/song offsets, per-bank s16 sample indices, Cseq headers, per-song bpm/tpqn/seq offsets | round-trip + plausibility |
| 4 | `vram_swap_sites` (:420) | LT_VRAM `.vrm` entries | packed marker, chunk sizes, RECT s16s, **every u16 pixel VALUE** (element-wise) | round-trip + rect/size match |
| 5 | `dram_swap_sites` (:477) | every pointer-mapped DRAM entry (332) | word0 (map offset), map `numBytes`, every map offset word, **every listed pointer word** | round-trip + overlap + shape |
| 6 | `dram_pack_scalar_sites` (:543) | model packs (lookup head) | `LevTexLookup.numIcon`, `.numIconGroup`; per model `s16 id`, `s16 numHeaders` | shape (printable names, map agreement) |
| 7 | `dram_model_header_scalar_sites` (:867) | pack models | `ModelHeader`: `0x10`(4), `0x14`(2), `0x16`(2), `0x18/0x1A/0x1C`(2 each), `0x30`(4), `0x34`(4) — skipping any 4-byte slot the map lists | shape + map arbiter |
| 8 | `dram_level_scalar_sites` (:609) | `struct Level` at content+0 | frame `0xC` (`numInstances`), `0x14` (`numModels`) | shape: words 0/4/8/16/24 map-listed, counts 1..4096 |
| 9 | `dram_instance_scalar_sites` (:641) | level `InstDef[]` (stride 0x40) | `0x14..0x1A` scale s16s, `0x1C` colorRGBA, `0x20` flags, `0x24/0x28` ints, `0x30..0x3A` pos/rot s16s, `0x3C` modelID | per-entry name+model-pointer shape |
| 10 | `dram_level_model_sites` (:802) | level-embedded models | `id`, `numHeaders`, every `ModelHeader` scalar as (7) | shape + map arbiter |
| 11 | `dram_model_array_sites` (:740) | map-only model arrays (racer LODs) | same as (10), fallback branch | shape |
| 12 | `_animtex_chain_sites` / `_animtex_sites_from` (:698/:734) | AnimTex chains off `ModelHeader.animtex` (0x3C) and `Level.ptr_anim_tex` (frame 8) | `numFrames`(2), `frameOffset`(2), `frameSkip`(2); stride `0xC + nf*4`; sentinel = first entry address | per-entry `1..64` numFrames + map agreement on word0/`+4/+6/+8` |
| 13 | (inline in `cook()` :1037) | `Level.ptr_anim_tex` chain root | as (12) | — |

**Not cooked at all** (grep-verified: no pass names these):
`mesh_info` scalars, `BSP` bodies, `QuadBlock` bodies, `LevVertex` arrays,
`PVS` bodies (`visLeafSrc/visFaceSrc/visInstSrc/visExtraSrc` *targets* — their pointer
words are map-listed and cooked), `VisMem` body words (the `Level.visMem` *pointer* is
cooked; the pointed-at 0x90-byte block's 36 words are cooked **only where the file's
own map lists them**, which is partial — see §3.4), `ModelAnim.numFrames/frameSize`,
`ModelAnim.ptrDeltaArray` body, `ModelFrame.pos/vertexOffset`, `ModelAnim`'s frame
vertex bytes, `TextureLayout` bodies (u/v/clut/tpage — read with explicit LE helpers,
so correctly uncooked), `ptrColors` bodies (packed LE words, correctly uncooked),
`Level` scalars beyond 0xC/0x14 (`configFlags`, `clearColorRGBA`, `numWaterVertices`,
`numSCVert`, `glowGradient`, `stars`, `splitLines`, `numSpawnType2*`, `cnt_restart_points`,
`build_*` pointers), `Skybox` body, `LevTexLookup`-adjacent `Icon` bodies.

---

## 2. The read-convention rule (the matrix's axis)

Three consumer conventions exist in this codebase. A field's *cook requirement* is
determined by which one its consumer uses — not by the field's type.

| Convention | Helper | Cook needed? | Examples |
|---|---|---|---|
| **A. Host load** (native `*(u32*)p`, or a struct member access) | — | **YES — field must be BE in the file** | `mh->ptrCommandList`, `mh->scale`, `bsp->flag`, `mesh->numQuadBlock`, `inst->scale`, `ModelAnim.numFrames`, `mf->vertexOffset`, all map-listed pointers, `Level.numInstances/numModels` |
| **B. Explicit LE accessor** | `CTR_ReadU32AlignedLE`, `CTR_ReadU16AlignedLE`, `CTR_ReadU32LE`, `RenderBucket_ReadPackedWord`, `DrawLevelOvr1P_ReadPackedWord/Half`, `CtrGpu_WritePackedUVWord` | **NO — must stay LE** | `TextureLayout.u0/u1/u2/u3`, `QuadBlock.index[]`, `draw_order_low/high`, `LevVertex` pos/color words (in 226), `Model` names, `ptrColors[]`, packed command words, delta arrays, `Level.InstDef` name |
| **C. Runtime-only** (built in RAM) | — | n/a | `Instance.matrix`, `idpp.mvp/m3x3`, `AnimTex.frameCurr`, OT lists, `PrimMem`, scratchpad |

Evidence for the split:
- `include/macros.h:81-137` — `CTR_ReadU16LE/U32LE/AlignedLE` are explicit byte-wise
  reads under `CTR_NATIVE`; the retail (`#else`) path is a plain load. So every call
  site of these is a deliberate "this data is little-endian on disc" declaration.
- `game/RenderBucket/RenderBucket_QueueExecute.c:391-420` — `RenderBucket_ReadPackedWord`
  / `ReadTextureWord` / `ReadMatrixWord` are hand-rolled byte-wise LE readers used for
  `TextureLayout` words (`:2836-3436`), colour layouts (`:2291-2301`), delta arrays
  (`:459`), and the packed `ModelFrame.pos` word (`:1047`).
- `game/226/226_00_DrawLevelOvr1P.c:82-112` — the same pattern for the level overlay.
- Contrast: `game/RenderBucket/RenderBucket_QueueExecute.c:1347`
  `packedScaleXY = RenderBucket_ReadPackedWord(&mh->scale.x);` — **`ModelHeader.scale`
  is read LE byte-wise even though the cooker swaps it** (`0x18,2 ×3`). That is a
  **double conversion** and is discussed in §4.1 (it is a *second* live bug class:
  cooker + explicit-LE reader = field reads byte-reversed).

---

## 3. Field-by-field matrix for the in-level draw path

Legend: **P** = pointer (map-relocated), **S** = scalar needing a cook, **R** = runtime,
**LE** = must stay little-endian (explicit-LE consumer). "cooked?" = present in
`cook_disc.py` today. Evidence column = file:line of the consumer.

### 3.1 `ModelHeader` (`include/namespace_Instance.h:349`, stride 0x40)

| off | field | class | cooked? | consumer / convention | note |
|---|---|---|---|---|---|
| 0x00 | `name[0x10]` | LE bytes | no | `ModelName_ReadWord` (`game/DecalGlobal.c:6`, explicit LE); `game/230/MM_Characters.c:239-242` explicit LE | correct |
| 0x10 | `unk1` | S (4B) | **yes** (`:789/:858/:923`) | no consumer found in the draw path | cooked only when the map does not list it |
| 0x14 | `maxDistanceLOD` | S (s16) | **yes** | `RenderBucket_QueueExecute.c:1252` host load `(u16)mh->maxDistanceLOD` | correct pairing |
| 0x16 | `flags` | S (u16) | **yes** | `CTR_CycleTex.c:93` `(pHeader->flags & 2)` host load | correct pairing |
| 0x18..0x1E | `scale` (3×s16 + pad) | S | **yes** | `RenderBucket_QueueExecute.c:1347` **explicit LE** `ReadPackedWord(&mh->scale.x)`; also `(u16)mh->scale.z` at `:1352` (host) | **MIXED** — see §4.1 |
| 0x20 | `ptrCommandList` | P | **yes** (map-listed) | `RenderBucket_QueueExecute.c:2112`, `:2268`, `:4313`, `:4600`, `:4696`, `:4797`, `:4907`; `game/231/RB_Banner.c:46` | pointer word correct; **body must not be cooked** (§3.2) |
| 0x24 | `ptrFrameData` | P | yes | `RenderBucket_GetFrame` (`:1913-1924`) | pointer correct; **body needs scalars cooked** (§3.3) |
| 0x28 | `ptrTexLayout` | P | yes | `:2751-2760` `ptrTexLayout[texIndex-1]` then `ReadTextureWord` (explicit LE) | pointer + LE body = correct |
| 0x2C | `ptrColors` | P | yes | `:5165` null check; `:2265-2272` `commandList[0]`-count copy then `ReadPackedWord` | pointer + LE body = correct |
| 0x30 | `unk3` | S (4B) | yes | `RenderBucket_GetFrame:1923` `*deltaArrayOut = mh->unk3;` (host load) | correct pairing |
| 0x34 | `numAnimations` | S (4B) | **yes** | `:568-579` `mh->numAnimations` host load; `game/INSTANCE.c:364` | correct pairing |
| 0x38 | `ptrAnimations` | P | yes | `:579` `mh->ptrAnimations[inst->animIndex]` | pointer correct; **body needs scalars** (§3.3) |
| 0x3C | `animtex` | P | yes | `CTR_CycleTex.c:93-95` | pointer + cooked chain scalars = correct (the pass-12 fix) |

### 3.2 `ModelHeader.ptrCommandList` body — **the question in the brief**

**Verdict: opaque packed bit-stream. Do NOT cook. Current state (uncooked) is correct.**

Evidence:

1. **Consumer decode.** `RenderBucket_DrawFunc_Normal`
   (`RenderBucket_QueueExecute.c:4313-4322`) does `pCmd = (u32*)idpp->ptrCommandList; pCmd++;`
   then loops `while (*pCmd != 0xffffffff)`, splitting each word as
   `flags = (command >> 24) & 0xff`, `stackIndex = (command >> 16) & 0xff`,
   `texIndex = command & 0x1ff`, `colorOffset = (command >> 7) & 0x1fc`,
   and the strip-continuation bits `flags & 0x80` / `flags & 0x40` / `flags & 4`.
   Word 0 is a **count** (`commandList[0]`, used as the colour-cache copy count at
   `:2270`). Every consumer is a **bitfield extraction from the word as stored**.
   The identical pattern repeats in `_Special` (`:4600`), `_Reflection` (`:4696`),
   `_Split` (`:4797`), `_NormalAlt` (`:4907`) and `game/231/RB_Banner.c:46-100`
   (which additionally reads the first word as `CTR_ReadU16AlignedLE`).
2. **Offline bitfield plausibility (byte-level, both interpretations).**
   Scanning the command stream of all 20 ND-crate models (`_audit_cmdlist.py`):
   with the **LE** interpretation, 100% of commands satisfy
   `texIndex ≤ 512 && colorOffset < commandList[0]*4`
   (`ndi_box_lid` 84/84, `ndi_box_box_01` 684/684, `ndi_box_oxide` 777/777, …);
   with the **BE** interpretation, 0–50% do (`ndi_box_lid` 0/84).
   The flags byte also lands on the game's own bit meanings under LE
   (`0x80` new strip / `0x40` reuse-first-vertex / `0x04` cached vertex).
3. **The values are not addresses.** `low24` of the first commands are
   `0x570a01, 0x570a01, 0x570a01, 0x570a02, 0x570003` — repeating small
   pattern words, not ascending in-file offsets. A pointer-map relocator would have
   listed them (it lists every other pointer in the file: 2071 words in entry 514);
   **zero** words inside any command list are map-listed
   (`_audit_cmdlist.py`: `map-covered words inside = 0` for all 20 models).
4. **The loader does not touch them.** `LOAD_RunPtrMap`
   (`game/LOAD/LOAD_Assets.c:7-19`) only relocates the map's listed words, and the
   cook mirrors exactly that list. So even the "pre-relocation words must be swapped"
   rule from the skill does not apply: there is no `+= base` on these bytes.
5. **Contrast with the VRAM pixels.** The `.vrm` pixels *are* values because
   `LoadImage` copies them into VRAM as 5:5:5:1 fields and the renderer samples them.
   Command words are never copied anywhere — they are read in place, bit-sliced, and
   consumed as control codes.

**Consequence:** cooking them would corrupt the strip/strip-index/texIndex decode for
every instance (the `0xffffffff` terminator is byte-order-invariant, so the walk would
still terminate — a silent, total geometry corruption rather than a crash).
**Action: explicitly mark the command-list body as a no-cook region** (see §6, R1).

### 3.3 Model animation bodies (the live defect class)

| struct | off | field | class | cooked? | consumer / convention | verdict |
|---|---|---|---|---|---|---|
| `ModelAnim` (`namespace_Instance.h:328`, size 0x18) | 0x10 | `numFrames` (u16) | S | **NO** | `RenderBucket_GetFrame:1936-1969` host load; `RenderBucket_GetAnim` → `ptrAnimations[i]` | **bug**: `115 → 29440`, `55 → 21760`; `lastFrame = (numFrames & 0x7fff) - 1` becomes 0x72FF → `frameIndex` clamped to a frame far past the anim body |
| | 0x12 | `frameSize` (s16) | S | **NO** | `:1964` `frameSize = (u16)anim->frameSize;` then `MipsMultuLo(frameIndex, frameSize)` | **bug**: `188 → -17408 = 0xBC00` → frame pointer 256× off |
| | 0x14 | `ptrDeltaArray` | P | yes | `:1959` + `:2352` | correct |
| | 0x18 | first `ModelFrame` | — | **NO** | see below | |
| `ModelFrame` (`namespace_Instance.h:316`, size 0x1C) | 0x00..0x04 | `pos` (3×s16) | LE-packed | **NO** | `:1047` **explicit LE** `ReadPackedWord(&frame->pos.x)`; but `:2210-2227` and `:5233-5243` use **host** member loads (`mf->pos.x`, `nextFrame->pos.x`, `ctx->mf->pos.z`) | **mixed** — see §4.1 |
| | 0x18 | `vertexOffset` (int, = 0x1C) | S | **NO** | `:5235` `(char *)nextFrame + mf->vertexOffset` host load; `game/231/RB_Banner.c:28` | **bug**: `0x1C → 0x1C000000` |
| | 0x1C.. | packed vertex bytes | LE bytes | **NO** | `RenderBucketCompVertex` u8×3 reads (`:2382-2385`, `:2443-2446`), delta-stream bit reads (`:459-460`) | **correct as-is** (byte-wise, not numeric) |
| `AnimTex` (`namespace_Level.h:129`) | 0x4/0x6/0x8 | `numFrames/frameOffset/frameSkip` | S | **yes** (pass 12) | `CTR_CycleTex.c:12-30` host loads | correct (the HANDOFF/RESEARCH fix) |

Empirical confirmation of the *uncooked* state (retail ↔ cooked byte-identical):
`_audit_cooked.out` entry 514 model `ndi_box_lid`:
`MA.numFrames retail=7300 cooked=7300` (LE 115 / BE-read 29440);
`MA.frameSize retail=bc00 cooked=bc00` (LE 188 / BE-read -17408);
`MF.vertexOffset retail=20000000 cooked=20000000`.
Same for the driver pack (entry 259, `crash`): `MA.numFrames=1500`, `frameSize=e400` in
both images. And the *cooked* contrast is right next to it: `Model.id be00→00be`,
`numHeaders 0100→0001`, `MH.ptrAnimations 70010000→00000170`.

**Why the boot still reaches frame 13 with these uncooked:** every driver model in the
ND-crate level has `ptrFrameData == 0` (`_audit_cmdlist.py`, all 20 headers), and
`RenderBucket_GetFrame` under `CTR_NATIVE` returns 0 when `anim->numFrames == 0` —
except `numFrames` is never 0 when uncooked, it is `<<8`. The actual guard that saves
it is `RenderBucket_QueueDraw:2087` (`if (frame == 0) { …; return rbi; }`) plus the
`anim == 0` early-out at `:1925`. So the frame-13 wedging is **not** explained by these
fields; it is explained by the OT walk (§5). But the moment an instance with a
*non-null* `ptrFrameData` (814 of 1674 headers in the dump — `_audit_bsp.out` census,
e.g. `entry 1 startbanner ptrFrameData frame 0x5bf20`) is drawn, `vertexOffset` and the
frame-stride math are wrong.

### 3.4 `mesh_info`, `Level`, `BSP`, `QuadBlock`, `LevVertex`, `PVS`, `VisMem`

Byte-level result for **entry 41 (Tiger Temple)**, retail vs cooked
(`_audit_cooked.out`): the *only* level-file bytes the cooker changes are the
map-listed pointer words. Every geometry/scalar body below is byte-identical.

| struct | field | class | cooked? | consumer / convention | verdict |
|---|---|---|---|---|---|
| `mesh_info` (`namespace_Level.h:555`) | 0x00 `numQuadBlock` | S | **NO** | `LevInstDef.c:24,62`; `MainFrame.c:641` `(mesh->numQuadBlock+0x1f)>>5` host load | **bug** (entry 41: 1379 → 0x63050000 → huge memcpy size) |
| | 0x04 `numVertex` | S | **NO** | `game/226:8026+` uses `ptrVertexArray` only | latent |
| | 0x0C `ptrQuadBlockArray` | P | **yes** (map) | `LevInstDef.c:23`, `game/226:8031`, `COLL.c:1054` | correct |
| | 0x10 `ptrVertexArray` | P | **yes** | `game/226:8026`, `COLL.c:901` | correct |
| | 0x18 `bspRoot` | P | **yes** | `MainFrame_RenderFrame.c:938` → `RenderLists_Init1P2P` | correct |
| | 0x1C `numBspNodes` | S | **NO** | `MainFrame.c:636` `(mesh->numBspNodes+0x1f)>>5`; `MainInit.c:20` loop bound `for (bspIndex < mesh->numBspNodes)` | **bug** (entry 41: 907 → 0x8B030000 → the VisMem bspList init loop runs ~2.3e9 iterations) |
| `struct Level` (`namespace_Level.h:684`) | 0x00/0x04/0x08/0x10/0x18/0x190 | P | **yes** | `MainFrame_RenderFrame.c:938-942`; `LOAD_TenStages.c:467` | correct |
| | 0x0C `numInstances`, 0x14 `numModels` | S | **yes** (pass 8) | `LOAD_Hub.c:67-69`, `MainFrame.c:254` | correct |
| | 0x28 `visOVertSrc`, 0x170 `visSCVertSrc`, 0x178 `ptrSCVert` | P | **not map-listed → not cooked** | `MainFrame.c:742-746` `memcpy(…, level->visOVertSrc, ((level->numWaterVertices+0x1f)>>5)<<2)` | **inconsistent state**: pointer uncooked AND its length field uncooked (`numWaterVertices` 0x34, not cooked) — entry 41 has `ptr_water=0`, `ptrSCVert=0` so both are inert there, but a level with water would `memcpy` from a byte-swapped pointer |
| | 0x34 `numWaterVertices` | S | **NO** | `MainFrame.c:742`, `MainFrame_RenderFrame.c:886` | **bug** when non-zero |
| | 0x3C `levTexLookup` | P | **yes** | `DecalGlobal_Store` | correct |
| | 0x44 `ptr_tex_waterEnvMap` | P | **not map-listed → not cooked** | `DrawLevelOvr1P(..., level1->ptr_tex_waterEnvMap)` `MainFrame_RenderFrame.c:942`; consumed as `TextureLayout` in `game/226:9035` | **bug when non-zero** (entry 41: 0) |
| | 0xD8 `clearColorRGBA` | S | **NO** | `MainInit.c:562-569` `lev1->clearColorRGBA << 8` host load | **bug** (entry 41 has one; the clear colour would be byte-swapped) |
| | 0xDC `configFlags` | S | **NO** | `MainFrame_RenderFrame.c:948,961,989` `configFlags & 1/4` host load | **bug** — bit 0/2 land in the wrong place ⇒ wrong water/animated-vertex branch |
| | 0x48..0x68 `glowGradient[3]` | S | **NO** | `CAM_SkyboxGlow(&level1->glowGradient[0], …)` `:1037` | latent |
| | 0x6C..0xCC `DriverSpawn[8]` | S | **NO** | driver spawn (`VehBirth_SetConsts` path) | latent for cutscene |
| | 0x174 `numSCVert`, 0x37C.. `stars`, `splitLines`, `numSpawnType2*`, `cnt_restart_points` | S | **NO** | `MainFrame_RenderFrame.c:944` (AnimateQuad), COLL/CAM | latent |
| `BSP` (`namespace_Level.h:283`, size 0x20) | 0x00 `flag` (u16) | S | **NO** | `RenderLists.c:118,125,144` `bsp->flag & BSP_*` host load | **bug** — slot selection reads the wrong bits (LE `0x0001` reads as `0x0100`) |
| | 0x02 `id` (s16) | S | **NO** | not read in the draw path (debug) | latent |
| | 0x04 `box` (6×s16) | S | **NO** | `RenderLists_BoxOverlapsPushBuffer` (`:33-36`), `RenderLists_BoxPassesFrustum` (`:92`), `RenderLists_ProjectDistance` (`:105`) — all host loads through `CTR_PackS16Pair`/`gte` | **bug** — frustum/box culling on byte-swapped coordinates |
| | 0x10 `axis[4]` (s16) | S | **NO** | branch split (retail; native uses `childID`) | latent |
| | 0x18 `childID[4]` (u16, `BspChildId`) | S | **NO** | `RenderLists.c:200-201` `branch->data.branch.childID[0/1]`; `:213` `&bspRoot[((u16)record.childID) & 0x3fff]` host load | **bug** — `childID` 1 (LE `0100`) reads `0x0001`; `464` (`d001`) reads `0x01d0` → the walk descends to the wrong node (or, with the leaf flag test `0x4000` reading as `0x0040`, mis-classifies a branch as a leaf) |
| | leaf: 0x18 `numQuads`, 0x1C `ptrQuadBlockArray` | S / P | **NO / yes** | `game/226:8031-8032` `bsp->data.leaf.numQuads`, `:8138-8139`, `:9074-9075`; `COLL.c:1053-1054` | **bug on the count** (`numQuads` uncooked), pointer correct |
| `QuadBlock` (`namespace_Level.h:202`, size 0x5C) | 0x00 `index[9]` (u16) | LE | **NO** | `game/226:1035-1122` `vertices[block->index[i]]` — host array index, but the *array* is the uncooked `LevVertex[]` | **consistent only if both stay LE** (they do) — but `COLL.c` uses the same indices against a recomputed vertex array |
| | 0x12 `quadFlags` (u16) | S | **NO** | `COLL.c` collision flags | latent |
| | 0x14 `draw_order_low` (u32) | S | **NO** | `game/226:238` `DrawLevelOvr1P_SetActiveDrawOrderLow(block)` host load, then `>> selector->drawOrderShift) & 0x1f` (`:313`), and `game/226:2038` reads a **byte** of it via `DrawLevelOvr1P_ReadRetailQuadBlockByte(block, 0x18 + slot)` | **bug** — the draw-order byte index is computed from a byte-swapped word (the byte accessor at 0x18..0x1F is *outside* the `0x1C..0x2B` pointer-word special case at `:577-590`) |
| | 0x18 `draw_order_high` (u32) | S | **NO** | `game/226` face-mode fields | same class |
| | 0x1C `ptr_texture_mid[4]` | P | **yes** | `game/226:366,580,600` + `ResolveTexturePointerChecked` | correct (this is why `:577-590` has the pointer special case) |
| | 0x2C `bbox` (6×s16) | S | **NO** | 226 clipping | latent |
| | 0x38 `terrain_type`, 0x39/0x3A `weather_*`, 0x3B `mulNormVecY`, 0x3C `blockID`, 0x3E `checkpointIndex`, 0x3F `triNormalVecBitShift` | S | **NO** | COLL (`blockID`), CAM (`checkpointIndex`) | latent |
| | 0x40 `ptr_texture_low` | P | **yes** | `game/226:7393` | correct |
| | 0x44 `pvs` | P | **yes** | `LevInstDef.c:29,67`; `MainFrame.c:611-641` | correct |
| | 0x48 `triNormalVecDividend[10]` (s16) | S | **NO** | `FUN_8001f2dc` collision | latent |
| `PVS` (`namespace_Level.h:156`) | 4 pointer words | P | **yes** (map) | `LevInstDef.c:32,70`; `MainFrame.c:636-641` | correct — verified cooked (`QB[7].pvs` retail `98d80400` → cooked `0004d898`) |
| | `visLeafSrc/visFaceSrc/visInstSrc` **bodies** | R (built by CAM/COLL) | n/a | `MainFrame_OrPackedVisList` (memcpy / thunk) | **runtime** — `pvs->visInstSrc` points at a *list of instance pointers* that `LevInstDef_UnPack` swaps between InstDef*/Instance* in place (`LevInstDef.c:32-35`); it is `NULL`-terminated and built at load |
| `VisMem` (`namespace_Level.h:507`, size 0x90) | 0x00-0x3F `*List[4]` ×4 | P (to RAM) | **partial** (entry 41: only `[0]` map-listed) | `MainFrame.c:636-746` memcpy targets | **bug**: `visLeafList[1..3]` are NOT cooked → multi-player would memcpy to a byte-swapped pointer. 1P is fine |
| | 0x40-0x7F `*Src[4]` ×4 | R | n/a | written by `LOAD_Hub.c:88-91`, CAM | runtime |
| | 0x80-0x8F `bspList[4]` | P (to RAM) | partial (entry 41: `[0]` only) | `MainInit.c:20-24` fills them, `RenderLists_LinkBsp` | same partial-cook issue |
| `LevVertex` (`namespace_Level.h:424`, size 0x10) | 0x00 `pos` (3×s16) | LE | **NO** | `game/226:7944-7947` **explicit LE** `ReadPackedWord(&vertex7->pos.x)`; but `game/226:992` `CTR_COPY_VEC3(projected->pos, CTR_VECTOR_DATA(&vertex->pos))` is a **raw copy** into a struct whose fields are then read as s16 by `CTR_GteLoadSVec3V3` | **self-consistent**: the raw copy preserves LE order and the GTE loader repacks s16s from the same bytes. Entry 41 vertex 0 = `cfe20009 69130000` → pos (−7473, 2304, 4969), sane |
| | 0x06 `flags` (u16) | S | **NO** | `game/226:993` `projected->flags = vertex->flags` host load; later re-read as bytes | latent |
| | 0x08 `color_hi[4]`, 0x0C `color_lo[4]` | LE bytes | **NO** | `DrawLevelOvr1P_CopyColorWord` (`:985-988`) byte-wise | correct as-is |
| `TextureLayout` (`namespace_Decal.h:114`, size 0xC) | all (u0,v0,clut,u1,v1,tpage,u2,v2,u3,v3) | LE | **NO** | `RenderBucket_ReadTextureWord` (`:2836-3436`), `DrawLevelOvr1P_ReadPackedWord` (`:631,866,4440,4525,4854,9035`), `CtrGpu_WritePackedUVWord` | **correct as-is** |
| `Model.ptrColors` body | packed LE colour words | LE | **NO** | `RenderBucket_CopyScratchColorCache` (`:2265-2272`) + `ReadPackedWord` (`:2291-2301`); `game/231/RB_Banner.c:147-155` explicit LE | correct as-is |
| `ptrDeltaArray` body | packed LE bitfield words | LE | **NO** | `:2352-2376` `(temporal >> 6) & 7` etc. — bitfield extraction from the stored word | **correct as-is** (verified sane: `xBits/zBits/yBits` all ≤ 7) |

### 3.5 `InstDrawPerPlayer` / `Instance` (`namespace_Instance.h:471/:562`)

Both are **runtime structures** built by `INSTANCE_LevInitAll` (`game/INSTANCE.c:213-280`)
from the (cooked) `InstDef` and by `RenderBucket_QueueDraw`. No field of either is read
from disc, so **none needs a cook**. The load-bearing boundary is `InstDef` (pass 9) —
`memcpy((u8*)inst + offsetof(Instance,name), levInstDef, offsetof(InstDef, ptrInstance))`
copies 0x2C bytes verbatim, i.e. `name`, `model`, `scale`, `colorRGBA`, `flags`, `unk24`,
`unk28`; the cooker's InstDef list (`0x14..0x28`) covers exactly that prefix plus
`ptrInstance`, `pos`, `rot`, `modelID`. `InstDef.name` is a byte string (no cook — fine).
`idpp.mvp/m3x3` are computed (`RenderBucket_StoreMatrixWords`, `ConvertRotToMatrix`);
`idpp.ptrCommandList/ptrTexLayout/ptrColorLayout` are *copied from the cooked
ModelHeader* at `:2112-2114`; `idpp.mh`, `lodIndex`, `depthOffset`, `otRange*` are set by
`QueueDraw`.

---

## 4. The two systematic mismatches found

### 4.1 Fields that are cooked **and** read with an explicit-LE accessor (double conversion)

| field | cooked by | read by | effect |
|---|---|---|---|
| `ModelHeader.scale` (0x18, 2×3) | pass 7/10/11 | `RenderBucket_QueueExecute.c:1347` `ReadPackedWord(&mh->scale.x)` | the packed word is byte-reversed relative to what the reader expects ⇒ `scaleX/scaleY` swap, `scale.z` (host load at `:1352`) is right ⇒ **inconsistent scale triple** |
| `ModelFrame.pos` (0x00, 3×s16) | *not* cooked | `:1047` explicit LE (correct) **vs** `:2210-2227`, `:5233-5243` host loads (`ctx->mf->pos.x`, `nextFrame->pos.x`, `ctx->mf->pos.z`) | two consumers of the same field disagree ⇒ whichever runs second is wrong |
| `ModelFrame.vertexOffset` | *not* cooked | `:5235` host load | reads `0x1C000000` |

These are the highest-value *cheap* fixes: they are one-line consumer changes
(switch to the explicit-LE accessor, or add the cook site) and they are all on the
**instance** draw path, which is exactly what frame 13 exercises (14 queued driver
instances).

### 4.2 Fields neither cooked nor LE-read (the real missing coverage)

`mesh_info.numQuadBlock/numVertex/numBspNodes`, `BSP.flag/id/box/axis/childID/leaf.numQuads`,
`QuadBlock` scalars (`quadFlags`, `draw_order_low/high`, `bbox`, `blockID`,
`triNormalVecDividend`, `terrain_type`), `LevVertex.flags`, `Level` scalars
(`configFlags`, `clearColorRGBA`, `numWaterVertices`, `numSCVert`, `stars`, `splitLines`,
`glowGradient`, `numSpawnType2*`, `cnt_restart_points`), `ModelAnim.numFrames/frameSize`,
`ModelFrame.vertexOffset`. All of them are read with **host loads**, so all of them are
byte-swapped at runtime today.

---

## 5. What is actually blocking frame 13 (evidence from the last run log)

`F:/downloads/xenia_canary_windows/cache/ctr360.log` (Sep 19 10:12, the newest):

- `:39888` `w1 f=13 bsp=00000000 pb=8234501c` and `:39889` `lg4 f=13 leafs=0` —
  `level1->ptr_mesh_info->bspRoot == NULL` for entry 514 (confirmed offline:
  `_audit_mesh.out` "mesh_info: numQB=0 numV=0 ptrQB=0x4a0 ptrV=0x4a0 bspRoot=0x0 numBsp=0").
  So `RenderLists_Walk1P2P` draws **0 leaves** and `DrawLevelOvr1P` returns at
  `game/226:9769` (`mesh->ptrQuadBlockArray == NULL` is false, but `numQuadBlock == 0`).
  **The mesh scalars are NOT what blocks frame 13** — the cutscene level simply has no
  BSP tree. They will block the first *real track*.
- `:39892` `DrawOTag#23 enter p=826ED938`, then 1027 packets walked and the log stops
  mid-walk at `:41958-41959`:
  `walk#23 pkt=826CFD0C len=2 code=00 tag=02eca7e4` / `prim code=00 len=2 primLength=3`.
  The 1026 preceding packets are all `len=0` — `code` values walking down
  `30,2c,28,…,04,00,fc,…,e8` at addresses `826EC984 → 826EC93C`, i.e. the OT walking
  *backwards through the OT table itself* (`tag=00eca8xx` = the OT slot's own token).
  The last packet (`826CFD0C`, `len=2`, `tag=02eca7e4`) has a **2-word payload** and is
  parsed as `primLength=3` — the parser consumed 3 longs where the tag declares 2, or the
  packet's payload words are themselves a link. `ParsePrimitivesLinkedList`
  (`platform/native_gpu.c:1136-1218`) would then either break out on
  `currentPacket != endPacket` (printing a `NATIVE_GPU_ERROR`, which goes to `stderr`
  only — see `platform/xbox360/native_xbox360_log.c:170-177`, and `grep "CTR GPU"`
  over `ctr360.log` = **0 hits**, so any such message is invisible in the captured log)
  or walk into the next link. Either way the walk never returns, which matches the
  observed wedge (audio pump alive, no `walker done`).
  **This is a GPU/OT-link issue, not a data-endianness issue** — the OT is built in RAM
  by the cooked game code. It is *ranked first* below only because it is what is
  actually stopping the frame, and it is not fixable by the cooker.

---

## 6. Ranked next cook passes

Ranking axes: **(a) blocking visible rendering** (does a *visible* in-level draw need it,
and how soon), **(b) risk** (chance the pass corrupts something, given the map arbiter
and the round-trip/overlap gates).

### R1 — Documentation/no-cook guard (not a pass; do first, zero risk)
Write down the **no-cook region list** in `cook_disc.py`'s docstring and add a
regression assertion: for every model, assert that no site falls inside
`[ptrCommandList, terminator]`, `[ptrColors, ptrColors+count*4]`, any `TextureLayout`
body, any `ptrDeltaArray` body, or any `LevVertex`/vertex-byte region. Reason: these are
the streams whose corruption is *silent* (§3.2), and the cooker's gates cannot see it.
Effort: minutes. Risk: none.

### R2 — `ModelAnim.numFrames/frameSize` + `ModelFrame.vertexOffset` (all three model passes)
- **Blocking:** YES, as soon as any instance with `ptrFrameData != 0` (814/1674 headers
  in the dump) or a real `ptrAnimations` chain is drawn. It is *the* instance-draw
  scalar class. Frame 13 already queues 14 driver instances.
- **Risk: low.** The structure is tiny and the walk is already implemented for
  `AnimTex`; the map arbiter excludes `ptrDeltaArray` (map-listed) and the rest is
  s16/u16/int at fixed offsets from a root the cooker already validates
  (`ModelHeader.ptrAnimations` is map-listed; each `ModelAnim` is reached through it).
  Shape validation: `1 <= numFrames <= 0x7FFF`, `frameSize == 0x18 + numFrames*...`
  is *not* a reliable invariant — instead validate `numFrames <= 0x2000` and
  `frameSize > 0 && frameSize < 0x2000`, and `ptrDeltaArray` map-listed-or-zero.
  `vertexOffset` is a constant `0x1C` in every sample seen — validate it as such
  (a cheap, strong check).
- **Interaction:** whichever way you go, make the *consumer* and the *file* agree.
  Simplest and lowest-risk: **cook the file** (BE) and leave the host loads alone;
  then fix `RenderBucket_QueueExecute.c:1047` (`ReadPackedWord(&frame->pos.x)`) to a
  host load so the packed-word consumer stops disagreeing with `:2210`/`:5235`.
  Do NOT cook `ModelFrame.pos` — its primary consumers are the packed-LE ones.

### R3 — `mesh_info` scalars (`numQuadBlock`, `numVertex`, `numBspNodes`)
- **Blocking:** YES for any real track (entry 41: 1379/8593/907; the ND crate has 0).
  `MainInit.c:20` loops `bspIndex < mesh->numBspNodes` → a byte-swapped 907 is a
  ~2.3e9-iteration loop; `MainFrame.c:641` sizes a memcpy from `numQuadBlock`.
- **Risk: low.** `mesh_info` is reached from a map-listed pointer (`Level` frame 0), and
  the three fields are 4-byte scalars at fixed offsets that the map does **not** list
  (verified for entry 41: `0xC/0x10/0x1C` uncovered; `0x18` covered). Shape check:
  counts in `1..0x8000` (or `0` for the stub), `numBspNodes < 0x10000`.
  Include the `Level` scalars in the same pass where they are cheap:
  `configFlags` (0xDC, u32), `clearColorRGBA` (0xD8, u32) — both read with host loads in
  `MainFrame_RenderFrame.c:948-989` / `MainInit.c:562-569`.

### R4 — `BSP` node bodies (`flag`, `id`, `box`, `axis`, `childID`, leaf `numQuads`)
- **Blocking:** YES for real tracks — this is the entire visibility walk
  (`RenderLists_Walk1P2P`). Without it, `flag & BSP_LEAF_FLAG_WATER`, `childID`,
  `box` frustum tests and `numQuads` all read swapped.
- **Risk: medium.** The array is contiguous from `mesh_info.bspRoot`, length
  `numBspNodes` (cooked by R3), stride 0x20 — so the walk is easy, **but** the union at
  0x10 is *flag-dependent*: `flag` must be cooked FIRST to know whether 0x10..0x1F is
  `branch{axis[4],childID[4]}` or `leaf{unk1,hitboxArray,numQuads,ptrQuadBlockArray}` or
  `hitbox{center,radius,unk18,unk1A,instDef}`. Order matters. The `hitboxArray` and
  `ptrQuadBlockArray` words are map-listed (arbiter); the scalars are not.
  Validate: `flag` ∈ {0,1,2,8,0x10,0x20,0x80,0x82,…} (mask 0xFF83), `id` ascending,
  `box.min <= box.max` on all three axes, `numQuads <= 0x10000`.
  Note: the branch case has **no pointer words at all** (verified for entry 41 BSP[0..2]:
  `cov: axis words=[False×4] childID words=[False×4]`), so the cook is a pure
  fixed-layout scalar pass — low surprise.

### R5 — `QuadBlock` scalars + `LevVertex` scalar `flags`
- **Blocking:** YES for visible geometry, but *downstream* of R4 (the walk must find the
  leaves first). The pointer words (`ptr_texture_mid[4]`, `ptr_texture_low`, `pvs`) are
  already correct, which is why the 226 path can already *follow* textures.
- **Risk: medium-high** because the layout is big (0x5C) and interleaved with the
  pointer words; but the map arbiter resolves every 4-byte slot, and the pattern is
  already proven by `dram_instance_scalar_sites`. Offsets to cook (all uncovered):
  `0x00 index[9]` (**u16 ×9 — values, the same rule as the VRAM pixels**: they are used
  as array indices), `0x12 quadFlags`, `0x14 draw_order_low`, `0x18 draw_order_high`,
  `0x2C bbox` (6×s16), `0x38..0x3F` bytes, `0x3C blockID`, `0x48 triNormalVecDividend[10]`.
  **Watch out:** `index[]` is currently consumed by `game/226` as a host array index into
  the *uncooked* `LevVertex[]`, so both sides must flip together; and
  `DrawLevelOvr1P_ReadRetailQuadBlockByte` (`:577-590`) reads bytes of `draw_order_low`
  with a raw byte load, which will *stay* wrong until the *word* is cooked (its byte
  order changes with the cook). Validate `index[i] < numVertex` after cooking.

### R6 — `Level` remaining scalars (`numWaterVertices`, `numSCVert`, `glowGradient`,
`stars`, `splitLines`, `numSpawnType2*`, `cnt_restart_points`, `ptr_water`,
`ptr_tex_waterEnvMap`, `visOVertSrc`, `visSCVertSrc`, `ptrSCVert`)
- **Blocking:** only for water/SCVert levels and skybox gradients (entry 41 has
  `ptr_water=0`, `ptrSCVert=0`, `ptr_tex_waterEnvMap=0`, so inert there).
- **Risk: medium** — `ptr_water`/`ptrSCVert`/`ptr_tex_waterEnvMap`/`vis*Src` are
  **not map-listed** and hold non-zero values in water levels; a non-listed pointer that
  the loader never relocates must be treated as a *self-relative offset* (cook it as a
  4-byte value, exactly like the language-file ptr table) — but confirm per level with
  a value check (`< file size`, 4-aligned) before writing. This is the one pass where a
  wrong classification produces a wild pointer rather than a wrong number.

### R7 — `VisMem` body words (`visLeafList/visFaceList/visOVertList/visSCVertList/bspList[1..3]`)
- **Blocking:** NO for 1P (index `[0]` is map-listed and cooked; verified for entry 41).
  Only multi-player.
- **Risk: low** (36 words per level) but the payoff is also low. Do it when 2P+ is
  attempted.

### R8 — Vertex/anim frame byte payloads (the `ModelFrame` vertex blocks, delta streams)
- **Blocking:** NO — verified byte-wise consumers everywhere (`RenderBucketCompVertex`
  u8 reads, delta bit reads, `DrawLevelOvr1P` packed-word reads).
- **Action: explicitly do not cook.** Add to the R1 no-cook list.

### Explicitly NOT recommended
- Cooking `ModelHeader.ptrCommandList` bodies (§3.2).
- Cooking `TextureLayout` / `ptrColors` / `ptrDeltaArray` / `LevVertex` pos+colour
  bodies (all have explicit-LE consumers; cooking them would break the working paths).
- Cooking `ModelFrame.pos` (its packed-LE consumers are the majority).

---

## 7. What I could not determine

1. **Which of `RenderLists`' swapped reads is *currently* reachable.** For entry 514
   (`bspRoot == NULL`) the whole walk is dead, so R4/R5 cannot be runtime-verified
   until a real track loads. I verified the *offline* values (BSP flag/childID/box and
   quadblock fields are byte-identical retail↔cooked) but not a runtime symptom.
2. **Whether `mesh_info.numQuadBlock == 0` in entry 514 is authentic or a mis-parse.**
   The stub at `ptrQuadBlockArray == ptrVertexArray == 0x4a0` with
   `index[9] = (377,0,1240,0,44,44,44,44,0)` and `blockID = -301` looks like real
   (degenerate) data — `NDI_BOX_CODE`'s animtex being non-null there (HANDOFF §ANIMTEX)
   says the file is read correctly — but I did not confirm against an external
   CTR-tools parse.
3. **Whether `Level.ptr_water`/`ptrSCVert`/`ptr_tex_waterEnvMap`/`visOVertSrc`/
   `visSCVertSrc` are self-relative offsets or absolute PSX addresses** when non-zero.
   Entry 41 has all of them zero, so I had no sample. This decides whether R6 is a
   "cook as value" or a "cook as pointer" pass.
4. **The exact failure mode of the frame-13 OT walk.** The last packet
   (`826CFD0C`, `len=2`, `primLength=3`) suggests either a length/payload mismatch or an
   unregistered link; the parser's diagnostics go to `stderr`
   (`Platform_LogError` → `Platform_LogV(stderr, …)`), and `ctr360.log` contains **zero**
   `[CTR GPU]` lines — so either no error fired or the stream isn't captured. I could not
   tell which without a run (out of scope: no process launches allowed).
5. **`ModelHeader.unk1` (0x10) semantics.** No consumer found in `game/`; the cooker
   swaps it only when uncovered. If a later consumer reads it, the classification stands
   (host load ⇒ cook) but I cannot name the consumer.
6. **Whether `dram_model_header_scalar_sites`' `1..64` `numHeaders` bound rejects any
   live pack** (RESEARCH F5). I did not sweep all packs for a zero-header model.

---

## 8. Evidence appendix (commands run, read-only)

- Cooker read: `tools/ctr360/cook_disc.py` lines 1–1143 (all passes above).
- Retail vs cooked byte comparison: `tools/ctr360/_audit_cooked.py` →
  `_audit_cooked.out` (entries 514 and 41; every listed field, retail vs cooked hex).
- Command-list decode both ways: `tools/ctr360/_audit_cmdlist.py` (entry 514, all 20
  models; plausibility 100% LE vs 0–50% BE; 0 map-listed words inside any list).
- Mesh/BSP/PVS coverage: `tools/ctr360/_audit_mesh.py`, `_audit_bsp.py`.
- Scalars: `tools/ctr360/_audit_scalars.py`, `_audit_driverpack.py`
  (driver pack entry 259: `MA.numFrames=1500`, `frameSize=e400` uncooked).
- Level census: `tools/ctr360/_audit_levels.py` (48 level-shaped entries; 46 with real
  BSP trees, entry 514 and the two ending levels with degenerate/absent meshes).
- Runtime log: `F:/downloads/xenia_canary_windows/cache/ctr360.log` (Sep 19 10:12) —
  `w1 f=13 bsp=00000000`, `lg4 f=13 leafs=0`, `DrawOTag#23` wedge at
  `walk#23 pkt=826CFD0C len=2 code=00`.
- `_audit_*.py` files are scratch helpers; delete them if you want the tools dir clean.

_— end of data_coverage_matrix.md —_
