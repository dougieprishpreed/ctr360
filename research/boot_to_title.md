# boot_to_title — exact expected sequence: frame 13 (cutscene L41, mainGameState=3) → TITLE SCREEN

_Audit pass, 2026-09-19. Read-only. Sources: repo `game/`, `include/`, `platform/`,
`tools/ctr360/build_360_mirror.py`, the run log
`F:/downloads/xenia_canary_windows/cache/ctr360.log` (mtime Sep 19 10:12, XEX Sep 19 10:07)
and `xenia.log` (same run), plus the retail dump (`BIGFILE.BIG`, `XA/ENG.XNF`)._

---

## 0. Where the port actually is right now (log-proven)

| # | line | log text | meaning |
|---|---|---|---|
| 1 | 39532 | `[trace] FinishLoading f=12 mode1=60000000` | TenStages stage 9 done for level 41; `gameMode1 = LOADING\|GAME_CUTSCENE` |
| 2 | 39585 | `[trace] frame: ResetDB f=13 mode1=20000000` | case-1 post-load init finished; LOADING cleared, still GAME_CUTSCENE |
| 3 | 39586 / 39824 | `frame: gameLogic enter f=13 lvl1=82715e5c` … `gameLogic returned f=13` | first frame whose gameLogic completes with real content |
| 4 | 39826-39891 | `rf1..rf19 f=13`, `lg1/lg2w`, `w1 f=13 bsp=00000000 pb=8234501c`, `lg4 f=13 leafs=0` | every render stage of frame 13 runs; the level's BSP root is **NULL** ⇒ level geometry contributes 0 leaves |
| 5 | 39837-39879 | 21 `q7/q8` pairs (`826f53b8`…`826f7140`, last `next=00000000`) | the f=13 visible-instance queue walk queues **21** instances (HANDOFF says 14 — this log says 21) |
| 6 | 39892 | `[trace] DrawOTag#23 enter p=826ED938` | first DrawOTag with real content |
| 7 | 39900-41959 | `walk#23` ×1027 packets, 3 with `len>0` | the OT walk proceeds 1027 packets and **stops** |
| 8 | 41959 | `walk#23 pkt=826CFD0C len=2 code=00 tag=02eca7e4` then `walk#23   prim code=00 len=2 primLength=3` | last guest line of the run |
| 9 | 41960-42366 | 407 × `[CTR Audio] pump callbacks=N` (4000→85200) | audio thread alive; guest main thread wedged (blocked, not spinning) |

Hard negatives that matter:

- `grep -c "CTR GPU"` in `ctr360.log` = **0**; `did not output`, `invalid OT link`,
  `unregistered linked DrawOTag` = **0**. The walker's own error reporters never fired *into the log*.
- `xenia.log`: `KiExceptionDispatch` 0, `C0000005` 0, `RtlRaiseException` 1 (the CRT's normal
  startup one at line 698). No fault. Last guest kernel call = the last `walk#23` trace write
  (xenia.log:216604); everything after is the audio thread's `NtWriteFile`.
- So this is a **silent wedge in the OT packet walk**, exactly the class HANDOFF §2.3 calls
  "blocked in an HLE/memory path".

### 0.1 The packet it dies on (frame-13 specific)

Walks 11–22 are byte-identical in shape: 1034 packets each, 4 with `len>0`
(`826CFD0C len=5 code=00`, `826CFD4C len=7 code=40`, `826CFD8C len=5 code=00`,
`826CFD6C len=7 code=40`, alternating with the `826B81xx` set), and each **terminates cleanly**
on `pkt=…code=60 tag=00ffffff` → `packet done … end=1`.

Walk#23 is different: **1027** packets, 3 with `len>0`, and its tail is

```
41956 walk#23 pkt=826EC93C len=0 code=e8 tag=00ece800
41958 walk#23 pkt=826CFD0C len=2 code=00 tag=02eca7e4   <-- link points here (not the terminator)
41959 walk#23   prim code=00 len=2 primLength=3
```

i.e. frame 13 appends one extra 3-long packet at `826CFD0C` (tag `02eca7e4`, two zero payload
words) to the chain that previously ended at `826EC93C`.

`platform/native_gpu.c:1880-1890`: `primType 0x00` with `len == 2` returns **primLength = 3**
either through the "retail length-2 zero packet" divergence branch or the plain `primSubType == 0`
branch. The walker then does `currentPacket += (primLength + P_LEN) * 4`
(`native_gpu.c:1166`, `P_LEN = 1`, `include/psx/libgpu.h:281`) = **+16 bytes**, while
`endPacket = basePacket + (tagLength + P_LEN) * 4` (`native_gpu.c:1157`) = **+12 bytes**.
⇒ `currentPacket > endPacket`, the tagless loop is skipped, and the very next statement is the
consistency failure `NATIVE_GPU_ERROR("did not output valid primitive or ptag length is not valid (diff=%d …)")`
(`native_gpu.c:1179-1187`).

That error line is the **next expected log line** and it never lands, while the log file keeps
being written by the audio thread for another 407 lines. Two candidate mechanisms, both inside
that error path (ranked in §4): (a) the branch is off-by-one and the *failure* is real
(`len=2` packet consumed as 3 payload longs), (b) the reporter itself wedges — it goes through
`Platform_LogError` → `Platform_LogV(stderr, …)` → `_vsnprintf` + `fputs(stderr)` +
`OutputDebugStringA` (`platform/xbox360/native_xbox360_log.c:170-177,27-57`) and
`NativeGpu_FormatPointerRegion` formats with `%zx` (`native_gpu.c:1039/1049/1060/1068`), a length
modifier the XDK CRT does not support (`snprintf` is `#define snprintf _snprintf`,
`platform/xbox360/native_xbox360_compat.h:46`).

Note the trace caps that will blind the next run: `s_drawOTagTrace < 30` (`platform/native_libgpu.c:300-336`)
— frame 13's walk is **#23**, so only 7 DrawOTag traces remain; walk tracing stops after walk 60
(`native_gpu.c:1131`); the line budget is 60000 (`native_gpu.c:1080-1090`), 27098 used.

---

## 1. (a) What drives the cutscene → menu transition

**`mainGameState` is NOT what changes.** On this path it stays 3 the whole time. The transition is
a *loading-stage* transaction. Only 7 writers exist in the ported game code
(`grep -rn 'mainGameState\s*=' game/`): `MainMain.c:155` (case 1 → 3), `MainMain.c:169`
(case 2 → 1), `MainMain.c:210` (case 3 LOAD_RESTART → 2), `MainMain.c:284` (`FinishLoading:`
→ 1), `MainMain.c:363` (demo-timeout → sets `mainMenuState`, not mainGameState),
`MainMain.c:483` (case 4 reboot, `#ifndef CTR_NATIVE`), `MainMain.c:668` (`StateZero` → 3).

The real chain (every step is a code checkpoint):

1. **Cutscene script** — `CS_Thread_UseOpcode()` (`game/233/CS_Thread.c:111-961`), called from
   `CS_Thread_ThTick` (`CS_Thread.c:1516-1640`, call at 1531) which is ticked by
   `ThTick_RunBucket` (`game/PROC.c:580-647`) from `MainFrame_GameLogic`
   (`game/MAIN/MainFrame.c:334`, probe `g4`).
   The **camera thread** is the one with `instance == 0` (born `CS_Thread_Init(0, CS_INTRO_NAME(s_introcam), …)`,
   `game/233/CS_Cutscene.c:13`, bucket CAMERA at `CS_Thread.c:1658`). Its script is
   `&D233.creditsOpcodeData[0x18]` — `CS_Thread.c:1701-1703`, `CS_CREDITS_ND_CRATE_SCRIPT_OFFSET = 0x18`
   (`CS_Thread.c:58`), `creditsOpcodeData` at retail `0x800b4978` (`include/ovr_233.h:577,728`).
2. **The script's own route to the menu** (`game/233/D233_data.inc:1703-1714`, offsets are
   byte offsets inside `creditsOpcodeData`):
   ```
   0x18  ANIM_SYNC_MARKER
   0x19  PLAY_XA(category=1 EXTRA, xaID=0x51)
   0x22  ANIM_RANGE(frameStart=0x19a, frameEnd=0x19a, arg0=0, arg1=0)   // 410-frame hold
   0x2f  RACEFLAG_TRANSITION1_IF_OFFSCREEN
   0x30  ADVANCE_IF_RACEFLAG_ONSCREEN
   0x31  WAIT_XA_DONE
   0x32  REQUEST_LEVEL(0x27 = 39 = MAIN_MENU_LEVEL)
   0x37  GOTO 0x8f88  ->  creditsOpcodeData[0] = ANIM_RANGE(0xa,0xa) + GOTO 0x8f88  (2-opcode idle loop)
   ```
   `CS_OPCODE_REQUEST_LEVEL` handler: `CS_Thread.c:546-576`; the `MAIN_MENU_LEVEL` arm is
   `CS_Thread.c:565-569` → `RaceFlag_SetDrawOrder(0)`, `gameMode2 &= ~VEH_FREEZE_PODIUM`,
   `MainRaceTrack_RequestLoad(MAIN_MENU_LEVEL)`.
   `ADVANCE_IF_RACEFLAG_ONSCREEN` = `CS_Thread.c:485-488`; `WAIT_XA_DONE` = `CS_Thread.c:592-599`
   (falls through immediately when `CS_XA_STATE == XA_IDLE`).
3. **Input skip (START)** — same function, camera thread only: `CS_Thread.c:311`
   `if ((GAMEPADS->gamepad[0].buttonsTapped & BTN_START) != 0)`. For `NAUGHTY_DOG_CRATE` it is
   gated by `CS_Thread.c:320-331`:
   `if ((u32)gGT->msInThisLEV >> CS_FRAME32_SHIFT < CS_ND_CRATE_SKIP_MIN_FRAME32) goto afterCameraAndSkipChecks;`
   with `CS_FRAME32_SHIFT = 5` (`CS_Thread.c:36`) and `CS_ND_CRATE_SKIP_MIN_FRAME32 = 0xb5`
   (`CS_Thread.c:47`) ⇒ **START does nothing before `msInThisLEV ≥ 0xb5*32 = 5792 ms ≈ 5.8 s**.
   Past the gate: `RaceFlag_SetCanDraw(1)`, force fully-offscreen (`326-330`),
   `CseqMusic_StopAll()` + `CDSYS_XAPauseRequest()` + `RaceFlag_SetDrawOrder(0)` (`345-347`),
   `levelToLoad = MAIN_MENU_LEVEL` (`348`), `MainRaceTrack_RequestLoad(levelToLoad)` (`350`),
   `CS_FINISHED = 1` and `gameMode2 &= ~VEH_FREEZE_PODIUM` (`351-355`).
4. **Request → start load** — `MainRaceTrack_RequestLoad` (`game/MAIN/MainRaceTrack.c:16-30`)
   only sets `sdata->Loading.stage = LOAD_REQUESTED (-4)` and `Loading.Lev_ID_To_Load = 39`.
   The actual start is `MainMain.c:226-260` (case 3, `iVar8 == -4`): waits for
   `RaceFlag_IsFullyOnScreen()`, applies the deferred `gameMode1/gameMode2` Add/Rem bits, then
   `MainRaceTrack_StartLoad(Lev_ID_To_Load)` (`MainMain.c:250`) → `LOAD_LevelFile`
   (`game/LOAD/LOAD_Level.c:29-51`): `prevLEV = levelID; levelID = 39; renderFlags &= CHECKERED;
   Loading.stage = LOAD_TEN_STAGES_0`.
   (If the flag is still off-screen it runs `RaceFlag_BeginTransition(1)` instead — `MainMain.c:253-256`.)
5. **Ten stages for the menu** — `LOAD_TenStages` (`game/LOAD/LOAD_TenStages.c:32-722`):
   stage 0 sets `levelName = metaDataLEV[39].name_Debug` = `"screen15"`
   (`zGlobal_DATA.c:3900-3901`, `zGlobal_RDATA.c:44`) and the `"screen"` prefix match sets
   `gameMode1 |= MAIN_MENU`, `numPlyrCurrGame = 4` (`LOAD_TenStages.c:141-153`, prefix const
   `LOAD_LEVEL_PREFIX_SCREEN_LENGTH = 6`, `include/namespace_Load.h:173`);
   stage 3 → `LOAD_OvrThreads(0)`; stage 4 → **`mainMenuInit[sdata->mainMenuState]()`**
   (`LOAD_TenStages.c:295-302`, table at `LOAD_TenStages.c:3`,
   `mainMenuInit[0] = MM_JumpTo_Title_FirstTime`); stage 8 → audio state `AUDIO_GARAGE_ENTRY`
   for `MAIN_MENU_LEVEL` (`LOAD_TenStages.c:620-630`); stage 9 → `renderFlags =
   (renderFlags & RENDER_FLAG_CHECKERED_FLAG) | RENDER_FLAG_RENDER_BUCKET` + flag transition
   (`LOAD_TenStages.c:683-692`) and `return -2` (LOAD_FINISHED).
6. **The VLC detour only the menu takes** — `MainMain.c:268-277`: when stage == LOAD_FINISHED and
   `levelID == MAIN_MENU_LEVEL || levelID == SCRAPBOOK` → `MainLoadVLC()` and
   `Loading.stage = LOAD_VLC (-6)`; case 3 then parks at `MainMain.c:190-201` until
   `sdata->bool_IsLoaded_VlcTable == 1`, then `goto FinishLoading` → `Loading.stage = LOAD_IDLE;
   mainGameState = 1; gameMode1 &= ~LOADING` (`MainMain.c:279-286`).
   `MainLoadVLC` (`game/MAIN/MainLoadVLC.c:14-30`) allocates
   `(entry[BI_VLCTABLE].size + 0x7ff) & 0xfffff800` and queues `BI_VLCTABLE`
   (=480; 69,632 B) with `MainLoadVLC_Callback` setting the flag (`MainLoadVLC.c:3-12`).
   **This code path has never run in the port** (the ND crate is not MAIN_MENU/SCRAPBOOK).
7. **case 1 for the menu** — `MainMain.c:103-157`: `ElimBG_Deactivate`, clear END_OF_RACE,
   `if (levelID == MAIN_MENU_LEVEL) { if (RaceFlag_IsFullyOffScreen()) RaceFlag_SetFullyOnScreen(); }`
   (`113-119`), `MainInit_FinalizeInit` (`131`), audio state 9/10 (`142-154`), `mainGameState = 3` (`155`).

So the *observable* menu transition is:
`Loading.stage = -4` → `0..9` (level=39) → `-6` (VLC) → `FinishLoading` → `mainGameState = 1` →
`mainGameState = 3`, `gGT->levelID = 39`, `gameMode1 & MAIN_MENU` set, `overlayIndex_Threads = 0`.

### 1.1 Retail timing of the crate cutscene (e)

- It is the **Naughty Dog crate intro**, level 41 `NAUGHTY_DOG_CRATE`
  (`include/namespace_Level.h:47`), bigfile `BI_NDBOX` = 513 (VRAM) / 514 (LEV, 458,808 B) /
  515 (PTR) — `LOAD_GetBigfileIndex` (`game/LOAD/LOAD_Assets.c:262-265`), verified against the dump.
- Content: 21 cutscene threads spawned by `CS_Cutscene_Start` (`game/233/CS_Cutscene.c:43-61`):
  `NDI_BOX_BOX_01/02/02_BOTTOM/02_FRONT/02A/03`, `NDI_BOX_CODE`, `NDI_BOX_GLOW`,
  `NDI_BOX_LID/LIDB/LIDC/LIDD/LID2`, `NDI_KART0..3`, `KART6`, `KART7` (ids `include/namespace_Instance.h:267-285`)
  — the crate lid opening with the Naughty Dog logo and karts.
- Camera: `CS_ND_CRATE_CAMERA_DISTANCE = 0x140` forced while `levelID == NAUGHTY_DOG_CRATE`
  (`CS_Thread.c:303-306`), camera path driven from `gGT->msInThisLEV` scaled by `2^11 / 2^16`
  (`CS_Thread.c:250-268`).
- **Duration ≈ the XA voice-over**: `PLAY_XA(cat=EXTRA(1), id=0x51)` → from the retail `XA/ENG.XNF`
  (magic `XINF`, ver 102, 3 categories, 29 XA files, 414 tracks; header 0x44) cat1
  `numSongs=87, firstSongIndex=13` ⇒ track index 94, entry bytes `08 01 db 02`
  ⇒ `channelFilter=8, fileNumber=1, numSectors=0x2db=731` ⇒ the stream is
  `XA/ENG/EXTRA/S01.XA`, 1,933,312 bytes = 944 Form-2 sectors ≈ **51 s** at 37800 Hz.
  The script's `ANIM_RANGE(0x19a,0x19a)` = a **410-frame hold** (≈6.8 s of game time at 32 ms/frame)
  then the flag transition, then `WAIT_XA_DONE` — so retail plays the crate scene for the length of
  that XA (~51 s) and then **requests the menu by itself** (`REQUEST_LEVEL 0x27`).
- Advance/skip: only **START**, only after 5.8 s of `msInThisLEV` (§1 step 3). Cross/circle/square/
  triangle do nothing here (that is the *title* skip input, `include/ovr_230.h:58`).
- **Port divergence (important):** the XA assets are absent — `dist/assets` contains only
  `ctr-u.bin`, and `xenia.log` shows 39 `NtCreateFile` attempts for `game:/assets/XA/ENG.XNF` and
  `XA/{MUSIC,ENG/EXTRA,ENG/GAME}/S*.XA`, **all failing** (`HostPathDevice::ResolvePath` →
  status 2). So `CDSYS_XAPlay` takes the native branch (`game/CDSYS.c:658-686`):
  `NativeAudio_PlayXATrack(...) == 0` ⇒ `return 0` and `XA_State` is left `XA_IDLE`.
  `CS_OPCODE_WAIT_XA_DONE` therefore falls through immediately, and the script does **not** wait
  51 s — it reaches `REQUEST_LEVEL(0x27)` as soon as the 410-frame hold + the race-flag
  transition complete (≈7 s of game time). If the menu does not arrive within a few hundred
  frames of the cutscene starting to advance, the XA-skip is not the reason.

---

## 2. (b) What the title screen needs

**Level/overlay:**

| what | id | evidence |
|---|---|---|
| level | `MAIN_MENU_LEVEL = 39` | `include/namespace_Level.h:45` |
| level name | `"screen15"` | `zGlobal_DATA.c:3900-3901`, `zGlobal_RDATA.c:44` |
| bigfile files | `BI_MAINMENUFILE = 215` + `{LVI_VRAM=0, LVI_LEV=1, LVI_PTR=2}` ⇒ **215 = VRAM (458,808 B), 216 = LEV (495,716 B), 217 = PTR** | `LOAD_Assets.c:274-277`, `namespace_Load.h:240-242`; sizes read from the dump |
| PTR queued? | **No** — the PTR append is gated to adventure-hub / credits level ranges (`LOAD_TenStages.c:454-458`); 39 matches neither | same |
| overlay 230 | `BI_OVERLAYSECT3 + 0 = 230` (44,612 B); native path does not stream it, it calls `OVR230_InitData()` + `LOAD_Callback_Overlay_230` | `LOAD_Overlays.c:45-88`, `LOAD_Callbacks.c:9-13`, `include/ovr_233.h`-style layout asserts in `ovr_230.h` |
| VLC table | `BI_VLCTABLE = 480` (69,632 B), loaded by `MainLoadVLC` | `MainMain.c:268-277`, `MainLoadVLC.c` |
| models used | `modelPtr[0x66..0x6B]`: `STATIC_INTRO_TROPHY(0x66)`, `STATIC_INTRO_CRASH(0x67)`, `STATIC_RINGTOP(0x68)`, `STATIC_RINGBOTTOM(0x69)`, `STATIC_CTR(0x6A)`, `STATIC_BANNER(0x6B)` | `D230.c:216-224`, `namespace_Instance.h:187-192` |

**What draws it (code chain):**

1. `LOAD_TenStages` stage 4 calls `MM_JumpTo_Title_FirstTime` (`game/230/MM_MenuFlow.c:688-718`):
   `MM_ResetAllMenus()`, `MM_ACTIVE_MENU = &MM_MENU_MAIN`, `MM_TITLE_INTRO_FRAME = 0`,
   `MM_TITLE_MENU_STATE = TITLE_MENU_STATE_INTRO`, distance-to-screen 0x100.
   (`sdata->mainMenuState` has **no initializer** in `zGlobal_SDATA.c`, so it is 0 =
   `MAIN_MENU_TITLE`, `include/namespace_Main.h:138`.)
2. `MM_Title_Init` (`game/230/MM_Title.c:553-651`) — requires
   `MM_TITLE_OBJECT == NULL && (gameMode1 & MAIN_MENU) && state != EXITING &&
   modelPtr[STATIC_RINGTOP] != 0 && level1->ptrSpawnType1->count > 2` (lines 568-583). It grabs the
   camera path from spawn-type-1 (`ST1_GETPOINTERS`, `ST1_CAMERA_PATH`, `namespace_Level.h:589-601`),
   births the `Title` thread (`MM_Title_ThTick`) and **6 instances**.
3. Per-frame: `MM_MenuProc_Main` (`MM_MenuFlow.c:52-283`) → `MM_Title_MenuUpdate`
   (`MM_Title.c:3-261`) runs the state machine INTRO(0) → IN_MENU(1) → EXITING(2)/RETURNING(3)
   (`include/ovr_230.h:27-30`); the intro frame counter runs to
   `TITLE_INTRO_MENU_READY_FRAME = 230` and the TM line draws past frame 229
   (`MM_MenuFlow.c:76-82`).
4. Draw calls in the frame: `RenderAllTitleDPP` → `MM_Title_SetTrophyDPP`
   (`game/MAIN/MainFrame_RenderFrame.c:769-780`, probe `rf13`) and
   `RenderBucket_ExecuteAllInstances` (`rf14`) — both gated on `gameMode1 & MAIN_MENU`,
   `LOAD_IsOpen_MainMenu()` (= `overlayIndex_Threads == OVERLAY_INDEX_MAIN_MENU`,
   `game/LOAD/LOAD_IsOpen.c:8-11`) and `RENDER_FLAG_RENDER_BUCKET` (set by stage 9).
5. `MM_Title_ThTick` (`MM_Title.c:434-551`) drives the 6 instances, plays the 8 title sounds
   (`D230.c:258-268`) and the trophy specular light; `TITLE_INTRO_SKIP_INPUT`
   (cross/circle/square/triangle, `ovr_230.h:58`) sets `MM_TITLE_INTRO_FRAME = 1000` to skip.
   30 s of no input → `TITLE_MENU_STATE_EXITING` + `MM_EXIT_ROUTE_DEMO` (`MM_MenuFlow.c:84-110`).

---

## 3. (c) Where a stall would most likely occur between here and the title — ranked

1. **Frame-13 OT walk tail (the stall that exists now).** Last line `walk#23 pkt=826CFD0C len=2
   code=00 tag=02eca7e4` + `prim code=00 len=2 primLength=3` (log 41959); the next statement in
   `ParsePrimitivesLinkedList` is the `currentPacket != endPacket` failure
   (`native_gpu.c:1179-1187`) whose line never lands. Fix/hypothesis: `primLength` for a `len==2`
   tag must be **2**, not 3 (`native_gpu.c:1876-1890`), because the walker adds `P_LEN` itself
   (`native_gpu.c:1166`); and/or the error reporter must be made non-blocking (`%zx` →
   `%08x`, `Platform_LogFlush()` first, and log via `Platform_Log` not `Platform_LogError`).
2. **The same walk on frames 14+ once it completes**: `DrawAllSplits` (`native_gpu.c:944-990`) —
   frame 13's walk has `splits=0` so far; the flag/instance geometry must produce splits and
   the vertex upload must scale (f=11/12 show `1 split(s) at 12 verts`, `vb: locking bytes=768`,
   `DrawTriangles start=0 count=4`). Every frame also still triggers Xenia's
   `Surface pitch 9552 larger than the maximum texture width 8192` +
   `PM4_DRAW_INDX(6,4,2): Failed in backend` (xenia.log tail, repeated per frame) — unresolved
   (RESEARCH F2) and fatal to *textured* level/menu draws.
3. **The CS camera-thread script advance (unobserved).** Nothing in the log proves the cutscene
   script ever runs an opcode: there is no probe in `CS_Thread_UseOpcode`, and the menu request
   depends on `ANIM_RANGE(0x19a)` completing + `RaceFlag_IsFullyOffScreen/OnScreen` transitions +
   `WAIT_XA_DONE`. If the camera thread is not ticked (bucket CAMERA, `MainFrame.c:334`), or
   `msInThisLEV` does not advance (`MainFrame.c:210`), or `RaceFlag_DrawSelf` never completes its
   transition (`RaceFlag_GetOT`, `game/RaceFlag.c:231-318`), the request never fires and the port
   sits in `mainGameState=3` forever with no error — indistinguishable from a wedge.
4. **The menu level load + VLC gate** (`MainMain.c:190-201, 268-277`, `MainLoadVLC.c`). The VLC
   path is new code that has never executed; a queued `LT_SETADDR` read whose callback never runs
   parks the boot in `Loading.stage = -6` with `mainGameState = 3`. Second-order: the menu LEV's
   own mesh/InstDef/model scalars (entry 216 is a level: pointer map + level scalars + InstDef +
   level models are cooked, but **mesh/vertex/quadblock data is cooked by no pass** — RESEARCH F1),
   and the menu's model pack (`BI_MAINMENUFILE+2`? no: the menu pack is the VRAM/LEV pair above;
   driver MPKs come from `LOAD_DriverMPK`, `LOAD_Assets.c:80+`).
5. **Overlay-230 native reset / `LOAD_IsOpen_MainMenu`** (`LOAD_Overlays.c:45-88`, `D233.c:133-165`
   pattern) — pure-C resets in this port, low risk, but `MM_Title_Init` will silently do nothing
   (no title object ⇒ blank menu) if `modelPtr[STATIC_RINGTOP]` is 0 or
   `level1->ptrSpawnType1->count <= 2` (`MM_Title.c:568-583`) — a **non-crashing** failure mode.
6. **The crate cutscene's own first real draws** (`w1 f=13 bsp=00000000` ⇒ 0 level leaves): the
   visible content is the 21 queued instances + the checkered flag/loading text. If the ND box
   instances' mesh command lists are uncooked garbage, the *cutscene* stays blank while the frame
   loop "works" — visual, not fatal (RESEARCH F1).

---

## 4. (d) Exact log lines / probe signatures that prove each transition

### 4.1 Lines that already exist in this build (BOOT_TRACE / platform probes)

| transition | proving line(s) | emitter |
|---|---|---|
| cutscene script runs / advances | _(none today — see 4.2 #2/#3)_ | — |
| menu level requested | _(none today — see 4.2 #1/#3)_ | — |
| load engaged | `[trace] main loop it=%d state=%d loadStage=%d gameMode1=%08x level=%d frame=%d xa=%d` (it==1 or %60) | `build_360_mirror.py:680` |
| stage machine | `[trace] TenStages: stage %d level=%d` (expect `stage 0..9 level=39`) | `:761` |
| per-stage sanity | `[trace] stage=%d d15=%08x d64=%08x` (cap 60) | `:879` |
| model store | `[trace] LibOfModels_Store: arr=%08x m=%08x raw=…` | `:778` |
| MPK stage | `[trace] stage5: ptrMPK=%08x mpkIcons=%08x words=…` | `:788` |
| stage 9 / load end | `[trace] stage9: pre-ElimBG xa=%d ptrLevelFile=%08x level1=%08x` → `stage9: post-ElimBG` → `[trace] FinishLoading f=%d mode1=%08x` (expect `mode1` with `MAIN_MENU=0x2000` and **without** `GAME_CUTSCENE=0x20000000`) | `:1071,1073,1075` |
| case 1 | `[trace] case1: stats reset/rain reset/highscore ptr/finalize init/engine audio f=%d` | `:1080-1092` |
| frame loop | `frame: ResetDB f=%d mode1=%08x` / `gameLogic enter` / `gameLogic returned` / `beginFrame done` / `renderFrame returned f=%d lvl1=%08x mesh=%08x` | `:1058-1066` |
| render stages | `rf1..rf19`, `rf10b`, `lg1/lg2w/lg2s/lg4`, `w1 f=%d bsp=%08x pb=%08x`, `q1..q8`, `g0..g9`, `t1` | `:920-950, 1047-1150` |
| OT walk | `[trace] DrawOTag#%d enter p=%p` → `walk#%d pkt=%p len=%d code=%02x tag=%08x` → `packet done: splits=%d verts=%d end=%d` → `DrawOTag#%d walker done` → `DrawAllSplits: %d split(s) at %d verts` → `DrawOTag#%d splits done` → `exit` | `native_libgpu.c:305,324,329,335`; `native_gpu.c:1141,1195` |
| present | `[CTR Renderer] frame %d presented` (every 300), `[trace] present ok %d` (598-606 only) | `native_xbox360_video.c:2672-2685` |
| liveness | `[CTR Audio] pump callbacks=N queuedBytes=N` | audio backend |

**Menu-specific positive signature (what to look for after the fix):**
`TenStages: stage 0 level=39` … `stage 9 level=39` → `FinishLoading f=… mode1=00002000`
→ `case1: finalize init` → `frame: ResetDB f=… mode1=20002000` → `rf13`/`rf14` drawing
→ `main loop … level=39`.

### 4.2 Probes to add (this is the actionable instrumentation)

1. **`[probe] menu: request level=%d cs=%08x ms=%d`** immediately before
   `MainRaceTrack_RequestLoad(levelToLoad);` at `game/233/CS_Thread.c:350` (skip path) and
   before/after `CS_Thread.c:568` (script path). One line proves the whole (a) chain.
2. **`[probe] cs: inst=%08x opcode=%d at=%p anim=%d dur=%d phase=%d ms=%d`** right after the
   declarations in `CS_Thread_UseOpcode` (`CS_Thread.c:137-141`, after
   `metadataBackup = cs->decodedOpcode;`), count-capped to ~200 calls. Proves the camera thread's
   opcode progression (0x22 ANIM_RANGE → 0x2f → 0x30 → 0x31 → 0x32 REQUEST_LEVEL).
3. **`[probe] cs: REQUEST_LEVEL id=%d`** inside `case CS_OPCODE_REQUEST_LEVEL:` (`CS_Thread.c:546`)
   — the single most decisive line for "cutscene → menu".
4. **`[probe] raceflag: pos=%d anim=%d candraw=%d order=%d`** at the top of `RaceFlag_GetOT`
   (`game/RaceFlag.c:231-240`) and **`[probe] raceflag: begin dir=%d stage=%d`** in
   `RaceFlag_BeginTransition` (`RaceFlag.c:162`) — proves the flag transition the script waits on
   (`ADVANCE_IF_RACEFLAG_ONSCREEN`).
5. **`[probe] mm: menuInit idx=%d state=%d`** at `game/LOAD/LOAD_TenStages.c:298-301` and
   **`[probe] mm: titleInit obj=%08x ringtop=%08x st1=%d level1=%08x`** at `MM_Title.c:568-583`
   — proves `MM_JumpTo_Title_FirstTime` and the title object birth (or the silent no-op).
6. **`[probe] mm: state=%d introFrame=%d demo=%d`** at the top of `MM_Title_MenuUpdate`
   (`MM_Title.c:3`) — proves INTRO → IN_MENU and the 230/245 counters.
7. **`[probe] vl: load entry=%d size=%d isLoaded=%d`** in `MainLoadVLC` and
   `MainLoadVLC_Callback` (`game/MAIN/MainLoadVLC.c:6,14-29`) — proves the menu-only VLC gate.
8. **`[probe] ovr: threadsIdx=%d open=%d`** at `LOAD_OvrThreads` entry
   (`game/LOAD/LOAD_Overlays.c:68`) and after `LOAD_Callback_Overlay_230`
   (`LOAD_Callbacks.c:9-13`).
9. **`[probe] walktail pkt=%p len=%d code=%02x primLength=%d end=%p cur=%p`** immediately before
   the `NATIVE_GPU_ERROR` at `platform/native_gpu.c:1179`, plus a `Platform_LogFlush()` before it,
   plus change the `%zx` in `NativeGpu_FormatPointerRegion` (`native_gpu.c:1039/1049/1060/1068`)
   to `%08x` — this both localizes the current wedge and removes the `_snprintf` `%z` hazard.
10. **Raise the caps** (they will blind the very frames of interest):
    `s_drawOTagTrace` 30 → ≥120 and print `walker done` unconditionally
    (`native_libgpu.c:300-336`); walk tracing past walk 60 (`native_gpu.c:1131`);
    `s_walkTraceLines` budget 60000 → 200000 (`native_gpu.c:1080-1090`);
    `g1` (12) and `g4` (20) are already exhausted.

### 4.3 What "blocked vs spinning" looks like for this failure

- Blocked: `[CTR Audio] pump callbacks` keeps advancing while no guest line appears (current state:
  last guest line 41959, audio continues 4000 → 85200 = 407 lines).
- The HANDOFF's CPU-delta check (`powershell … TotalProcessorTime`) remains the tie-breaker.

---

## 5. Open / not determined

1. **Which mechanism wedges the walk** — the off-by-one `primLength` for the `len==2` packet
   (`native_gpu.c:1876-1890` vs `:1157/1166`) or the error reporter itself (`%zx`/stderr).
   The log proves only that the thread stopped between the `prim code=…` line and the next
   expected line, and that no `[CTR GPU]` line ever landed.
2. **Why frame 13's OT is different** (1027 vs 1034 packets, and the extra `826CFD0C len=2` node
   linked after `826EC93C`): which subsystem appended it is not identified from the log alone;
   candidates are the flag/loading-text packets (`RaceFlag_DrawSelf`, `RaceFlag.c:753-771`) and
   the UI OT of `pushBuffer_UI`. A `[probe] drawotag: ot=%p len=%d` at `DrawOTag` entry plus the
   `NativeGpu_FormatPointerRegion` output (which names `pbN.ot+0x…` / `ui.ot+0x…` / `dbN.ot+0x…`)
   would name it in one run.
3. **Whether the cutscene script advances at all** — no probe exists; `cs:` probes (#2/#3) settle it.
4. **Menu-level cook coverage** — entry 216 (the menu LEV) is a level and gets the level passes,
   but mesh/quadblock/vertex data is still uncooked by every pass (RESEARCH F1), and the menu's
   model pack path (`BI_MAINMENUFILE+…`) is untested. Whether the title's 6 instances need cooked
   mesh to be visible is unverified.
5. **`XA/ENG.XNF` + `XA/**/S*.XA` are not staged** (`dist/assets` has only `ctr-u.bin`). Consequence
   established above (no 51 s wait), but the *extraction* tooling for those files was not audited.
6. The claim "14 queued driver instances" in HANDOFF does not match this log (21 `q7/q8` entries
   for f=13); one of the two is stale.
