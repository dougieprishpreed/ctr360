# Session 6: per-instance projection — the GTE register half-word endianness bug

Status: root cause found, fix applied to both trees, host-verified in both register
layouts; 360 re-verification run in progress (see §5 for what to look for).

## 1. Symptom recap

The menu/title screen never drew its 3D instances. `qd4` showed every instance's
per-instance mvp collapsing to `(x, 0, 0, 0, 0)` — only the x column of the m3x3
survived — so `bdz` (the depth reject in `RenderBucket_AcceptProjectedBounds`)
rejected every instance with `maxZ = 0 < geomScreenHalf`.

Two facts pinned it down to the scale/multiply chain and not the data:

* the x column was *correct*: for the title models it equalled `5 * mh->scale.x`
  (`introcrash`: `m3 = 0x5078 = 5 * 0x1018`), and for the copyright-screen
  instances (`entry 514` `ndi_box_*`) it equalled their `mh->scale.x` verbatim
  (`0x1914` for `ndi_box_oxide`, `0x22c4` for `ndi_box_code`);
* the y/z columns were zero for **every** instance, including ones whose
  `mh->scale.y/.z` (read little-endian) are clearly non-zero
  (`ndi_box_oxide`: `0x40e6`, `0x34b5`).

So the loss was in the code, not the cooked data.

## 2. Root cause: `PAIR.sw.l` / `.sw.h` are memory-order, not value-order

`include/psx/gtereg.h` defines the GTE register union:

```c
typedef union
{
	struct { unsigned char l, h, h2, h3; } b;
	struct { unsigned short  l, h;        } w;
	struct { char            l, h, h2, h3; } sb;
	struct { short           l, h;        } sw;
	unsigned int d;
	int sd;
} PAIR;
```

The member names follow the PSX convention: `.l` = the **low half-word of the
register value**, `.h` = the high half, `.b.l` = value byte 0 (least
significant). On the PSX (and any little-endian host) that is also the memory
order, so the ascending declaration is right. On the big-endian Xbox 360 the
first member is the *most* significant bytes, so `.sw.l` reads the **high**
half of `d` and `.sw.h` the low one — every mixed-width GTE access is swapped:

* `CTC2` writes a matrix word into `CP2C.p[r].d`; the core then reads the
  elements back as `.sw.l` / `.sw.h` (`MX11`..`MX33`, `C2_LR1/LR2`, `C2_R11/R12`),
  so matrix element pairs (11,12), (21,22), (31,32) swap on the 360;
* `MTC2` packs a vector into `CP2D.p[r].d`; `VX(n)/VY(n)` then read `.sw.l` /
  `.sw.h`, so **VX and VY swap** and `VZ` (the low half of `p[1].d`) reads as 0;
* `MFC2(9/10/11)` reads `.sw.l` of the IR registers — self-consistent with the
  core's `C2_IRn` writes, which is why the x column still came out right.

Worked example for the title instance (`inst` diag 0x5000, `mh->scale` =
`0x1018/0x0b3b/0x06c9`), `BuildM3x3` → `lcv0` (opcode `0x04c6012`, which is
MVMVA with `cv=2` — the real hardware's "buggy" path that drops the
`T<<12 + M(i,0)*Vx` terms, faithfully reproduced by the port's `case 2` and by
DuckStation's `MulMatVecBuggy`):

| term | 360 (pre-fix) | expected |
| --- | --- | --- |
| `IR1 = MX12*VY + MX13*VZ` | `MX12 = 0x1018` (low half), `VY = 0x1000` | `0x1018` ✔ |
| `IR2 = MX22*VY + MX23*VZ` | `MX22 = 0` (high half of `sy`), `VZ = 0` | `0x0b3b` ✘ |
| `IR3 = MX32*VY + MX33*VZ` | `MX32 = 0`, `MX33 = 0` (high half of `sz`) | `0x06c9` ✘ |

which is exactly the observed `b3s sc=00001018,00000000,00000000` and
`m3=00005078,00000000,00000000,00000000,00000000`.

## 3. Fix

`include/psx/gtereg.h` (both trees) now declares the `PAIR` members in reverse
memory order when `CTR_GTE_BIG_ENDIAN` is set, so `.l/.h/.b.*` stay
value-relative on both targets:

```c
#ifndef CTR_GTE_BIG_ENDIAN
#if defined(_XBOX) || defined(_M_PPC) || defined(__PPC__) || defined(__ppc__) \
 || defined(__BIG_ENDIAN__) || defined(_BIG_ENDIAN)
#define CTR_GTE_BIG_ENDIAN 1
#else
#define CTR_GTE_BIG_ENDIAN 0
#endif
#endif
```

`_XBOX` is already in the vcxproj's preprocessor definitions, so the 360 build
takes the reversed declaration; nothing else in the tree touches `PAIR` members
(`native_gte_core.c`, `native_inline_c.c`, `gtereg.h` only), so the fix is
contained.

## 4. Host unit test (`tools/ctr360/gte_mul_test.c`, `run_gte_unit_test.sh`)

The test drives the **real** scalar GTE and the real matrix helpers
(`MATRIX_SET_r11r12r13r14r15`, `Unknown_8006c49c/558/600`) with the register
choreography of `RenderBucket_BuildM3x3` and `RenderBucket_BuildMvp`, and is
compiled twice:

* `CTR_GTE_BIG_ENDIAN=0` — the fixed/PSX layout: full assertions, e.g.
  `m3x3 = (0x5078, 0x3827, 0x21ed)` and
  `mvp = viewProj x diag(m3x3)` = `1c135078 0a0f087b 043d3827 03820507 000021ed`;
* `CTR_GTE_BIG_ENDIAN=1` — on a little-endian host this emulates the pre-fix 360
  layout, and the test asserts the **symptom** (x survives, y/z drop to 0), i.e.
  the same shape the guest produced. This is the regression guard: the two runs
  must disagree in exactly that way.

Helper semantics confirmed by the test: `BuildMvp` computes
`mvp = matrix_ViewProj x m3x3` (columns of the viewProj scaled by the m3x3
diagonal), `BuildM3x3` produces the full diagonal
`diag(5*mh.scale.x, 5*mh.scale.y, 5*mh.scale.z)` for a diag(0x5000) instance.

## 5. What the next 360 run must show (f>=500, i.e. after `title-init`)

* `b3s f=... mid=103 sc=00001018,00000b3b,000006c9 m3=00005078,00003827,000021ed`
  — the lcv0 triple and the m3x3 diagonal complete;
* `qd4 m=...` with non-zero words 2/4 and `mvp` likewise;
* `bdz` rejects for the title instances gone (or at least `maxZ` no longer 0),
  `pk` bounds sensible;
* the GPU command walk gaining 3D prims for the title frames (the pre-fix log
  only had the 2D `pack`/`pvr` quads: `verts=6`/`verts=12` counts of 49/16).

## 6. Cooker changes this session

* **`ModelHeader.scale` is no longer byte-swapped** (removed `0x18/0x1A/0x1C/0x1E`
  from the three model-header scalar lists). The reader
  (`RenderBucket_BuildM3x3` → `RenderBucket_ReadPackedWord`) is little-endian, so
  the cooked image must keep the retail LE bytes; the previous swap fed the
  scale path `0x1810/0x3b0b/0xc906` instead of `0x1018/0x0b3b/0x06c9`.
* **New `dram_spawntype1_sites` pass**: cooks the level's `SpawnType1.count`
  (host-read by `MM_Title_Init`'s `count > 2` gate and every spawner) and, for
  the main menu entry (216), the title camera path `ST1_CAMERA_PATH` frames
  0..230 (`MM_Title_CameraMove` reads them as host `s16`s).
  Verified in the guest: `title-init st1=4` (was `0x04000000`) and
  `tcp p=0,128,960 r=2168,0,0` (was `p=0,-32768,-16381 r=30728,0,0`).

## 7. Byte-order discipline (verified conventions + prior art)

The port mixes two standard strategies, and every bug in this session was a
place where a *reader* and its *writer* disagreed about which one applies.

Prior art (researched this session):

* **Source engine's `studiobyteswap.cpp`** — the canonical Xbox 360 approach:
  convert file formats to big-endian **at build time** so the console can use
  native loads. That is what `tools/ctr360/cook_disc.py` does.
* **WiiSX / PCSX-Revolution (`psxmem.h`)** — a PSX emulator on a big-endian PPC
  console: guest memory stays **raw little-endian** and every access goes
  through a swapping accessor (`SWAP16/32`, with `lhbrx`/`lwbrx`/`stwbrx`
  asm). That is what `CTR_Read*LE`/`RenderBucket_ReadPackedWord` do per site.
* **XenonRecomp README** — "the instruction implementations operate on
  little-endian values; since the 360 is big-endian, the memory load
  instructions swap endianness". Logical values are LE; memory order is BE.
* **PPC byte-reversed loads** (`lwbrx`/`lhbrx`/`stwbrx`) exist precisely to
  read LE data efficiently; the 360 XDK exposes them (the port currently uses
  byte-wise reads, which is correct but ~4x the instructions — an optimization
  lever, not a correctness one).

Conventions that hold in **this** tree (each verified from code, not assumed):

1. **Disc data is cooked to BE** for anything read with a host load
   (`mh->flags`, `numAnimations`, ModelAnim frames, command words, level
   scalars, InstDef scalars, `SpawnType1.count`, the camera path, …).
2. **Pointer-map words and their slots are handled by the loader**
   (`LOAD_RunPtrMap`: `*(int *)&origin[offset] = *(int *)&origin[offset] +
   (int)origin`) — i.e. the *slot* is read and written in **host order**, so
   after loading every map-covered pointer slot holds a **host-order (BE)**
   guest pointer. Anything that reads such a slot with an LE accessor is
   wrong on the 360. `LevInstDef_Peer` was exactly that (fixed this session:
   plain host-order read).
3. **PSX-packed conventions stay LE**: `RenderBucket_ReadPackedWord`,
   `RenderBucket_ReadMatrixWord`, `DrawLevelOvr1P_ReadPackedWord`,
   `CTR_Read*LE`, the GTE's register half-word views (`PAIR`, now
   endianness-aware), and `ModelHeader.scale`.
4. **Runtime pointers** (game-allocated instances/threads/particles in the
   mempack) are plain host-order C pointers everywhere.

So when a value looks byte-swapped, first ask which of 1-4 the *reader*
assumes, then make the writer agree — do not "fix" the data.

## 8. Open items after session 6

* **f=205 wedge — ROOT CAUSE FOUND AND FIXED (session 7)**:
  `RenderBucket_QueueDraw`'s `RB_INSTANCE_SKIP_OT_RANGE` path stores a *halfword*
  into `idpp->otRangeSecondary` (`idpp->otRangeSecondary = (u16)pb->rect.h;`).
  In retail that is a `sh` (store-halfword): the high half keeps the previous OT
  range's high bits, so the resulting "range" stays inside the OT pool. As a
  plain 32-bit C store in this port it instead preserved the *uninitialised
  arena poison* in the high half — `qw` shows `rs=80008000` for the drawn
  instance at f=204 — and the draw's OT link write
  (`RenderBucket_LinkPrimRaw`: `*otEntry = RenderBucket_OTAddress(prim)`) then
  lands at wild addresses. `lp` caught those writes: entries scattered across
  the model pack (`0x8270xxxx`) and the instance pool (`0x826fxxxx`) with
  garbage old values, instead of the `0x826eae04..0x826ece00` OT pool.
  One of them hit the Jit `taken` list head's `next` (a prim link word
  `0x00ef0458`), so the f=205 walk followed a wild pointer and wedged.
  Fix: keep the high half from the instance's real primary range —
  `idpp->otRangeSecondary = ((u32)idpp->otRangeNormal & 0xffff0000) | (u16)pb->rect.h;`
  (repo + tree, both updated). *This hardening is correct but was not the cure.*
  The decisive datum is the `or` probe at `RenderBucket_DrawInstPrim_NormalAtRange`:
  the range is sane (`r=826e90b0`), but the depth is a wild 32-bit value
  (`d=626ce401, be01e401, 780ce301, f5e6e501 …`) whose **low byte always equals
  the prim command's low byte** (`cmd=a8570201 → d=…01`, `cmd=a8570402 → d=…02`,
  `cmd=…0203 → d=…03`). The depth comes from
  `gte_stopz(&depthMac0)` = `MFC2(24)` — GTE register 24 (MAC0/OTZ) — so the
  native GTE's reg-24 slot holds `[24 varying high bits | the command byte]`.
  `(depth >> 17)` is then ~0x3000-0x5F00 instead of 0..~0x80, and
  `GetNormalOTEntry` (which deliberately does not clamp) adds that bin to the
  range, sending the OT link writes to `0x8270xxxx`/`0x826fxxxx`.
  **ROOT CAUSE (session 7, `mf` probe)**: `mf f=204 cmd=88570205 mfc=01e78c30
  loc=308ce701` — the local is the MFC2 value **byte-reversed**. The `gte_st*`
  family in `include/psx/inline_c.h` stores through `CTR_WriteU32LE` (byte-wise
  little-endian), but its destinations are the port's own C locals/structs,
  which are HOST order. On the big-endian 360 every `gte_stopz`/`gte_stsz`/
  `gte_stsxy…`/`gte_Read*Matrix` output was therefore byte-swapped; the
  `depthMac0` fed `GetNormalOTEntry` a garbage bin and the OT link writes went
  wild. Fix: a `CTR_STORE_U32` host-order store for the whole `gte_st*` family
  (all 55 sites, repo + tree). The `gte_ld*` family keeps `CTR_ReadU32LE`
  because its sources are the cooked little-endian level data; the GPU walker
  reads prim fields (`poly->x0` …) as plain native C fields, so native stores
  are the correct convention on the write side too.
  **Next step**: confirm the wedge is gone past f=205 in the guest log, then the
  title draw (f>=500) and the demo race.
  **Convention map verified while fixing this** (important for future work):
  * The prim/GPU path uses the port's own `CTR_GteStoreU32` (byte-wise LE) via
    `CTR_GteStoreSXY3` — the `gte_stsxy*`/`gte_strgb*`/`gte_stlvl`/`gte_sttr`/
    `gte_stfc`/`gte_stdp`/`gte_Read*Matrix` macros have **zero callers** in the
    game code, so the `gte_st*` native-store change only affects the scalar
    locals it must affect (`gte_stopz` ×4, `gte_stsz` ×15, `gte_stflg` ×2).
  * The GPU walker reads prim fields the LE way (`uv0[0]`/`uv0[1]` bytes,
    16-bit VERTTYPE halves), so the LE prim layout stays as it was — no
    regression from the fix.
  * `gte_ld*` keeps `CTR_ReadU32LE`: its sources are cooked LE level data.
  Probe trail: `pi`/`pz` (pool stride vs walk) → `cb1`/`cb2` (setup callback
  clean) → `d1..d4` (d3 clean, d4 clobbered ⇒ inside
  `RenderBucket_DispatchDrawInstPrim`) → `qw` (queue-side ranges) → `lp` (the
  wild OT writes) → `or` (the depth value) → `gte_stopz`/`MFC2(24)` → `mf`
  (the byte reversal).
  This is the same *half-word* bug class as the GTE `PAIR` bug fixed earlier
  this session: **a value's halves are not interchangeable across a big-endian
  port**.
* The crate scene has no PVS lists (`cDC->visInstSrc == 0`), so its instances
  come from the Jit `taken` list; `LevInstDef_UnPack/RePack` only matter for
  levels with InstDefs (real tracks) — the peer fix is still required there.
* Title draw verification (f>=500) and the demo race remain.
