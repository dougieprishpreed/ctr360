# ctr360 RESEARCH.md — audit findings, corrections, and direction for the next agent

_2026-09-19. Produced by a review pass over HANDOFF.md, the skill references
(`game-decompilation-porting`: console-port-debug-loop, endianness-cooker), the
cooker source (`tools/ctr360/cook_disc.py`), the mirror generator's probe lists
(`tools/ctr360/build_360_mirror.py`), the game headers (`include/namespace_Level.h`,
`include/namespace_Instance.h`, `game/CTR/CTR_CycleTex.c`), the last runtime log
(`F:/downloads/xenia_canary_windows/cache/ctr360.log`, Sep 19 07:50 run) and
`xenia.log`. Everything below is evidence-backed; claims are tied to the log line,
source line, or struct definition that proves them._

---

## 0. TL;DR for the continuing agent

The HANDOFF end-state is accurate, but **the designed animtex fix contains a
stride bug that would make the cooker patch the WRONG bytes** (proof in §2).
Apply the corrected fix in §3 (drop-in), wire it into the right three functions
(§4), ALSO cover the level's own animtex chain that `CTR_CycleTex_LEV` walks (§5),
then run the loop in §6. After that, expect the mesh/vertex frontier — it is
likely ON the critical path to a *visible* title screen, not optional cleanup (§7).

---

## 1. Verified state on disk (re-checked, matches HANDOFF)

- `cook_disc.py` (45,806 B, Sep 18 23:12) does **NOT** contain
  `_animtex_chain_sites` — only a docstring mention (line 705). The animtex fix
  is still unapplied. ✓ matches HANDOFF.
- `build-360/ctr-u-360.bin` (Sep 18 23:55) was cooked with the pre-animtex
  cooker, staged via `prep_test.sh --cooked`. ✓
- `build-360/xex/dist/default.xex` (Sep 18 23:49) built with all probes incl.
  the null-deref guards. ✓
- Last run (log mtime Sep 19 07:50): boot reaches mainGameState=3, frame 13,
  cy1 (driver pack, `mpk=827049e0`) walks all 20 models + terminator cleanly
  (final `s2 ... w=00000000`, then `g1 f=13`), cy2 (level array `arr=82715f6c`)
  reaches the first non-NULL animtex on `ndi_box_code`
  (`c1 ... hdr=827413f4 atx=82741bb8`), then
  `c2 cur=82741bb8 link=827417f8 nf=4096 fo=0 fs=0 fc=1` →
  `c2 cur=82745bc4 link=a6298b80 nf=296 ...` — the chain walk leaves the data
  and wedges. Audio pump continues (blocked, not spinning). ✓ exactly the
  HANDOFF's ANIMTEX FRONTIER section.
- The off-by-4 model-list fix (`while off in frame:`) is present in all three
  scans (`cook_disc.py` lines 590, 723, 847). ✓
- `ModelHeader` stride 0x40 and the per-header scalar site list
  `(0x10,4)(0x14,2)(0x16,2)(0x18,2)(0x1A,2)(0x1C,2)(0x1E,2)(0x30,4)(0x34,4)`
  in the cooker match `struct ModelHeader` in `include/namespace_Instance.h`
  (0x0 name[0x10], 0x10 unk1, 0x14 maxDistanceLOD, 0x16 flags, 0x18 scale,
  0x20 ptrCommandList, 0x24 ptrFrameData, 0x28 ptrTexLayout, 0x2C ptrColors,
  0x30 unk3, 0x34 numAnimations, 0x38 ptrAnimations, 0x3C animtex). ✓
- Git: `platform/native_gpu.c`, `platform/native_libgpu.c`,
  `include/platform/native_renderer.h` modified-uncommitted; `platform/xbox360/`,
  `tools/ctr360/`, `HANDOFF.md` entirely untracked. See §8-R4.

---

## 2. CRITICAL: the HANDOFF's designed animtex stride is wrong (0x10 → 0xC)

The HANDOFF's fix sketch walks the chain with:

```
nxt = cur + 0x10 + nf*4        # WRONG
```

**Proof it must be `0xC`:**

1. `struct AnimTex` (`include/namespace_Level.h:129`) is
   `int* (4) + s16×4 (8) = 12 = 0xC` bytes. Alignment 4; 12 is already
   4-aligned, so the XDK compiler emits `sizeof(struct AnimTex) == 0xC`.
   `ANIMTEX_GETARRAY(x)` is `x + sizeof(struct AnimTex)`, and the game steps
   `curAnimTex = &ptrArray[numFrames]` (`game/CTR/CTR_CycleTex.c:61`), i.e.
   `next = cur + 0xC + nf*4`.
2. The runtime log proves the COMPILED stride directly: the stall run shows
   `c2 cur=82741bb8 nf=4096` → `c2 cur=82745bc4`, delta = **0x400C**
   = `0xC + 4096*4`. If sizeof were 0x10 the delta would have been 0x4010.

Why the bug is nasty: with stride 0x10 every chain step after the first lands
+4 bytes past the real next entry, so `numFrames/frameOffset/frameSkip` sites
get computed from misaligned words — the cooker would swap **wrong bytes**
while every verification gate still PASSES (each site is an involution, so
round-trip is blind to a wrongly *declared* site; the no-overlap gate only
fires if two wrong sites collide, which they won't — they're 4 apart). The
sentinel test (`word0(next) == first entry`) would also misfire. Result: a
"successfully cooked" image that changes nothing at runtime, costing a full
cook+stage+run cycle and looking like "the fix didn't help".

The HANDOFF's *field* sites are correct — only the stride is wrong:
- word0 `ptrActiveTex` (+0x0): map-relocated pointer, DO NOT cook ✓
- `numFrames` (+0x4), `frameOffset` (+0x6), `frameSkip` (+0x8): cook as s16 ✓
- `frameCurr` (+0xA): runtime state, correctly excluded ✓
- termination: the loop (`CTR_CycleTex.c:40`) exits when an entry's word0
  equals the FIRST entry's address — in file data the sentinel entry stores
  the first entry's frame-relative offset. ✓ (HANDOFF had this right.)

---

## 3. Corrected drop-in fix for `tools/ctr360/cook_disc.py`

```python
def _animtex_chain_sites(base, n, hfile, seen, extra):
    """Cook the AnimTex chain hanging off a ModelHeader (hfile = FILE coords
    of that header). All stored values are frame-relative; file = frame + 4.
    Stride is sizeof(struct AnimTex) = 0xC (NOT 0x10 - proven by the runtime
    c2 delta 0x400C in the Sep 19 stall run), then numFrames pointer words."""
    atx = struct.unpack_from('<I', base, hfile + 0x3C)[0]
    if atx == 0 or (atx % 4) or (4 + atx + 0xC) > n:
        return
    cur = atx                                   # frame coords
    for _ in range(64):
        if cur in seen or (4 + cur + 0xC) > n:
            return
        nf = struct.unpack_from('<h', base, 4 + cur + 4)[0]
        if not (1 <= nf <= 64):
            return
        seen.add(cur)
        extra.append((4 + cur + 4, 2))          # numFrames
        extra.append((4 + cur + 6, 2))          # frameOffset
        extra.append((4 + cur + 8, 2))          # frameSkip
        nxt = cur + 0xC + nf * 4                 # frame coords
        if (4 + nxt + 4) > n:
            return
        if struct.unpack_from('<I', base, 4 + nxt)[0] == atx:
            return                              # sentinel entry: game stops here too
        cur = nxt
```

Bounds-check `nxt` BEFORE reading the sentinel word, and note the sentinel
read is at **file** offset `4 + nxt` (the HANDOFF sketch wrote `u32 at (nxt)`,
ambiguous about the +4 file-header shift — same frame/file trap the skill
flags; every offset here needs the `4 +`).

Verification after cooking (do this BEFORE staging): walk the same chain on
the cooked image and assert every `numFrames` reads 1..64 big-endian, and the
`ndi_box_code` chain (entry 514) reads `nf=16` at its first entry. A tiny
`--check`-mode addition or a standalone inspect script is fine.

---

## 4. Wiring correction: the three functions with header loops (NOT `dram_pack_scalar_sites`)

The HANDOFF says "wire into all three model passes … dram_pack_scalar_sites /
dram_level_model_sites / dram_model_array_sites". **`dram_pack_scalar_sites`
has no ModelHeader loop** — for pack entries the per-header cook runs in
`dram_model_header_scalar_sites`. The three functions that contain the header
loop ending in `extra.append((hfile + f, sz))` are:

- `dram_model_array_sites` (line ~746) — map-only model arrays
- `dram_level_model_sites` (line ~813) — level-embedded models
- `dram_model_header_scalar_sites` (line ~876) — pack models

Wire `_animtex_chain_sites(...)` in each, immediately after the
`extra.append((hfile + f, sz))` line inside the `for h in range(num_headers)`
loop, each pass with its OWN `seen = set()` created next to its `extra = []`.

Coverage safety (verified against `cook()`'s dispatch): per entry exactly ONE
of these passes runs (pack branch → model_header pass; level branch →
level_model pass; else → model_array pass), so two passes cannot double-cook
the same chain within one file. The merged-site overlap check in `cook()`
(lines 994–1002) remains the backstop and will `SystemExit` loudly on any
mistake — keep it.

One edge to note while you're in there: `dram_model_header_scalar_sites`
requires `1 <= numHeaders <= 64` while the other two passes allow
`numHeaders == 0`. A single zero-header model in a pack currently rejects the
WHOLE pack's header cook (returns None). If a pack ever fails detection,
check that first.

---

## 5. Coverage gap the HANDOFF missed: the level's own AnimTex chain

`CTR_CycleTex` has TWO walkers with the same chain shape:

- `CTR_CycleTex_Model` — chains hang off `ModelHeader.animtex` (what the
  designed fix covers).
- **`CTR_CycleTex_LEV`** — chains hang off **`struct Level.ptr_anim_tex`**
  (frame word 8 — already validated map-covered by `dram_level_scalar_sites`,
  `cook_disc.py` docstring line 613: `8 ptr_anim_tex`). `functions.h:51`
  declares it; grep the game sources for its call site (likely a per-frame
  level-texture cycle: waterfalls, banners, animated trackside textures).

When the level branch of `cook()` detects a level, ALSO walk the chain at
`ptr_anim_tex` with the same `_animtex_chain_sites` logic (read the frame
word at `4 + 8`, feed it to the same walker, fresh `seen` set). If you don't,
the model fix will clear the frame-13 stall and the very next consumer of the
same uncooked `numFrames` class — `CTR_CycleTex_LEV` — stalls identically,
costing a cycle. This is the "cook the class, not the consumer that died"
rule: AnimTex chains are one class with two roots in level files
(`ModelHeader.animtex` AND `Level.ptr_anim_tex`).

Also check `struct Instance.animtex` (`include/namespace_Instance.h:396`) —
runtime instances point back at file AnimTex data; cooking the file entries
covers those bytes either way, but confirm no OTHER AnimTex root exists:
`grep -rn "animtex" game/ include/` before deciding the class is closed.

---

## 6. Next-run protocol (single next action, corrected)

```bash
cd /f/downloads/temp/python/hermes/ctrport/ctr360

# 1. Apply §3+§4 (+§5) to cook_disc.py — targeted edits, count-asserted.
# 2. Validate + cook:
python tools/ctr360/cook_disc.py --check          # must pass, no writes
python tools/ctr360/cook_disc.py --out build-360/ctr-u-360.bin
#    then verify animtex numFrames (all 1..64 BE; entry 514 ndi_box_code nf=16).

# 3. Stage + ASSERT staged identity (R3 below):
bash tools/ctr360/prep_test.sh --cooked build-360/ctr-u-360.bin
md5sum build-360/ctr-u-360.bin build-360/xex/dist/assets/ctr-u.bin   # must match

# 4. Run (XEX unchanged → no rebuild needed; if you DID touch sources,
#    regen/finalize/build first and trust build_xex.sh's FATAL gate):
bash tools/ctr360/run_xenia.sh 300
```

Expected signatures in the log if the fix works:
- `c2 ... nf=16 fo=... fs=...` at `cur=82741bb8` (cooked value), then the walk
  steps `cur + 0xC + 64` and TERMINATES on the sentinel (a final `c2`-adjacent
  line or the next probe firing).
- `g2 f=13` (`gl: cyc2 done`) fires, then the frame advances past 13.
- The next stall (if any) is localized by the `g3..g9` probes.

**Raise/adjust probe caps before the run — they will exhaust in ~1.5 frames
otherwise.** Measured from the stall run: `c0`/`c1` fire ~20 lines per cycle
call and BOTH cycle calls run every frame (cy1 = PLYROBJECTLIST walk, cy2 =
level walk), so caps of 60 are dead by frame ~14–15, and `g1` (cap 12) dies
at the 12th frame. Post-fix you want: caps raised to cover the first N frames
of interest (e.g. first-20-frames by `{ static int n; if (sdata->frameCounter
< 40 && n < X) ... }` — count-capped AND frame-windowed), and keep the
uncapped `frame %d presented` heartbeat as the liveness sampler. Remember
cy1 is called with `numModels = -1` (u32) so its countdown can NEVER reach
zero — it terminates only on the NULL terminator; every model in
PLYROBJECTLIST must stay cooked or you get exactly this class of stall again.

No rebuild is needed for the cook-only change (XEX is untouched); that is
the cheap path — do NOT regen for a data fix.

---

## 7. Open items, ranked (what I could NOT fully resolve in this pass)

**F1 — Mesh/vertex data is likely ON the critical path to a VISIBLE title
screen.** The boot reaches the ND-crate cutscene level (level 41). What the
user SEES from here depends on `struct Level.ptr_mesh_info` (frame word 0,
map-covered pointer, uncooked body), the quadblock/vertex/BSP command lists
(`include/namespace_Level.h`), and the PVS arrays (`visLeafSrc/visFaceSrc/
visInstSrc/visExtraSrc`). NO pass cooks any of that today. Even after the
animtex fix produces clean frame advance, the screen may stay black/garbage
until mesh scalars, vertex words, and texture-layout indices are cooked —
and the user is the visual judge, so "frames present" ≠ progress visible.
Approach it exactly like the model passes: find the first mesh consumer that
dies (the g-probes / a RenderLayout breadcrumb), read ITS struct, cook with
the pointer map as arbiter for 4-byte slots, validate offline first. Expect
s16 vertex/SCVert/OVert fields and quadblock command indices; PSX mesh
vertices are numeric words, not opaque bytes — same u16-VALUE rule as the
.vrm pixels.

**F2 — Xenia backend draw failures: `Surface pitch 9552 larger than the
maximum texture width 8192 specified by the guest` + `PM4_DRAW_INDX(6, 4,
2): Failed in backend`, 38× in the stall run, interleaved with per-frame
probe writes (e.g. right after `[trace] frame: post-ClearOTagR f=2`).**
6 verts / 4 indices = a fullscreen quad, i.e. one of OUR draws (present or
offscreen/Resolve pass) binds a surface Xenia considers 9552-pitch. 9552
matches neither the VRAM RT (1024-wide G8R8) nor the 1280×720 backbuffer.
Next step when you pick this up: find the FIRST occurrence (xenia.log line
~3922) and read BACKWARD for the texture-creation call that produced the
9552-pitch surface, then map it to the CreateTexture/Resolve call in
`platform/xbox360/native_xbox360_video.c`. It fires per-frame, so it may be
harmless to boot but fatal to actual level rendering — do not let it wait
past the first gameplay draw.

**F3 — Staging identity is asserted nowhere in the loop.** `prep_test.sh`
with a missing/typo'd `--cooked` flag silently stages the RAW retail dump and
the next run "regresses" in a way indistinguishable from a bad cook (the
skill documents this exact trap). Add the md5 comparison (§6 step 3) to
`run_xenia.sh` or make `prep_test.sh --cooked` echo the md5 it staged.

**F4 — Commit the work.** The probe infrastructure (`tools/ctr360/`), the
entire `platform/xbox360/` backend, and three modified `platform/` files are
uncommitted/untracked. One careless `git clean` or a bad regen loses the
project's tooling memory. Suggested: `git add tools/ctr360 platform/xbox360
platform/native_gpu.c platform/native_libgpu.c include/platform/native_renderer.h
HANDOFF.md RESEARCH.md && git commit`. (User prefers clean trees with
research artifacts preserved — committing them IS the preservation.)

**F5 — Model pack `numHeaders==0` edge** (§4 tail): unequal bounds between
`dram_model_header_scalar_sites` (1..64) and the other passes (0..64) can
silently reject a valid pack. Low priority; note for detector failures.

**F6 — Audio**: still unverifiable under Xenia (XTL sink isn't a sound
device); the pump heartbeat (callbacks/queuedBytes) proves the clock thread
lives, nothing more. Console is the test. Do not claim audio results.

---

## 8. What is WORKING and should not be re-litigated (audit result)

- The endianness-cook architecture itself: same-length in-place, map-as-
  arbiter, round-trip + overlap + confinement gates, staged by boot order.
  Every pass I read (`dram_swap_sites`, `dram_pack_scalar_sites`,
  `dram_level_scalar_sites`, `dram_instance_scalar_sites`,
  `dram_model_array_sites`, `dram_level_model_sites`,
  `dram_model_header_scalar_sites`, `vram_swap_sites`) correctly separates
  file coords (`4 + frame`) from frame coords and skips map-covered words.
  The frame/file discipline in `cook_disc.py` is sound.
- The build-freshness gates in `build_xex.sh` (FATAL on `: error`, exe-vs-
  mirror mtime) — trust them; do not run anything if FATAL prints.
- The probe discipline (count-capped, guarded derefs, repo-resident via
  `add_boot_stall_probes.py` / BOOT_TRACE / HEADER_PATCHES) — sound.
- Display chain is verified to the copyright page (user-confirmed); the
  present-path constant collision fix (vs c0/c1) stands.
- `run_xenia.sh [secs] [pattern]` already implements the self-driven loop
  with a CPU sample — prefer it over the inline HANDOFF §2.1F command.

## 9. False assumptions / corrections found in the HANDOFF (summary)

| # | HANDOFF claim | Correction | Evidence |
|---|---|---|---|
| 1 | AnimTex next entry at `cur + 0x10 + nf*4` | `cur + 0xC + nf*4` | c2 log delta 0x400C; `sizeof(struct AnimTex)=0xC`; `CTR_CycleTex.c:61` + `ANIMTEX_GETARRAY` |
| 2 | Wire animtex walk into `dram_pack_scalar_sites` | It has no header loop; wire into `dram_model_header_scalar_sites` (+ the other two header-loop passes) | `cook_disc.py` lines 543–606 vs 821–884 |
| 3 | (implicit) model-header wiring covers all AnimTex | `CTR_CycleTex_LEV` walks `Level.ptr_anim_tex` — a second root of the same class, uncooked | `cook_disc.py` docstring line 613; `functions.h:51` |
| 4 | "probe caps may need raising" | They WILL exhaust: c0/c1 fire ~40/frame once running; g1 cap 12 dies at frame 12 | stall-run log line counts |
| 5 | mesh cook = "suspected NEXT class, unverified" | Treat as expected frontier BEFORE a visible title screen: the ND-crate cutscene level must DRAW | boot path reaches level 41 rendering |

— end of RESEARCH.md —
