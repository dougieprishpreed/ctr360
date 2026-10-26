#include <common.h>
#include <platform/native_precise.h>
#include <platform/native_renderer.h>

#if defined(CTR_NATIVE)
/* Deterministic VRAM captures at named transitions (IMPLEMENTATION_PLAN Phase
 * 0.2). MainFrame_ResetDB runs at frame start, so the VRAM still holds the
 * previous frame - which is what the user's screen showed. Files land in
 * cache:\ and convert with tools/ctr360/tga_to_png.py. */
static void Ctr360_CaptureScheduledVRAM(void)
{
	static const int s_frames[] = { 12, 20, 30, 40, 50, 61, 75, 100, 205, 455, 505, 565, 625, 715, 745, 800 };
	static const char *s_tags[] = { "copyright", "boot20", "boot30", "boot40", "boot50", "crate61", "crate75", "crate100", "crate", "menu", "title000", "title060", "title120", "title210", "inmenu", "idle" };
	char path[64];
	int i;

	/* Full legacy VRAM dumps are a diagnostic opt-in. Console USB writes
	 * and GPU readbacks must not interrupt an ordinary launch. */
	if (!Platform_TraceEnabled(CTR_TRACE_VRAM)) return;

	for (i = 0; i < (int)(sizeof(s_frames) / sizeof(s_frames[0])); i++)
	{
		if ((int)sdata->frameCounter == s_frames[i])
		{
			sprintf(path, "cache:\\ctr360_%s_f%04d_vram.tga", s_tags[i], s_frames[i]);
			Platform_LogWarn("[cap] f=%d tag=%s path=%s\n", s_frames[i], s_tags[i], path);
			NativeRenderer_SaveVRAM(path, 0, 0, VRAM_WIDTH, VRAM_HEIGHT, 1);
		}
	}
}
#endif

#if defined(CTR_NATIVE)
static void MainFrame_RegisterGpuLinkRanges(struct GameTracker *gGT)
{
	static const char *const primLabels[2] = {"db0 prim", "db1 prim"};
	static const char *const otLabels[2] = {"db0 OT", "db1 OT"};
	static const char *const swapchainLabels[2] = {"swapchain OT0", "swapchain OT1"};

	NativeGpuLinks_Reset();

	// NOTE(aalhendi): Retail links PS1 RAM addresses directly in 24-bit GPU
	// tags. Native keeps the same packet shape, but maps the double-buffered
	// host draw arenas to stable 24-bit tokens before any OT/tag writer runs.
	for (int i = 0; i < 2; i++)
	{
		struct DB *db = &gGT->db[i];
		NativeGpuLinks_RegisterRangeChecked(primLabels[i], db->primMem.start, db->primMem.capacityBytes);
		NativeGpuLinks_RegisterRangeChecked(otLabels[i], db->otMem.start, db->otMem.capacityBytes);
		NativePrecise_SetRegion(i, db->primMem.start, db->primMem.capacityBytes);
	}
	// The back buffer's primitive memory was just rewound.
	NativePrecise_NewFrame();

	u32 swapchainOTBytes = ((u32)gGT->numPlyrCurrGame << 12) | 0x18u;
	for (int i = 0; i < 2; i++)
	{
		NativeGpuLinks_RegisterRangeChecked(swapchainLabels[i], gGT->otSwapchainDB[i], swapchainOTBytes);
	}
}
#endif

void MainFrame_TogglePauseAudio(b32 bool_pause)
{
	if (bool_pause == 0)
	{
		if (sdata->boolSoundPaused)
		{
			howl_StopAudio(0, 0, 1);
			howl_UnPauseAudio();
			sdata->boolSoundPaused = 0;
		}
	}
	else if (sdata->boolSoundPaused == 0)
	{
		OtherFX_Stop2(1);
		howl_PauseAudio();
		sdata->boolSoundPaused = 1;
	}
	return;
}

void MainFrame_ResetDB(struct GameTracker *gGT)
{
	u32 *puVar3;
	int iVar4;
	struct DB *db;
	int otSwapchainDB;

#ifdef CTR_NATIVE
	static int hintTraceState = -1;
	if ((gGT->gameMode1 & ADVENTURE_ARENA) && sdata->Loading.stage == LOAD_IDLE &&
	    (hintTraceState != sdata->AkuAkuHintState || (gGT->framesInThisLEV % 120) == 0))
	{
		hintTraceState = sdata->AkuAkuHintState;
		Platform_Log("[probe] hb hint f=%d age=%d state=%d request=%d visible=%d model=%08x mask=%08x queue=%d ready=%d load=%d xa=%d cam=%08x\n",
		             (int)sdata->frameCounter, (int)gGT->framesInThisLEV,
		             (int)sdata->AkuAkuHintState, (int)sdata->AkuHint_RequestedHint,
		             (int)sdata->boolDraw3D_AdvMask, (unsigned)(u32)sdata->modelMaskHints3D,
		             (unsigned)(u32)sdata->instMaskHints3D, (int)sdata->queueLength,
		             (int)sdata->queueReady, (int)sdata->load_inProgress,
		             (int)sdata->XA_State, (unsigned)gGT->cameraDC[0].flags);
		if (gGT->drivers[0] != NULL)
			Platform_Log("[probe] hb hint-driver pos=%d,%d,%d speed=%d\n",
			             (int)gGT->drivers[0]->posCurr.x, (int)gGT->drivers[0]->posCurr.y,
			             (int)gGT->drivers[0]->posCurr.z, (int)gGT->drivers[0]->speed);
		if (sdata->instMaskHints3D != NULL && sdata->AkuAkuHintState != 0)
			Platform_Log("[probe] hb hint-mask pos=%d,%d,%d scale=%d,%d,%d frame=%d\n",
			             (int)sdata->instMaskHints3D->matrix.t[0], (int)sdata->instMaskHints3D->matrix.t[1],
			             (int)sdata->instMaskHints3D->matrix.t[2], (int)sdata->instMaskHints3D->scale.x,
			             (int)sdata->instMaskHints3D->scale.y, (int)sdata->instMaskHints3D->scale.z,
			             (int)sdata->instMaskHints3D->animFrame);
	}
#endif

	if (sdata->frameCounter <= 120 || (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722))
	{
		Platform_Log("[probe] hb reset-enter f=%d hubSwap=%d step=%08x stage=%d level2=%08x\n", (int)sdata->frameCounter,
		             (int)gGT->bool_AdvHub_NeedToSwapLEV,
		             gGT->drivers[0] ? (unsigned)gGT->drivers[0]->stepFlagSet : 0, (int)sdata->Loading.stage,
		             (unsigned)(u32)gGT->level2);
	}

	Ctr360_CaptureScheduledVRAM();

	// check if new adv hub should be loaded,
	// this was a random place for ND to put it
	LOAD_Hub_Main(sdata->ptrBigfile1);
	if (sdata->frameCounter <= 120 || (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722))
	{
		Platform_Log("[probe] hb reset-hub-done f=%d\n", (int)sdata->frameCounter);
	}

	gGT->swapchainIndex = 1 - gGT->swapchainIndex;

	gGT->backBuffer = &gGT->db[gGT->swapchainIndex];
	gGT->frameTimer_MainFrame_ResetDB++;

	otSwapchainDB = (int)gGT->otSwapchainDB[gGT->swapchainIndex];

	db = gGT->backBuffer;
	db->blurCameraMask = 0;
	db->primMem.cursor = db->primMem.start;
	db->primMem.primitiveCount = 0;
	db->otMem.cursor = db->otMem.start;

#if defined(CTR_NATIVE)
	MainFrame_RegisterGpuLinkRanges(gGT);
	if (sdata->frameCounter <= 120 || (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722))
	{
		Platform_Log("[probe] hb reset-links-done f=%d\n", (int)sdata->frameCounter);
	}
#endif

	CTR_EmptyFunc_MainFrame_ResetDB();
	DecalGlobal_EmptyFunc_MainFrame_ResetDB();

	ClearOTagR((u32 *)otSwapchainDB, sdata->gGT->numPlyrCurrGame << 10 | 6);
	if (sdata->frameCounter <= 120 || (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722))
	{
		Platform_Log("[probe] hb reset-ot-done f=%d\n", (int)sdata->frameCounter);
	}

	for (iVar4 = 0; iVar4 < sdata->gGT->numPlyrCurrGame; iVar4++)
	{
		gGT->pushBuffer[iVar4].ptrOT = (u32 *)((int)otSwapchainDB + (sdata->gGT->numPlyrCurrGame - iVar4 - 1) * 0x1000 + 0x18);
	}

	for (; iVar4 < 4; iVar4++)
	{
		// but why?
		gGT->pushBuffer[iVar4].ptrOT = (u32 *)((int)otSwapchainDB + 3 * 0x1000 + 0x18);
	}

	puVar3 = (u32 *)((int)otSwapchainDB + 4);
	gGT->pushBuffer_UI.ptrOT = puVar3;
	db->otMem.uiOT = puVar3;

#if defined(CTR_NATIVE)
	if (sdata->ptrPushBufferUI != 0)
	{
		struct PushBuffer *wumpaPushBuffer = (struct PushBuffer *)(u32)sdata->ptrPushBufferUI;

		// NOTE(aalhendi): Retail stores PS1 RAM OT addresses here. Native stores
		// host pointers, so reset the fake UI pushbuffer to the current backbuffer
		// before RenderBucket can publish this frame's range metadata.
		wumpaPushBuffer->ptrOT = gGT->pushBuffer_UI.ptrOT;
		wumpaPushBuffer->renderBucketOTRangeEnd = NULL;
		wumpaPushBuffer->renderBucketOTByteOffset = 0;
	}
#endif

	return;
}

#if defined(CTR_NATIVE) && defined(CTR_INTERNAL)
#include <platform/native_replay_scheduler.h>
#endif

static void MainFrame_TraceIntroStep(const char *step, int bucket)
{
#ifdef CTR_NATIVE
	static int lastFrame = -1;
	static int frames = 0;
	static int demoStart = -1;
	struct GameTracker *tracker = sdata->gGT;
	if (tracker->levelID == CRASH_COVE && sdata->Loading.stage == LOAD_IDLE)
	{
		int frame = (int)sdata->frameCounter;
		if (demoStart < 0) demoStart = frame;
		if (frame - demoStart <= 1200)
			Platform_Log("[probe] hb demo f=%d age=%d step=%s bucket=%d demo=%d mode=%08x\n", frame, frame - demoStart, step, bucket,
			             (int)tracker->boolDemoMode, (unsigned)tracker->gameMode1);
		if (((frame - demoStart) % 60) == 0 && bucket == -1 && strcmp(step, "game-enter") == 0)
		{
			struct Driver *driver = tracker->cameraDC[0].driverToFollow;
			struct PushBuffer *pb = &tracker->pushBuffer[0];
			if (!driver) driver = tracker->drivers[0];
			Platform_Log("[probe] hb demo-camera f=%d players=%d follow=%08x driver0=%08x cam=%d,%d,%d/%d,%d,%d fade=%d/%d cmode=%d flags=%08x\n",
			 frame, (int)tracker->numPlyrCurrGame, (unsigned)tracker->cameraDC[0].driverToFollow, (unsigned)tracker->drivers[0],
			 (int)pb->pos.x, (int)pb->pos.y, (int)pb->pos.z, (int)pb->rot.x, (int)pb->rot.y, (int)pb->rot.z,
			 (int)pb->fadeFromBlack_currentValue, (int)pb->fadeFromBlack_desiredResult, (int)tracker->cameraDC[0].cameraMode,
			 (unsigned)tracker->cameraDC[0].flags);
			if (driver)
				Platform_Log("[probe] hb demo-world f=%d pos=%d,%d,%d vel=%d,%d,%d normal=%d,%d,%d rot=%d,%d,%d speed=%d nav=%08x path=%d flags=%08x inst=%d,%d,%d cam=%d,%d,%d/%d,%d,%d fade=%d/%d cmode=%d\n",
				 frame, (int)(driver->posCurr.x >> 8), (int)(driver->posCurr.y >> 8), (int)(driver->posCurr.z >> 8),
				 (int)driver->velocity.x, (int)driver->velocity.y, (int)driver->velocity.z,
				 (int)driver->AxisAngle2_normalVec.x, (int)driver->AxisAngle2_normalVec.y, (int)driver->AxisAngle2_normalVec.z,
				 (int)driver->rotCurr.x, (int)driver->rotCurr.y, (int)driver->rotCurr.z, (int)driver->speedApprox,
				 (unsigned)driver->botData.botNavFrame, (int)driver->botData.botPath, (unsigned)driver->stepFlagSet,
				 (int)driver->instSelf->matrix.t[0], (int)driver->instSelf->matrix.t[1], (int)driver->instSelf->matrix.t[2],
				 (int)pb->pos.x, (int)pb->pos.y, (int)pb->pos.z, (int)pb->rot.x, (int)pb->rot.y, (int)pb->rot.z,
				 (int)pb->fadeFromBlack_currentValue, (int)pb->fadeFromBlack_desiredResult, (int)tracker->cameraDC[0].cameraMode);
		}
	}
	if ((u32)(sdata->gGT->levelID - INTRO_RACE_TODAY) >= 9)
		return;
	if (lastFrame != (int)sdata->frameCounter)
	{
		lastFrame = (int)sdata->frameCounter;
		frames++;
	}
	if (frames <= 420 || ((int)sdata->frameCounter >= 3000 && (int)sdata->frameCounter <= 4200))
		Platform_Log("[probe] hb intro f=%d lvl=%d step=%s bucket=%d queue=%d ready=%d load=%d\n", lastFrame,
		             (int)sdata->gGT->levelID, step, bucket, (int)sdata->queueLength,
		             (int)sdata->queueReady, (int)sdata->load_inProgress);
#else
	(void)step;
	(void)bucket;
#endif
}

void MainFrame_GameLogic(struct GameTracker *gGT, struct GamepadSystem *gGamepads)
{
	b32 wasPausedAtFrameStart;
	s16 sVar2;
	u32 uVar3;
	int iVar4;
	DriverFunc pcVar5;
	u32 uVar5;
	struct Driver *psVar8;
	struct Driver *psVar9;
	struct PushBuffer *pushBuffer;
	int iVar11;
	struct Thread *psVar12;
	MainFrame_TraceIntroStep("game-enter", -1);
	{ static int s_g1 = 0; if ((((gGT->gameMode1) & GAME_MODE_MENU_OR_CUTSCENE_MASK) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_g1++; if (s_g1 < 400) { Platform_Log("[probe] g1m f=%d mode1=%08x\n", (int)sdata->frameCounter, (unsigned)gGT->gameMode1); } } else if ((sdata->frameCounter % 60) == 0) { Platform_Log("[probe] g1 f=%d\n", (int)sdata->frameCounter); } }

	wasPausedAtFrameStart = true;
	if ((gGT->gameMode1 & PAUSE_ALL) == 0)
	{
		wasPausedAtFrameStart = false;
		pushBuffer = gGT->pushBuffer;
		{ static int s_pa = 0; if ((((gGT->gameMode1) & 0x2000) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_pa++; if (s_pa < 400) { Platform_Log("[probe] pa f=%d \n", (int)sdata->frameCounter); } } }
		for (psVar12 = gGT->threadBuckets[0].thread; psVar12 != 0; psVar12 = psVar12->siblingThread)
		{
			psVar9 = (struct Driver *)psVar12->object;

			if (psVar9->clockSend)
			{
				psVar9->clockSend--;
			}
			uVar3 = psVar9->clockFlash;
			if (uVar3 == 0)
			{
				if (psVar9->clockReceive == 0)
				{
					uVar3 = (u32)psVar9->clockSend;
					if (uVar3 == 0)
					{
						if ((gGT->clockEffectEnabled & 1) == 0)
						{
							goto LAB_80034e74;
						}
						uVar3 = 10000;
					}
				}
				else
				{
					if ((psVar9->actionsFlagSet & ACTION_RACE_FINISHED) != 0)
					{
						psVar9->clockReceive = 0;
					}
					uVar3 = (u32)psVar9->clockReceive;
				}

#if defined(CTR_NATIVE)
				DISPLAY_Blur_Main(pushBuffer, uVar3);
#endif
			}
			else
			{
#if defined(CTR_NATIVE)
				DISPLAY_Blur_Main(pushBuffer, -uVar3);
#endif
				psVar9->clockFlash--;
			}
		LAB_80034e74:
			pushBuffer = pushBuffer + 1;
		}
		{ static int s_pd = 0; if ((((gGT->gameMode1) & 0x2000) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_pd++; if (s_pd < 400) { Platform_Log("[probe] pd f=%d \n", (int)sdata->frameCounter); } } }
		gGT->timer = gGT->timer + 1;
		gGT->framesInThisLEV = gGT->framesInThisLEV + 1;
		gGT->unk1cc4[4] = 0;
		{ static int s_pe = 0; if ((((gGT->gameMode1) & 0x2000) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_pe++; if (s_pe < 400) { Platform_Log("[probe] pe f=%d \n", (int)sdata->frameCounter); } } }

		iVar4 = Timer_GetTime_Elapsed(gGT->clockFrameStart, &gGT->clockFrameStart);
		{ static int s_pf = 0; if ((((gGT->gameMode1) & 0x2000) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_pf++; if (s_pf < 400) { Platform_Log("[probe] pf f=%d iVar4=%d\n", (int)sdata->frameCounter, (int)iVar4); } } }
		iVar4 = (iVar4 << 5) / 100;

		gGT->elapsedTimeMS = iVar4;
		if (iVar4 < 0)
		{
			gGT->elapsedTimeMS = 0x20;
		}
		if (0x40 < gGT->elapsedTimeMS)
		{
			gGT->elapsedTimeMS = 0x40;
		}
		if ((gGT->gameMode1_prevFrame & PAUSE_ALL) != 0)
		{
			gGT->elapsedTimeMS = 0x20;
		}
#if defined(CTR_NATIVE) && defined(CTR_INTERNAL)
		// NOTE(aalhendi): Replay playback must not let host RCNT timing decide
		// cutscene/gameplay advancement. Use the recorded PS1-shaped frame delta
		// before msInThisLEV and elapsedEventTime consume it.
		NativeReplayScheduler_ConsumeFrameElapsedTimeMS(&gGT->elapsedTimeMS);
#endif
		gGT->msInThisLEV += gGT->elapsedTimeMS;
		if (gGT->trafficLightsTimer < 1)
		{
			if ((gGT->gameMode1 & DEBUG_MENU) == 0)
			{
				if (gGT->frozenTimeRemaining < 1)
				{
					if ((gGT->gameMode1 & END_OF_RACE) == 0)
					{
						gGT->elapsedEventTime += gGT->elapsedTimeMS;
					}
				}
				else
				{
					iVar4 = gGT->frozenTimeRemaining - gGT->elapsedTimeMS;
					gGT->frozenTimeRemaining = iVar4;
					if (iVar4 < 0)
					{
						gGT->frozenTimeRemaining = 0;
					}
					else
					{
						uVar3 = gGT->timer;
						if (uVar3 == (uVar3 / 6) * 6)
						{
							if (uVar3 == (uVar3 / 0xc) * 0xc)
							{
								OtherFX_Play_LowLevel(0x40, '\0', 0x8c9080);
							}
							else
							{
								OtherFX_Play_LowLevel(0x40, '\0', 0x8c8880);
							}
						}
					}
				}
			}
		}
		else
		{
			gGT->elapsedEventTime = 0;
		}

		MainFrame_TraceIntroStep("cycle-player", -1);
		CTR_CycleTex_AllModels(-1, (struct Model **)sdata->PLYROBJECTLIST, gGT->timer);
		{ static int s_pg = 0; if ((((gGT->gameMode1) & 0x2000) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_pg++; if (s_pg < 400) { Platform_Log("[probe] pg f=%d plyrlist=%08x\n", (int)sdata->frameCounter, (unsigned)(u32)sdata->PLYROBJECTLIST); } } }
		MainFrame_TraceIntroStep("cycle-level", -1);
		CTR_CycleTex_AllModels(gGT->level1->numModels, gGT->level1->ptrModelsPtrArray, gGT->timer);
		{ static int s_g2 = 0; if ((((gGT->gameMode1) & GAME_MODE_MENU_OR_CUTSCENE_MASK) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_g2++; if (s_g2 < 400) { Platform_Log("[probe] g2m f=%d lvl1=%08x numModels=%d arr=%08x\n", (int)sdata->frameCounter, (unsigned)(u32)gGT->level1, (int)((gGT->level1 != NULL) ? gGT->level1->numModels : -999), (unsigned)(u32)((gGT->level1 != NULL) ? (u32)gGT->level1->ptrModelsPtrArray : 0)); } } }

		psVar8 = 0;
		psVar9 = 0;

#if defined(CTR_NATIVE)
		for (psVar12 = gGT->threadBuckets[0].thread; psVar12 != 0; psVar12 = psVar12->siblingThread)
		{
			struct Driver *currentDriver = psVar12->object;

			if (currentDriver->driverID == 0)
			{
				psVar8 = currentDriver;
				continue;
			}

			if (currentDriver->driverID == 1)
			{
				psVar9 = currentDriver;
			}

			// NOTE(aalhendi): Retail may read PSX low memory before driver 0 appears.
			if (psVar8 == NULL)
			{
				continue;
			}

			if (currentDriver->numTimesAttacking < psVar8->numTimesAttacking)
			{
				psVar9 = psVar8;
				psVar8 = currentDriver;
			}
		}
#endif

		{ static int s_g3 = 0; if ((((gGT->gameMode1) & GAME_MODE_MENU_OR_CUTSCENE_MASK) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_g3++; if (s_g3 < 400) { Platform_Log("[probe] g3m f=%d\n", (int)sdata->frameCounter); } } }
		if (((psVar8 != 0) && (psVar9 != 0)) && (iVar4 = (u32)psVar9->numTimesAttacking - (u32)psVar8->numTimesAttacking, psVar8->quip2 < iVar4))
		{
			psVar8->quip2 = (s16)iVar4;
		}

		{ static int s_g4 = 0; if ((((gGT->gameMode1) & GAME_MODE_MENU_OR_CUTSCENE_MASK) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_g4++; if (s_g4 < 400) { Platform_Log("[probe] g4m f=%d\n", (int)sdata->frameCounter); } } }
		for (iVar4 = 0; iVar4 < PAUSE; iVar4++)
		{
			if ((((gGT->gameMode1 & DEBUG_MENU) == 0) || ((gGT->threadBuckets[iVar4].boolCantPause & 1) != 0)) &&

			    // if threads exist
			    (gGT->threadBuckets[iVar4].thread != 0))
			{
				if (iVar4 == 0)
				{
					for (psVar12 = gGT->threadBuckets[iVar4].thread; psVar12 != 0; psVar12 = psVar12->siblingThread)
					{
						VehPickupItem_ShootOnCirclePress((struct Driver *)psVar12->object);
					}

					// run all driver funcPtrs,
					// all drivers must run the same DRIVER_FUNC_* stage
					// at the same time, that's why the stages exist
					for (iVar11 = 0; iVar11 < DRIVER_FUNC_COUNT; iVar11++)
					{
						for (psVar12 = gGT->threadBuckets[iVar4].thread; psVar12 != 0; psVar12 = psVar12->siblingThread)
						{
							// if PLYR converted to robotcar at end of race,
							// dont run funcPtrs from inside driver struct
							if (psVar12->funcThTick != 0)
							{
								continue;
							}

							psVar9 = (struct Driver *)psVar12->object;

							pcVar5 = psVar9->funcPtrs[iVar11];

							if (pcVar5 != 0)
							{
								pcVar5(psVar12, psVar9);
							}
						}
					}
				}

				MainFrame_TraceIntroStep("bucket-enter", iVar4);
				ThTick_RunBucket(gGT->threadBuckets[iVar4].thread);
				MainFrame_TraceIntroStep("bucket-exit", iVar4);
			}
		}

		{ static int s_g5 = 0; if ((((gGT->gameMode1) & GAME_MODE_MENU_OR_CUTSCENE_MASK) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_g5++; if (s_g5 < 400) { Platform_Log("[probe] g5m f=%d\n", (int)sdata->frameCounter); } } }
#if defined(CTR_NATIVE)
		MainFrame_TraceIntroStep("bots-enter", -1);
		BOTS_UpdateGlobals();
		MainFrame_TraceIntroStep("bots-exit", -1);
#endif
		GhostTape_WriteMoves(0);
		gGT->unk1cc4[4] = (u32)(gGT->unk1cc4[4] * 10000) / 0x147e;

#if defined(CTR_NATIVE)


		Particle_UpdateAllParticles();

#endif
	}
	else
	{
		psVar12 = gGT->threadBuckets[AKUAKU].thread;
		if (psVar12 != 0)
		{
			ThTick_RunBucket(psVar12);
		}
	}

	uVar5 = LOAD_IsOpen_RacingOrBattle();
	if (uVar5 != 0)
	{
#if defined(CTR_NATIVE)
		if ((gGT->gameMode1 & PAUSE_ALL) == 0)
		{
			RB_Bubbles_RoosTubes();
		}
#endif
		if (gGT->threadBuckets[BURST].thread != 0)
		{
			RB_Burst_DrawAll(gGT);
		}
	}

	PROC_CheckAllForDead();
	{ static int s_g6 = 0; if ((((gGT->gameMode1) & GAME_MODE_MENU_OR_CUTSCENE_MASK) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_g6++; if (s_g6 < 400) { Platform_Log("[probe] g6m f=%d\n", (int)sdata->frameCounter); } } }

	if ((gGT->gameMode1 & PAUSE_ALL) == 0)
	{
		MainFrame_TraceIntroStep("audio-enter", -1);
		Audio_Update1();
		MainFrame_TraceIntroStep("audio-exit", -1);
	}

	gGT->gameMode1_prevFrame = gGT->gameMode1;
	uVar5 = GAMEPAD_GetNumConnected(gGamepads);
	MainFrame_TraceIntroStep("pad-exit", -1);
	{ static int s_g7 = 0; if ((((gGT->gameMode1) & GAME_MODE_MENU_OR_CUTSCENE_MASK) != 0) && (((gGT->gameMode1) & 0x40000000) == 0)) { s_g7++; if (s_g7 < 400) { Platform_Log("[probe] g7m f=%d\n", (int)sdata->frameCounter); } } }
	uVar3 = gGT->gameMode1;

	if ((uVar3 & END_OF_RACE) == 0)
	{
		if (wasPausedAtFrameStart || ((uVar3 & PAUSE_ALL) != 0))
		{
			if (gGT->cooldownfromPauseUntilUnpause == 0)
			{
				if (((sdata->ptrActiveMenu != &data.menuRacingWheelConfig) && (sdata->ptrActiveMenu != &D232.menuHintMenu) // in 232
				     ) &&
				    ((sdata->AnyPlayerTap & BTN_START) != 0))
				{
					RECTMENU_ClearInput();
					gGT->gameMode1 &= ~PAUSE_1;

					MainFrame_TogglePauseAudio(0);
					OtherFX_Play(1, 1);

					MainFreeze_SafeAdvDestroy();
					ElimBG_Deactivate(gGT);

					RECTMENU_Hide(sdata->ptrActiveMenu);
					gGT->cooldownFromUnpauseUntilPause = 5;
				}
			}
			else
			{
				gGT->cooldownfromPauseUntilUnpause--;
			}
		}
		else if (gGT->cooldownFromUnpauseUntilPause == 0)
		{
			if ((uVar3 & (GAME_CUTSCENE | END_OF_RACE | MAIN_MENU)) == 0)
			{
				if (sdata->ptrActiveMenu == 0)
				{
					if (sdata->AkuAkuHintState == 0)
					{
						if (!RaceFlag_IsFullyOnScreen())
						{
							for (iVar4 = 0; iVar4 < gGT->numPlyrCurrGame; iVar4++)
							{
								if ((((uVar5 != 0) && ((
#if defined(CTR_NATIVE)
								                          !MainFrame_HaveAllPads((u16)gGT->numPlyrNextGame) &&
#endif
								                          ((gGT->gameMode1 & PAUSE_ALL) == 0)))) ||
								     ((gGamepads->gamepad[iVar4].buttonsTapped & BTN_START) != 0)) &&
								    (gGT->overlayIndex_Threads != OVERLAY_INDEX_NONE))
								{
									// NOTE(aalhendi): Retail writes this before freezing the game for pause.
									gGT->gameModeEnd = (gGT->gameMode1 & GAME_MODE_END_RETAINED_MODE_MASK) | PAUSE_1;

									MainFreeze_IfPressStart();

									gGT->cooldownfromPauseUntilUnpause = 5;
								}
							}
						}
					}
				}
			}
		}
		else
		{
			gGT->cooldownFromUnpauseUntilPause--;
		}
	}
	else if (gGT->timerEndOfRaceVS == 0)
	{
		uVar3 = gGT->gameModeEnd;
		if ((uVar3 & AKU_SONG) == 0)
		{
			if ((uVar3 & CRYSTAL_CHALLENGE) == 0)
			{
				if (gGT->unk_timerCooldown_similarTo_1d36 == 0)
				{
					return;
				}
			}
			else if (gGT->unk_timerCooldown_similarTo_1d36 == 0)
			{
				if ((uVar3 & PAUSE_2) == 0)
				{
					return;
				}

				sVar2 = SubmitName_DrawMenu(0x140);

				// if not done yet
				if (sVar2 == 0)
				{
					return;
				}


#if defined(CTR_NATIVE)

				// if SAVE
				if (sVar2 == 1)
				{
					sdata->boolSaveCupProgress = 0;

					SelectProfile_ToggleMode(SELECT_PROFILE_MODE_SLOT_SAVE);

					RECTMENU_Show(&data.menuWarning2);
					gGT->gameModeEnd |= NEW_NAME;

					return;
				}
#endif

				// if -1 (cancel)
				gGT->newHighScoreIndex = -1;
				gGT->gameModeEnd &= ~(NEW_BEST_LAP | NEW_HIGH_SCORE);
				return;
			}
			gGT->unk_timerCooldown_similarTo_1d36--;
		}
	}
	else if ((uVar3 & ARCADE_MODE) == 0)
	{
		if (gGT->timerEndOfRaceVS < 0x96)
		{
#if defined(CTR_NATIVE)
			UI_VsQuipDrawAll();
			UI_VsWaitForPressX();
#endif
		}
		if (0x1e < gGT->timerEndOfRaceVS)
		{
			gGT->timerEndOfRaceVS--;
		}
	}
	else
	{
		gGT->timerEndOfRaceVS = 0;
	}
	MainFrame_TraceIntroStep("game-exit", -1);
	return;
}

void MainFrame_InitVideoSTR(u32 boolPlayVideoStr, RECT *r, s16 posX, s16 posY)
{
#ifdef CTR_NATIVE
	if (r == NULL)
	{
		// NOTE(aalhendi): Native overlay 230 uses NULL to disable STR copy;
		// retail blindly copies the RECT fields in the PSX path below.
		sdata->videoSTR_src_vramRect.x = 0;
		sdata->videoSTR_src_vramRect.y = 0;
		sdata->videoSTR_src_vramRect.w = 0;
		sdata->videoSTR_src_vramRect.h = 0;
	}
	else
#endif
	{
		sdata->videoSTR_src_vramRect.x = r->x;
		sdata->videoSTR_src_vramRect.y = r->y;
		sdata->videoSTR_src_vramRect.w = r->w;
		sdata->videoSTR_src_vramRect.h = r->h;
	}

	sdata->boolPlayVideoSTR = boolPlayVideoStr;
	sdata->videoSTR_dst_vramX = posX;
	sdata->videoSTR_dst_vramY = posY;
}

b32 MainFrame_HaveAllPads(s16 numPlyrNextGame)
{
	// if game is not loading
	if (sdata->Loading.stage == LOAD_IDLE)
	{
		struct GamepadBuffer *gb = &sdata->gGamepads->gamepad[0];

		if (numPlyrNextGame == 0)
		{
			return false;
		}

		for (int i = 0; i < numPlyrNextGame; i++)
		{
			struct ControllerPacket *packet = gb->ptrControllerPacket;

			if (packet == NULL)
			{
				return false;
			}
			if (packet->plugged != PLUGGED)
			{
				return false;
			}

			gb++;
		}
	}

	return true;
}

static void MainFrame_ReplacePackedVisList(int *dst, void *src, int byteCount)
{
	u32 srcWord = (u32)src;
	MainFrame_TraceIntroStep("vis-replace-enter", -1);
#ifdef CTR_NATIVE
	if (sdata->gGT->levelID == CRASH_COVE && sdata->gGT->framesInThisLEV < 3)
		Platform_Log("[probe] hb vis-replace f=%d dst=%08x src=%08x bytes=%d\n", (int)sdata->frameCounter, (unsigned)(u32)dst, (unsigned)srcWord, byteCount);
#endif

	if ((srcWord & 1) == 0)
	{
		memcpy(dst, src, byteCount);
		MainFrame_TraceIntroStep("vis-replace-exit", -1);
		return;
	}

	CTR_unknownMaybeThunk1(dst, (void *)(srcWord & ~(u32)3));
	MainFrame_TraceIntroStep("vis-replace-exit", -1);
}

static void MainFrame_OrPackedVisList(int *dst, void *src, int byteCount)
{
	u32 srcWord = (u32)src;

	if ((srcWord & 1) == 0)
	{
		CTR_unknownMaybeThunk3(dst, src, byteCount);
		return;
	}

	CTR_unknownMaybeThunk2(dst, (void *)(srcWord & ~(u32)3));
}

static int MainFrame_VisMemHasQuad(const int *visFaceList, const struct QuadBlock *quad, const struct mesh_info *mesh)
{
	int quadIndex = (int)(quad - mesh->ptrQuadBlockArray);

	return (CTR_ReadU32LE(&visFaceList[quadIndex >> 5]) & (1u << (quadIndex & 0x1f))) != 0;
}

static void MainFrame_VisMemAddDriverPVS(struct GameTracker *gGT, int playerIndex)
{
	struct Driver *driver = gGT->drivers[playerIndex];
	struct mesh_info *mesh = gGT->level1->ptr_mesh_info;
	struct QuadBlock *quad = driver->underDriver;
	struct PVS *pvs;

	if (quad == NULL)
	{
		return;
	}

	pvs = quad->pvs;
	if (pvs == NULL)
	{
		return;
	}

	if (pvs->visLeafSrc != NULL)
	{
		MainFrame_OrPackedVisList(gGT->visMem1->visLeafList[playerIndex], pvs->visLeafSrc, ((mesh->numBspNodes + 0x1f) >> 5) << 2);
	}

	if (pvs->visFaceSrc != NULL)
	{
		MainFrame_OrPackedVisList(gGT->visMem1->visFaceList[playerIndex], pvs->visFaceSrc, ((mesh->numQuadBlock + 0x1f) >> 5) << 2);
	}
}

void MainFrame_VisMemFullFrame(struct GameTracker *gGT, struct Level *level)
{
	struct VisMem *visMem;
	struct mesh_info *mesh;
	int playerIndex;

	visMem = gGT->visMem1;
	if (visMem == NULL)
	{
		return;
	}

	if (level == NULL)
	{
		return;
	}

	if (gGT->numPlyrCurrGame == 0)
	{
		return;
	}

	mesh = level->ptr_mesh_info;

	for (playerIndex = 0; playerIndex < gGT->numPlyrCurrGame; playerIndex++)
	{
		struct CameraDC *camDC = &gGT->cameraDC[playerIndex];
		struct Driver *driver = gGT->drivers[playerIndex];
		struct QuadBlock *driverQuad = driver->underDriver;
		struct PVS *driverPVS = NULL;

		if (driverQuad != NULL)
		{
			driverPVS = driverQuad->pvs;
		}

		camDC->flags &= ~0x4000;

		if (camDC->visLeafSrc == NULL)
		{
			if ((driverPVS != NULL) && (driverPVS->visLeafSrc != NULL))
			{
				visMem->visLeafSrc[playerIndex] = driverPVS->visLeafSrc;
				MainFrame_ReplacePackedVisList(visMem->visLeafList[playerIndex], driverPVS->visLeafSrc, ((mesh->numBspNodes + 0x1f) >> 5) << 2);
			}
		}
		else if (visMem->visLeafSrc[playerIndex] != camDC->visLeafSrc)
		{
			visMem->visLeafSrc[playerIndex] = camDC->visLeafSrc;
			MainFrame_ReplacePackedVisList(visMem->visLeafList[playerIndex], camDC->visLeafSrc, ((mesh->numBspNodes + 0x1f) >> 5) << 2);
		}

		if (camDC->visFaceSrc == NULL)
		{
			if ((driverPVS != NULL) && (driverPVS->visFaceSrc != NULL))
			{
				visMem->visFaceSrc[playerIndex] = driverPVS->visFaceSrc;
				MainFrame_ReplacePackedVisList(visMem->visFaceList[playerIndex], driverPVS->visFaceSrc, ((mesh->numQuadBlock + 0x1f) >> 5) << 2);
			}
		}
		else if (visMem->visFaceSrc[playerIndex] != camDC->visFaceSrc)
		{
			visMem->visFaceSrc[playerIndex] = camDC->visFaceSrc;
			MainFrame_ReplacePackedVisList(visMem->visFaceList[playerIndex], camDC->visFaceSrc, ((mesh->numQuadBlock + 0x1f) >> 5) << 2);

			if ((driverPVS == NULL) || (driverPVS->visLeafSrc == NULL) || (driverPVS->visFaceSrc == NULL) || (driverPVS->visInstSrc == NULL) ||
			    MainFrame_VisMemHasQuad(visMem->visFaceList[playerIndex], driverQuad, mesh))
			{
				camDC->flags &= ~0x2000;
			}
			else
			{
				camDC->flags |= 0x2000;
			}

			if ((camDC->flags & 0x2000) != 0)
			{
				MainFrame_VisMemAddDriverPVS(gGT, playerIndex);
				camDC->flags |= 0x4000;
			}
		}

		if ((camDC->flags & 0x5000) == 0x1000)
		{
			MainFrame_VisMemAddDriverPVS(gGT, playerIndex);
		}

		if ((camDC->cameraMode == 0) && ((camDC->flags & 0x2000) != 0) && (driverPVS != NULL) && (driverPVS->visInstSrc != NULL))
		{
			camDC->visInstSrc = driverPVS->visInstSrc;
		}

		if ((level->configFlags & 4) == 0)
		{
			if (visMem->visOVertSrc[playerIndex] != camDC->visOVertSrc)
			{
				visMem->visOVertSrc[playerIndex] = camDC->visOVertSrc;
				MainFrame_ReplacePackedVisList(visMem->visOVertList[playerIndex], camDC->visOVertSrc, ((level->numWaterVertices + 0x1f) >> 5) << 2);
			}
			else if (visMem->visOVertSrc[playerIndex] == NULL)
			{
				memcpy(visMem->visOVertList[playerIndex], level->visOVertSrc, ((level->numWaterVertices + 0x1f) >> 5) << 2);
			}
		}
		else
		{
			if (visMem->visSCVertSrc[playerIndex] != camDC->visSCVertSrc)
			{
				visMem->visSCVertSrc[playerIndex] = camDC->visSCVertSrc;
				MainFrame_ReplacePackedVisList(visMem->visSCVertList[playerIndex], camDC->visSCVertSrc, ((level->numSCVert + 0x1f) >> 5) << 2);
			}
			else if (visMem->visSCVertSrc[playerIndex] == NULL)
			{
				memcpy(visMem->visSCVertList[playerIndex], level->visSCVertSrc, ((level->numSCVert + 0x1f) >> 5) << 2);
			}
		}
	}
}

// Request Aku Hint, doesn't start till FUN_800b3dd8
// hintId:
//	0x00 - Welcome to Adventure Arena
//	0x01 - using a warp pad (part of welcome)
// 	0x02 - Need more trophies
//	0x03 - Need 4 trophies for Boss
//	0x04 - Need 4 keys for oxide
//	0x05 - Must have 1 Boss Key
//	0x06 - This is the load/save screen
// 	0x07 - Congrats on opening new area
//	0x12 - Must have 2 Boss Key
//	0x19 - Collect every crystal in arena
//	0x1a - CTR Token
//	0x1b - Gem Cups
//	0x1c - Must get 10 relics
//	0x1d - Relic
// param2:
//	0x00 - not interrupting a warppad load screen
// 	0x01 - interrupting (CTR, Relic, or Crystal hints)
void MainFrame_RequestMaskHint(s16 hintId, s16 interruptWarpPad)
{
	struct GameTracker *gGT = sdata->gGT;

	if (((gGT->gameMode1 & PAUSE_ALL) == 0) && (sdata->AkuHint_RequestedHint == -1))
	{
		sdata->AkuAkuHintState = 1;

		gGT->drivers[0]->funcPtrs[DRIVER_FUNC_INIT] = VehPhysProc_FreezeEndEvent_Init;

		sdata->AkuHint_RequestedHint = hintId;
		sdata->AkuHint_boolInterruptWarppad = interruptWarpPad;
	}
	return;
}
