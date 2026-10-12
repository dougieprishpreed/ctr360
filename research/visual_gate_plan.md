# The visual gate: why the screen stays on the copyright page

_Session 7b, after external review (Claude / GLM / Grok) of the session-6/7
transcript. This supersedes the "title reached" framing: the guest **state**
advances to the title (title-init, title-menu intro=210, tcp camera path), but
**pixels never change** — the framebuffer keeps the last 2D page (copyright).

## Verified state (log + offline evidence)

* `rbe ents=120 ok=0 disp=0 ... drop=0,0,0,0,120,...` at the title frames —
  **every** queued instance is dropped by the cull. `ents=49 ok=19` at one
  crate frame shows the path can accept, but the title frames are all-culled.
* `bdz f=... maxZ=0 half=128 minZ=0` and `bdy f=... maxY=-1024` — the projected
  bounds are degenerate, so `RenderBucket_AcceptProjectedBounds` rejects.
* `pj f=575 sxy=03ff00df sz=3118` with `pk x=222..930 y=878..1023` — the
  projected screen bounds are off-screen (y saturated at 1023).
* The camera side is healthy (`sm` rot values sane, `matrix_ViewProj` m[][]
  words consistent with the LE convention).

## Root cause found this session (fixed, verifying)

`CTR_GteStoreMAC` stored MAC1/2/3 into `pb->matrix_ViewProj.t[]` /
`matrix_CameraTranspose.t[]` with **host-order** C assignments, while the
readers of those fields are little-endian:

* `gte_SetTransMatrix(projectionMvp)` in the cull path reads t[] via
  `CTR_ReadU32LE` — so the **view-projection's Y translation was byte-swapped
  every frame** → every instance's projected bounds garbage → all culled.
* `PushBuffer_SetMatrixVP`'s aspect scale on `t[1]` reads/writes LE too — the
  `sm` probe shows exactly this: `t=-2,<wild>,423` (t[0]/t[2] sane under the
  host-order store, t[1] wild because the LE round-trip corrupted it).

Fix: `CTR_GteStoreMAC` stores through `CTR_GteStoreU32` (byte-wise LE), like
the PSX `sw` it replaces. Repo + tree.

Ruled out by offline check (both images identical at the model-header scale
bytes `18 10 3b 0b c9 06`): the cooked model scale is fine; the LE read gives
the plausible all-positive scale (1.006, 0.703, 0.424) while the BE read gives
a negative z. The `mhs` probe's "scH" (plain read) was a **probe artifact**,
not a data bug.

## Ranked hypotheses still open (each with its test)

1. **Prim SXY store/read convention** (Claude's suspect). The 3D path stores
   SXY via `CTR_GteStoreSXY3` → `CTR_GteStoreU32` (byte-wise LE), but the GPU
   walker reads `poly->x0` as native 16-bit halves (`MakeVertexTriangle`:
   `p0[0]`/`p0[1]`), and the 2D path writes them natively
   (`CtrGpu_WritePackedXY`). Test: print `MFC2(12..14)`, the stored prim words,
   and `p0[0]`/`p0[1]` for the first 3D poly. If swapped, make
   `CTR_GteStoreSXY*` store native halves like `CtrGpu_WritePackedXY`; check
   tpage/clut too.
2. **Same class elsewhere**: `CTR_GteStoreIR`, the `matrix_Camera.t[]` host
   assignments, and every other GTE-store helper vs its reader. Test: the
   writer/reader sweep below.
3. **Instance identity** (GLM): are the title models (0x66..0x6b) ever offered
   to QueueDraw? Extend `qd1..qd5` with `model->id` + name words, gated
   menu-active.
4. **The f=91..111 stalls** (two runs wedged there; written off as flakiness).

## Infrastructure (do first, pays for itself)

* **Quiet build**: gate the probes behind one switch and drop the per-line
  flush in `Platform_Log` so 60 s of wall time reaches the title (currently
  ~2 fps under trace volume).
* **Framebuffer dump**: at fixed frames, write the guest's final framebuffer to
  `cache:\` (plus a PNG converter) so the agent can check pixels directly
  (vision) instead of asking for a screenshot. The user remains the final
  visual judge at milestones.
* **Probe-read rule**: a probe that reads a field with a different convention
  than the code produces artifacts (the `sm` t=, `mhs` scH, `qd4` mvp= lines).
  Probes must read via the same helper the code uses, or print both.

## The writer/reader convention sweep (replaces wedge-by-wedge hunting)

For every store helper (`CTR_GteStore*`, `CTR_WriteU32LE`, `CtrGpu_Write*`,
`RenderBucket_WritePackedWord`) and its consumers, build a table:

| destination | example | reader | correct order |
|---|---|---|---|
| PSX-model matrix fields | `matrix_ViewProj.t[]`, `inst->matrix` | `CTR_ReadU32LE`, `gte_Set*` | **LE** |
| prim structs (walker) | `poly->x0`, `poly->u0`, `poly->r0` | `MakeVertex*` (native C) | **native** (16-bit halves for SXY) |
| host C scalars | `depthMac0`, `gte_stsz` outputs | plain C | **native** |
| cooked image data | level/model headers | `ReadPackedWord` etc. | **LE** (as cooked) |

Then fix every mismatch in one pass and add a host unit test per convention
(the existing `run_gte_unit_test.sh` pattern).

## Verification protocol (no more state-only claims)

1. Every step ends with: guest-log check (bounds sane, `ok>0`), framebuffer
   dump comparison, and — at milestones — the user's visual verdict.
2. Stage with `prep_test.sh --cooked` + md5; confirm the probe strings are in
   the exe before running.
3. Keep the real-console path viable; Xenia config only for debugging.
