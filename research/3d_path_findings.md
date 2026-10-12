# 3D path findings — the "nothing ever renders" root cause + the model-data cooks

Session evidence gathered with in-build probes (`[probe] qall/rbe/qd*/qm`, `[trace] qw/d7/bd*`).
All log lines below are verbatim from `F:\downloads\xenia_canary_windows\cache\ctr360.log`
(Xenia run logs; the guest log is `cache:\ctr360.log` in the box).

## 1. Root cause of "SCEA screen then copyright screen, nothing else" (FIXED)

`game/RenderBucket/RenderBucket_QueueExecute.c` `RenderBucket_QueueDraw()` had a mis-patched
guard in the **tree** copy (`build-360/gen/...`, the copy that is actually compiled):

```c
	if (inst->model->headers == 0)
	{ static int s_q9 = 0; ... trace ... }   // <-- closes the if body
	{
		g_ctr360_qdDrop[2]++;
		return rbi;                          // <-- UNCONDITIONAL for every instance
	}
```

The q9 probe (from an earlier probe batch) was inserted as a separate block *before* the
guard's body, so the `return rbi;` ran for **every** instance of every frame. Result:
`RenderBucket_QueueAllInstances` always left the bucket empty, `RenderBucket_Execute` saw
`ents=0` on every frame, and no model polygon ever reached the OT — while 2D screens
(SCEA/copyright, drawn through the direct prim path) rendered fine. That is exactly the
reported symptom, and it also explains why the earlier `%zx`/reporter fixes "worked" in the
log yet the screen never changed.

Evidence before the fix:
`[probe] rbe ents=0 ok=0 disp=0 cas=0,0,0,0,0 ...` on every frame, and
`[probe] qall att=42 q=0 d=0,0,42,0,0,0,0,0,0` at frame 13 (42 attempts, 0 queued).
A one-shot dump at the drop site proved the models themselves were fine:
`[trace] qm f=14 inst=826f64b4 model=827780c8 w0=6e64695f w1=626f785f w2=6c696464 ... w5=827780e0`
(= name "ndi_box_lidd", `headers = 0x827780e0`, non-NULL).

**Rule for future probe batches: never insert a probe between an `if (...)` header and its
`{`; always put it inside the body.** The repo copy (`game/...`) was correct all along; only
the tree was broken, so the bug was invisible in source review.

## 2. Model data cooks added to `tools/ctr360/cook_disc.py`

With the guard fixed, every instance walked deeper and immediately exposed two more
uncooked model-data families (both previously "masked" because the stray return hid them):

### 2a. `dram_model_anim_sites` — ModelAnim + ModelFrame scalars
Pack/level models: `ModelHeader.ptrAnimations` (@0x38, map word) -> `ModelAnim`
(`numFrames` u16 @0x10, `frameSize` s16 @0x12, ModelFrame array at +0x18 with stride
`frameSize`). Per frame: `pos` (3*s16) + pad @0..7, `vertexOffset` (int) @0x18.
Un-cooked, `numFrames` 115 read as 29440 and `vertexOffset` 0x1C as 0x1C000000, so
`RenderBucket_GetFrame` returned a frame pointer outside guest RAM
(`[trace] qd3 f=13 frame=89a92808 next=00000000`) and the walk wedged at f=13.
Cooked entry 514 (the ND crate pack "ndi_box_*"): 21 anims / 1743 frames / 3528 sites.
The pass drops any site that overlaps a loader-map word or an earlier cook (the map is
authoritative - the loader adds the base to those).

### 2b. `dram_model_cmdlist_sites` — command lists + color layouts
Verified layout (entry 514): `commandList = [u32 colorCount][u32 command ...][0xFFFFFFFF]`,
command words bit-packed (`flags >>24`, `stackIndex >>16`, ...; the port's readers are in
`RenderBucket_DrawFunc_*` / `RenderBucket_CopyScratchColorCache`), colors = `colorCount`
words at `ModelHeader.ptrColors` (@0x2C). All must be byte-swapped. Un-cooked,
`commandList[0]` read as `count<<24`, `RenderBucket_CopyScratchColorCache` copied ~150M
words and Xenia dumped a crash:

```
!> F800002C ==== CRASH DUMP ====  PC: 0x82313984  Access Violation: read at 0x000000013483A583
 r4 = 000000003483A577   r29 = 000000003483A577   (fault address = r4 + 0xC)
```

After the cook: no crash dump in the run, the game runs to the menu.

## 3. State after the fixes (verified in the last run)

- No crash, no wedge, no `[fault]`; frame loop healthy through the menu (`hbm f=725`).
- `[trace] qd5 f=561 drawFunc=8006a52c uncompress=8006a8e0` - instances now complete
  QueueDraw and select real retail draw handlers.
- The bucket now receives entries (`qall ... q=4/6/10`, `rbe ents=2/3/5`, `cas=1`).
- Remaining drops in the menu are *plausible* retail filters, not data faults:
  - `BuildDepthRange` culls: `[trace] bdx f=499 maxX=-1024`, `bdy f=13 maxY=-1024`,
    `bdz f=13 maxZ=0 half=160` (projected bounds degenerate/off-screen).
  - `PrepareDrawContext` drops on `(instFlags & 0x80)` (HIDE_MODEL) - expected while the
    title instances have not reached their `animStartFrame` (MM_Title_ThTick hides
    instances 0,1,3,4,5 before their animation starts).
  - `(instFlags & 0x40) == 0` for some entries.

## 4. Next gates (in order of value)

1. **Projected-bounds quality**: the culls are the remaining reason cutscene/menu models do
   not draw. `RenderBucket_ProjectFrameBounds` projects the packed frame bbox through the
   GTE (`gte_rtpt`) with `projectionMvp` from the instance's IDPP. Degenerate `maxZ=0` /
   `maxX=-1024` bounds point at either (a) the MVP the camera code stores per instance, or
   (b) the packed bbox built from `mf->pos` (now cooked) + `projectionMvp`. Compare a known
   visible instance's MVP against a reference value.
2. **Who queues entries outside QueueAllInstances**: the bucket base gets entries between
   the queue and the execute (`qb n=0` yet `eb ents=2..5`) - find that writer (likely a
   `RB_*`/title/particle path) and confirm it prepares IDPP fields (those entries drop at
   `mf == 0` / HIDE).
3. **Cutscene camera**: the ND-crate frames cull with `maxZ=0`; confirm the cutscene camera
   matrix/`distanceToScreen_PREV` are set (`CS_*` camera path).

## 5. The remaining visible blocker: degenerate per-instance projections (INVESTIGATED)

After the guard fix + cooks, the screen still never changes. The instance pipeline now runs
(instances complete QueueDraw, draw funcs are selected, the bucket fills), but the projected
bounds are degenerate, so `RenderBucket_AcceptProjectedBounds` culls everything:

```
[trace] pj f=13 minXY=dff80000 minZ=00000010 sxy=fc00006c sz=0 mvp=00000000,00000000,00000000,00000000,00000000,00000000,00000000,00000000
[trace] pk f=13 x=108..108 y=256..256 z=0..0 h=320
[trace] bdx f=499 maxX=-1024 / bdy f=13 maxY=-1024 / bdz f=13 maxZ=0 half=160
```

Chain (`RenderBucket_ProjectFrameBounds` -> `gte_rtpt` with `projectionMvp`):

1. The camera side is FINE in the menu: `PushBuffer_UpdateFrustum` / `PushBuffer_SetMatrixVP`
   run per frame and compose `pb->matrix_ViewProj`; `[trace] rl f=712 i=0 rot=30728,0,0
   pos=0,-32768,-16381` (rot/pos set by the title camera; identity at f<=12 while no camera
   exists yet -- expected).
2. The instance side is NOT: `projectionMvp` = `idpp->mvp` = `m3x3 x pb->matrix_ViewProj`
   (GTE light-matrix multiply, `RenderBucket_BuildMvp`) and comes out ~0:
   `[trace] qd4 f=724 m=0000ee4f,80000000,00000000,0000ee4f,00000000 vp=00000010,00000000,00000900
    im=00063148,0006314c,00063150 mvp=00800000,0000f6ff,00000000,00000000,00000000`
   The `m3x3` tuple (`m=`) contains a saturated halfword (0x8000 = -32768) and the source
   `inst->matrix` words do not look like the scaled matrix MM_Title_Init writes
   (`TITLE_MATRIX_SCALE` on the diagonal, t = 0).
3. `RenderBucket_BuildM3x3` / `BuildMvp` / `StoreMvpTranslation` are byte-identical to the
   ctr-native reference; a whole-tree diff (`diff -rq ctr360/game repos/ctr-native/game`)
   shows only this session's probe lines in MM_Title.c / others. So the fault is in either
   the shared platform GTE helpers (`RenderBucket_GteMulLightMatrixColumns`,
   `RenderBucket_LoadMatrixWords`, `RenderBucket_StoreMatrixWords` -- compare against the
   reference platform code) or in the instance matrix data for the offered instances.

### Next steps (in order)
1. Extend the qd1..qd5 traces with `inst->name` / `inst->model->id` and confirm WHICH
   instances reach QueueDraw in the menu -- in particular whether the six title models
   (ids 0x66..0x6b from MM_TITLE_INSTANCES) are offered. If they are never offered, look at
   the visible-instance list build (`cDC[0].visInstSrc`, `INSTANCE_Birth3D` pool insert).
2. For an offered title instance, dump `inst->matrix` (all 8 words), `mh->scale`, and the
   `m3x3` tuple right after `BuildM3x3`, then compare `inst->matrix` with what MM_Title_Init
   wrote (diagonal = TITLE_MATRIX_SCALE). A zero/garbage source matrix here means the
   instance matrix writer in the title path is missing.
3. Unit-test the GTE light-matrix multiply: feed a known `m3x3` and a known
   `pb->matrix_ViewProj`, check the product against a hand-computed matrix. If the helper
   mis-orders the columns (a classic port bug), `mvp` collapses exactly like this.
4. Optional: `xenia --debug`, break on the first culled instance, inspect live GTE/矩阵 state.
