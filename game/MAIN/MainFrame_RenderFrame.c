#include <common.h>

#if defined(CTR_NATIVE) && defined(CTR_INTERNAL)
#include <platform/native_perf.h>
#define MAINFRAME_PERF_BEGIN(bucket) NativePerf_BeginScope(bucket)
#define MAINFRAME_PERF_END(bucket)   NativePerf_EndScope(bucket)
#else
#define MAINFRAME_PERF_BEGIN(bucket) ((void)0)
#define MAINFRAME_PERF_END(bucket)   ((void)0)
#endif

#ifdef CTR_INTERNAL
volatile int gCtrDebugSkipLevelGeometry = 0;
#endif

static void MainFrame_TraceLateRender(const char *step)
{
#ifdef CTR_NATIVE
	static int demoStart = -1;
	if (!Platform_TraceEnabled(CTR_TRACE_WATCH)) return;
	if (sdata->gGT->levelID == CRASH_COVE && sdata->Loading.stage == LOAD_IDLE)
	{
		int frame = (int)sdata->frameCounter;
		if (demoStart < 0) demoStart = frame;
		if (frame - demoStart <= 1200)
			Platform_Log("[probe] hb demo-render f=%d age=%d step=%s demo=%d\n", frame, frame - demoStart, step, (int)sdata->gGT->boolDemoMode);
	}
	if ((sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722) ||
	    (sdata->frameCounter >= 3500 && sdata->frameCounter <= 3600))
		Platform_Log("[probe] hb render f=%d step=%s\n", (int)sdata->frameCounter, step);
#endif
}

void MainFrame_RenderFrame(struct GameTracker *gGT, struct GamepadSystem *gGamepads)
{
	struct Level *lev = gGT->level1;
	struct mesh_info *ptr_mesh_info = 0;
	MainFrame_TraceLateRender("enter");

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_SETUP);
	DrawUnpluggedMsg(gGT, gGamepads);
	MainFrame_TraceLateRender("unplugged-exit");
	DrawFinalLap(gGT);
	MainFrame_TraceLateRender("final-lap-exit");

	ElimBG_HandleState(gGT);
	MainFrame_TraceLateRender("elim-bg-exit");

	if (lev != 0)
	{
		ptr_mesh_info = lev->ptr_mesh_info;
	}
	{ static int s_rf = 0; if ((s_rf++ % 10) == 0) { Platform_Log("[probe] rf-in f=%d flags=%08x lev=%08x mesh=%08x\n", (int)sdata->frameCounter, (unsigned)gGT->renderFlags, (unsigned)(u32)lev, (unsigned)(u32)ptr_mesh_info); } }

	if ((gGT->renderFlags & RENDER_FLAG_VISMEM_REFRESH_MASK) != 0)
	{
		MainFrame_TraceLateRender("visibility-enter");
		MainFrame_VisMemFullFrame(gGT, gGT->level1);
		MainFrame_TraceLateRender("visibility-exit");
	}


	if ((gGT->renderFlags & RENDER_FLAG_DRAW_LEVEL) != 0)
	{
		if (gGT->visMem1 != 0)
		{
			if (lev != 0)
			{
				MainFrame_TraceLateRender("texture-cycle-enter");
				CTR_CycleTex_LEV(lev->ptr_anim_tex, gGT->timer);
				MainFrame_TraceLateRender("texture-cycle-exit");
			}
		}
	}

	if ((sdata->ptrActiveMenu != 0) || ((gGT->gameMode1 & END_OF_RACE) != 0))
	{
		RECTMENU_CollectInput();
	}

	if (sdata->ptrActiveMenu != 0)
	{
		if (sdata->Loading.stage == LOAD_IDLE)
		{
			RECTMENU_ProcessState();
		}
	}

	MainFrame_TraceLateRender("menu-exit");
	RainLogic(gGT);
	MainFrame_TraceLateRender("rain-exit");
	DropRain_MakeSound(gGT);
	MenuHighlight();
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_SETUP);
	MainFrame_TraceLateRender("setup-exit");

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);
	RenderAllWeather(gGT);
	RenderAllConfetti(gGT);
	if (((gGT->renderFlags & RENDER_FLAG_STARS) != 0) && (gGT->stars.numStars != 0))
	{
		RenderStars(&gGT->pushBuffer[0], &gGT->backBuffer->primMem, &gGT->stars, gGT->numPlyrCurrGame);
	}

	if (((gGT->renderFlags & RENDER_FLAG_MULTIPLAYER_DECALS) != 0) && (gGT->numPlyrCurrGame > 1))
	{
		DecalMP_01(gGT);
	}
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_HUD);
	RenderAllHUD(gGT);
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_HUD);

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);
	RenderAllBeakerRain(gGT);

	RenderAllBoxSceneSplitLines(gGT);
	MainFrame_TraceLateRender("effects-exit");
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_QUEUE_INSTANCES);
	RenderBucket_QueueAllInstances(gGT);
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_QUEUE_INSTANCES);

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);
	RenderAllNormalParticles(gGT);

	RenderDispEnv_World(gGT); // == RenderDispEnv_World ==

	if (((gGT->renderFlags & RENDER_FLAG_MULTIPLAYER_DECALS) != 0) && (gGT->numPlyrCurrGame > 1))
	{
		DecalMP_02(gGT);
	}

	RenderAllFlag0x40(gGT); // I need a better name
	RenderAllTitleDPP(gGT);
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_EXECUTE_INSTANCES);
	RenderBucket_ExecuteAllInstances(gGT);
	MainFrame_TraceLateRender("instances-exit");
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_EXECUTE_INSTANCES);

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);
	RenderAllTires(gGT);
	MainFrame_TraceLateRender("tires-exit");

	RenderAllShadows(gGT);
	MainFrame_TraceLateRender("shadows-exit");

	RenderAllHeatParticles(gGT);
	MainFrame_TraceLateRender("heat-exit");

	PushBuffer_FadeAllWindows();
	MainFrame_TraceLateRender("fade-exit");
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_EFFECTS);

	if (((gGT->renderFlags & RENDER_FLAG_DRAW_LEVEL) != 0) && (ptr_mesh_info != 0))
	{
#ifdef CTR_INTERNAL
		if (gCtrDebugSkipLevelGeometry == 0)
#endif
		{
			MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_LEVEL_GEOMETRY);
			{ static int s_lg = 0; if ((s_lg++ % 10) == 0) { Platform_Log("[probe] lg-in f=%d nq=%d nv=%d nb=%d bsp=%08x\n", (int)sdata->frameCounter, (int)ptr_mesh_info->numQuadBlock, (int)ptr_mesh_info->numVertex, (int)ptr_mesh_info->numBspNodes, (unsigned)(u32)ptr_mesh_info->bspRoot); } }
			MainFrame_TraceLateRender("geometry-enter");
			RenderAllLevelGeometry(gGT, lev, ptr_mesh_info);
			MainFrame_TraceLateRender("geometry-exit");
			{ static int s_lx = 0; if ((s_lx++ % 10) == 0) { Platform_Log("[probe] lg-out f=%d\n", (int)sdata->frameCounter); } }
			MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_LEVEL_GEOMETRY);
		}

		MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_POST_LEVEL);
		RenderDispEnv_World(gGT); // == RenderDispEnv_World ==

		if (((gGT->hudFlags & HUD_FLAG_RACE_HUD) != 0) && (gGT->numPlyrCurrGame > 1))
		{
			UI_RenderFrame_Wumpa3D_2P3P4P(gGT);
		}

		if (((gGT->renderFlags & RENDER_FLAG_MULTIPLAYER_DECALS) != 0) && (gGT->numPlyrCurrGame > 1))
		{
			DecalMP_03(gGT);
		}

		int dotLightsLoadReady = sdata->Loading.stage != LOAD_REQUESTED;

		if (
		    // if not cutscene
		    // if not in adventure arena
		    // if not in main menu
		    ((gGT->gameMode1 & (GAME_CUTSCENE | ADVENTURE_ARENA | MAIN_MENU)) == 0) && dotLightsLoadReady)
		{
			DotLights_AudioAndVideo(gGT);
		}

		if ((gGT->renderFlags & RENDER_FLAG_SPLIT_SCREEN_LINES) != 0)
		{
			WindowBoxLines(gGT);

			WindowDivsionLines(gGT);
		}

		// if game is not loading
		if (sdata->Loading.stage == LOAD_IDLE)
		{
			// If game is not paused
			if ((gGT->gameMode1 & PAUSE_ALL) == 0)
			{
				PickupBots_Update();
			}

#if defined(CTR_NATIVE)
			// NOTE(aalhendi): Native menu/adventure-hub LEVs may publish no
			// restart table. Retail lap stats assume the table exists whenever
			// this caller reaches them; keep the retail lap path intact.
			if ((gGT->level1 != NULL) && (gGT->level1->ptr_restart_points != NULL) && (gGT->level1->cnt_restart_points != 0))
			{
				PlayLevel_UpdateLapStats();
			}
#else
			PlayLevel_UpdateLapStats();
#endif
		}
		MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_POST_LEVEL);
	}

	MainFrame_TraceLateRender("level-exit");
	// If in main menu, or in adventure arena,
	// or in End-Of-Race menu
	if ((gGT->gameMode1 & (ADVENTURE_ARENA | END_OF_RACE | MAIN_MENU)) != 0)
	{
		MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_REFRESHCARD);
		RefreshCard_Entry();
		MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_REFRESHCARD);
	}

	// clear swapchain
	if (((gGT->renderFlags & RENDER_FLAG_CLEAR_BACK_BUFFER) != 0) && ((lev->clearColor[0].enable != 0) || (lev->clearColor[1].enable != 0)))
	{
		MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_CLEAR_SCREEN);
		CAM_ClearScreen(gGT);
		MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_CLEAR_SCREEN);
	}

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_UI);
	if ((gGT->renderFlags & RENDER_FLAG_CHECKERED_FLAG) != 0)
	{
		RaceFlag_DrawSelf();
#ifdef _XBOX
		if (RaceFlag_GetCanDraw())
		{
			/* A copied UI rectangle selects the full-width environment while
			 * leaving the normal HUD/text environment on the original buffer.
			 * OT insertion is reversed: this packet runs before the flag. */
			struct PushBuffer flagBuffer = gGT->pushBuffer_UI;
			PushBuffer_SetDrawEnv_Normal(RaceFlag_GetOT(), &flagBuffer, gGT->backBuffer, NULL, 0);
		}
#endif
	}

	RenderDispEnv_UI(gGT);
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_UI);

	MAINFRAME_PERF_BEGIN(NATIVE_PERF_BUCKET_MAINFRAME_RENDER_VSYNC);
	MainFrame_TraceLateRender("vsync-enter");
	RenderVSYNC(gGT);
	MainFrame_TraceLateRender("vsync-exit");
	MAINFRAME_PERF_END(NATIVE_PERF_BUCKET_MAINFRAME_RENDER_VSYNC);

#ifndef CTR_NATIVE
	RenderFMV();
#endif

	RenderSubmit(gGT);
	MainFrame_TraceLateRender("submit-exit");
}

void DrawUnpluggedMsg(struct GameTracker *gGT, struct GamepadSystem *gGamepads)
{
	int posY;
	int lngArrStart;
	int skipMainMenuTopLevel;
	RECT window;
	int i;

	skipMainMenuTopLevel = 0;

	if (LOAD_IsOpen_MainMenu())
	{
		// if main menu is open, assume 230 loaded,
		// quit if menu is at highest level (no ptrNext to draw)
		// maybe a member of D230.c?
		if (sdata->ptrActiveMenu == (struct RectMenu *)0x800B4540)
		{
			skipMainMenuTopLevel = ((*(int *)0x800b4548 & 0x10) == 0);
		}
	}

	// dont draw error in cutscene, if no controllers are missing currently,
	// in demo mode, or at the highest main-menu level.
	if ((gGT->gameMode1 & GAME_CUTSCENE) != 0)
	{
		return;
	}

	if (MainFrame_HaveAllPads(gGT->numPlyrNextGame))
	{
		return;
	}

	if (gGT->boolDemoMode != 0)
	{
		return;
	}

	if (skipMainMenuTopLevel != 0)
	{
		return;
	}

	// position of error
	posY = data.errorPosY[sdata->errorMessagePosIndex];

	// "Controller 1" or "Controller 2"
	lngArrStart = 0;

	window.x = 0xffec;
	window.y = posY - 3;
	window.w = 0x228;
	window.h = 0;

	// if more than 2 players, or if multitap used
	if ((gGT->numPlyrNextGame > 2) || (gGamepads->slotBuffer[0].controllerData == (PAD_ID_MULTITAP << 4)))
	{
		// change to "1A", "1B", "1C", "1D",
		lngArrStart = 2;
	}

	for (i = 0; i < gGT->numPlyrNextGame; i++)
	{
		struct ControllerPacket *ptrControllerPacket = gGamepads->gamepad[i].ptrControllerPacket;

		if (ptrControllerPacket != 0)
		{
			if (ptrControllerPacket->plugged == PLUGGED)
			{
				continue;
			}
		}

		// if controller is unplugged

		DecalFont_DrawLine(sdata->lngStrings[data.lngIndex_gamepadUnplugged[lngArrStart + i]], 0x100, posY + window.h, FONT_SMALL, (JUSTIFY_CENTER | ORANGE));

		// add for each line
		window.h += 8;
	}

	DecalFont_DrawLine(sdata->lngStrings[LNG_PLEASE_INSERT_A_CONTROLLER], 0x100, posY + window.h, FONT_SMALL, (JUSTIFY_CENTER | ORANGE));

	// add for each line
	window.h += 8;

	// add 3 pixels above, 3 pixels bellow
	window.h += 6;

	RECTMENU_DrawInnerRect(&window, 1, gGT->backBuffer->otMem.uiOT);
}

void DrawFinalLap(struct GameTracker *gGT)
{
	int i;
	int textTimer;
	struct PushBuffer *pb;

	int startX;
	int endX;
	int posY;

	SVec2 resultPos;

	// number of players
	for (i = 0; i < 4; i++)
	{
		// time remaining in animation
		textTimer = sdata->finalLapTextTimer[i];

		// skip if not drawing "FINAL LAP"
		if (textTimer == 0)
		{
			continue;
		}

		// turn "time remaining" into "time elapsed",
		// 90 frames total in animation, 1.5 seconds
		textTimer = 90 - textTimer;

		// camera
		pb = &gGT->pushBuffer[i];

		// << 0x10, >> 0x12
		posY = pb->rect.h / 4;

		// fly from right to center
		if (textTimer <= 10)
		{
			startX = pb->rect.w + 100;
			endX = pb->rect.w / 2;

			goto DrawFinalLapString;
		}

		// sit in center
		if (textTimer <= 0x50)
		{
			startX = pb->rect.w / 2;
			endX = startX;

			// for duration
			textTimer -= 10;

			goto DrawFinalLapString;
		}

		// fly from center to left
		startX = pb->rect.w / 2;
		endX = -100;
		textTimer -= 0x50;

	DrawFinalLapString:

		UI_Lerp2D_Linear(CTR_VECTOR_DATA(&(resultPos)), (s16)startX, (s16)posY, (s16)endX, (s16)posY, textTimer, 10);

		// need to specify OT, or else "FINAL LAP" will draw on top of character icons,
		// and by doing this, "FINAL LAP" draws under the character icons instead
		DecalFont_DrawLineOT(sdata->lngStrings[LNG_FINAL_LAP], resultPos.x, resultPos.y, FONT_BIG, (JUSTIFY_CENTER | ORANGE), pb->ptrOT);

		sdata->finalLapTextTimer[i]--;
	}
}

void RainLogic(struct GameTracker *gGT)
{
	int i;
	struct QuadBlock *camQB;
	int numPlyrCurrGame;

	numPlyrCurrGame = gGT->numPlyrCurrGame;

	for (i = 0; i < numPlyrCurrGame; i++)
	{
		PushBuffer_UpdateFrustum(&gGT->pushBuffer[i]);

		camQB = gGT->cameraDC[i].ptrQuadBlock;

		// skip if camera isn't over quadblock
		if (camQB == 0)
		{
			continue;
		}

		// assume numPlayers is never zero,
		// assume weather_intensity is always valid

		gGT->rainBuffer[i].numParticles_max = (camQB->weather_intensity << 2) / numPlyrCurrGame;

		gGT->rainBuffer[i].vanishRate = (camQB->weather_vanishRate << 2) / numPlyrCurrGame;
	}
}

void MenuHighlight()
{
	int fc;
	int trig;

	fc = sdata->frameCounter << 7;
	trig = MATH_Sin(fc);

	trig = (trig << 6) >> 0xc;

	// sine curve of green, plus base color
	ColorCode_SetPacked(&sdata->menuRowHighlight_Normal, ((trig + 0x40) * 0x100) | 0x80);
	ColorCode_SetPacked(&sdata->menuRowHighlight_Green, ((trig + 0xA0) * 0x100) | 0x400040);
}

void RenderAllWeather(struct GameTracker *gGT)
{
	int numPlyrCurrGame = gGT->numPlyrCurrGame;

	// only if rain is enabled
	if ((gGT->renderFlags & RENDER_FLAG_RAIN) == 0)
	{
		return;
	}

	// only for single player,
	// probably Naughty Dog's last-minute hack
	if (numPlyrCurrGame > 1)
	{
		return;
	}

	RenderWeather(&gGT->pushBuffer[0], &gGT->backBuffer->primMem, &gGT->rainBuffer[0], numPlyrCurrGame, gGT->gameMode1 & PAUSE_ALL);
}

void RenderAllConfetti(struct GameTracker *gGT)
{
	int i;
	int numWinners = gGT->numWinners;

	// only if confetti is enabled
	if ((gGT->renderFlags & RENDER_FLAG_CONFETTI) == 0)
	{
		return;
	}

	// only if someone needs confetti
	if (numWinners == 0)
	{
		return;
	}

	for (i = 0; i < numWinners; i++)
	{
		DrawConfetti(&gGT->pushBuffer[gGT->winnerIndex[i]], &gGT->backBuffer->primMem, &gGT->confetti, gGT->frameTimer_Confetti, gGT->gameMode1 & PAUSE_ALL);
	}
}

void RenderAllHUD(struct GameTracker *gGT)
{
	int hudFlags;
	int gameMode1;

	hudFlags = gGT->hudFlags;
	gameMode1 = gGT->gameMode1;

	// if drawing intro-race title bars
	if ((gGT->numPlyrCurrGame == 1) && ((hudFlags & HUD_FLAG_INTRO_RACE_TITLE_BARS) != 0) && ((gameMode1 & START_OF_RACE) != 0))
	{
		UI_RaceStart_IntroText1P();
	}

	// if not drawing intro-race title bars
	else
	{
		// if no hud
		if ((hudFlags & HUD_FLAG_RACE_HUD) == 0)
		{
			// if standings
			if ((hudFlags & HUD_FLAG_CUP_STANDINGS) != 0)
			{
				UI_CupStandings_InputAndDraw();
			}
		}

		// if hud
		else
		{
			// if not adv hub
			if ((gameMode1 & ADVENTURE_ARENA) == 0)
			{
				// if not drawing end of race
				if (
				    // end of race is not reached
				    ((gameMode1 & END_OF_RACE) == 0) ||

				    // cooldown after end of race not expired
				    (gGT->timerEndOfRaceVS != 0))
				{
					// not crystal challenge
					if ((gameMode1 & CRYSTAL_CHALLENGE) == 0)
					{
						UI_RenderFrame_Racing();
					}

					// if crystal challenge
					else
					{
						UI_RenderFrame_CrystChall();
					}
				}

				// drawing end of race
				else
				{
					if ((u32)(sdata->Loading.stage + 5) > 1)
					{
						if ((gameMode1 & CRYSTAL_CHALLENGE) == 0)
						{
							if ((gameMode1 & TIME_TRIAL) == 0)
							{
								if ((gameMode1 & ARCADE_MODE) == 0)
								{
									if ((gameMode1 & RELIC_RACE) == 0)
									{
										if ((gameMode1 & ADVENTURE_MODE) != 0)
										{
											AA_EndEvent_DrawMenu();
										}
										else if ((gGT->gameMode2 & CUP_ANY_KIND) == 0)
										{
											VB_EndEvent_DrawMenu();
										}
										else
										{
											gGT->hudFlags = (hudFlags & HUD_FLAG_CLEAR_RACE_HUD_MASK) | HUD_FLAG_CUP_STANDINGS;
										}
									}
									else
									{
										RR_EndEvent_DrawMenu();
									}
								}
								else
								{
									AA_EndEvent_DrawMenu();
								}
							}
							else
							{
								TT_EndEvent_DrawMenu();
							}
						}
						else
						{
							CC_EndEvent_DrawMenu();
						}
					}

					return;
				}
			}

			// if adv hub
			else
			{
				// load on last frame of waiting to load 232,
				// leave transition at 1 (see later in func),
				// and load the 232 overlay
				if (gGT->overlayTransition > 1)
				{
					gGT->overlayTransition--;
					if (gGT->overlayTransition == 1)
					{
						LOAD_OvrThreads(2);
					}
				}

				// if 233 is still loaded
				if (!LOAD_IsOpen_AdvHub())
				{
					// if any transition is over
					if (gGT->pushBuffer_UI.fadeFromBlack_currentValue > 0xfff)
					{
						UI_RenderFrame_AdvHub();
					}
				}

				// if 232 overlay is loaded
				else
				{
					// if any transition is over
					if (gGT->pushBuffer_UI.fadeFromBlack_currentValue > 0xfff)
					{
						AH_Map_Main();

						if (sdata->AkuHint_RequestedHint != -1
#ifdef CTR_NATIVE
						    /* Keep the hint request pending until the existing batch
						     * releases the inactive pack. Starting the mask here
						     * could clear a hub preload and append behind its callback,
						     * which switches the allocator back to the current hub. */
						    && !sdata->load_inProgress && !sdata->queueLength && sdata->queueReady
#endif
						   )
						{
							AH_MaskHint_Start(sdata->AkuHint_RequestedHint, sdata->AkuHint_boolInterruptWarppad);

							// erase submitted request
							sdata->AkuHint_RequestedHint = -1;
							sdata->AkuHint_boolInterruptWarppad = 0;
						}
					}

					// if first frame of transition to 232
					if (gGT->overlayTransition != 0)
					{
						gGT->overlayTransition = 0;

						INSTANCE_LevDelayedLInBs(gGT->level1->ptrInstDefs, gGT->level1->numInstances);

						// allow instances again
						gGT->gameMode2 &= ~(NO_LEV_INSTANCE);

						// fade transition
						gGT->pushBuffer_UI.fadeFromBlack_desiredResult = 0x1000;
						gGT->pushBuffer_UI.fade_step = 0x2aa;
					}
				}
			}
		}
	}
}

void RenderAllBeakerRain(struct GameTracker *gGT)
{
	int numPlyrCurrGame = gGT->numPlyrCurrGame;

	// only if beaker rain is enabled
	if ((gGT->renderFlags & RENDER_FLAG_BEAKER_RAIN) == 0)
	{
		return;
	}

	// only for 1P/2P
	if (numPlyrCurrGame > 2)
	{
		return;
	}

	RedBeaker_RenderRain(&gGT->pushBuffer[0], &gGT->backBuffer->primMem, &gGT->JitPools.rain, numPlyrCurrGame, gGT->gameMode1 & PAUSE_ALL);
}

void RenderAllBoxSceneSplitLines(struct GameTracker *gGT)
{
	// Check 233 overlay, cause levelID is set and MainFrame_RenderFrame runs before 233 loads.
	if (LOAD_IsOpen_Podiums())
	{
		if (gGT->levelID == NAUGHTY_DOG_CRATE)
		{
			CS_BoxScene_InstanceSplitLines();
		}
	}
}

void RenderBucket_QueueAllInstances(struct GameTracker *gGT)
{
	int lod;
	int *RBI;
	int numPlyrCurrGame = gGT->numPlyrCurrGame;

	if ((gGT->renderFlags & RENDER_FLAG_RENDER_BUCKET) == 0)
	{
		return;
	}

	lod = numPlyrCurrGame - 1;
	if ((gGT->gameMode1 & RELIC_RACE) != 0)
	{
		lod |= 4;
	}

	RBI = RenderBucket_QueueLevInstances(&gGT->cameraDC[0], &gGT->backBuffer->otMem, gGT->ptrRenderBucketInstance, (u8)sdata->LOD[lod], numPlyrCurrGame,
	                                     gGT->gameMode1 & PAUSE_ALL);

	RBI = RenderBucket_QueueNonLevInstances(gGT->JitPools.instance.taken.first, &gGT->backBuffer->otMem, (void *)RBI, (u8)sdata->LOD[lod], numPlyrCurrGame,
	                                        gGT->gameMode1 & PAUSE_ALL);

	// null terminator at end of list
	*RBI = 0;
	{ static int s_qb = 0; if ((s_qb++ % 30) == 0) { Platform_Log("[probe] qb base=%08x end=%08x n=%d first=%08x first2=%08x' + NL + '", (unsigned)(u32)gGT->ptrRenderBucketInstance, (unsigned)(u32)RBI, (int)(((u32 *)RBI - (u32 *)gGT->ptrRenderBucketInstance) / 2), (unsigned)((u32 *)gGT->ptrRenderBucketInstance)[0], (unsigned)((u32 *)gGT->ptrRenderBucketInstance)[1]); } }

	{
		extern u32 g_ctr360_qdAtt;
		extern u32 g_ctr360_qdQueued;
		extern u32 g_ctr360_qdDrop[9];
		static u32 s_qall = 0;
		if ((s_qall++ % 30) == 0)
		{
			Platform_Log("[probe] qall att=%u q=%u d=%u,%u,%u,%u,%u,%u,%u,%u,%u lodm=%08x L=%08x,%08x,%08x,%08x,%08x\n",
			             (unsigned)g_ctr360_qdAtt, (unsigned)g_ctr360_qdQueued,
			             (unsigned)g_ctr360_qdDrop[0], (unsigned)g_ctr360_qdDrop[1],
			             (unsigned)g_ctr360_qdDrop[2], (unsigned)g_ctr360_qdDrop[3],
			             (unsigned)g_ctr360_qdDrop[4], (unsigned)g_ctr360_qdDrop[5],
			             (unsigned)g_ctr360_qdDrop[6], (unsigned)g_ctr360_qdDrop[7],
			             (unsigned)g_ctr360_qdDrop[8],
			             (unsigned)sdata->LOD[lod],
			             (unsigned)sdata->LOD[0], (unsigned)sdata->LOD[1],
			             (unsigned)sdata->LOD[2], (unsigned)sdata->LOD[3],
			             (unsigned)sdata->LOD[4]);
			g_ctr360_qdAtt = 0;
			g_ctr360_qdQueued = 0;
			g_ctr360_qdDrop[0] = 0;
			g_ctr360_qdDrop[1] = 0;
			g_ctr360_qdDrop[2] = 0;
			g_ctr360_qdDrop[3] = 0;
			g_ctr360_qdDrop[4] = 0;
			g_ctr360_qdDrop[5] = 0;
			g_ctr360_qdDrop[6] = 0;
			g_ctr360_qdDrop[7] = 0;
			g_ctr360_qdDrop[8] = 0;
		}
	}
}

void RenderAllNormalParticles(struct GameTracker *gGT)
{
	int i;

	if ((gGT->renderFlags & RENDER_FLAG_PARTICLES) == 0)
	{
		return;
	}

	for (i = 0; i < gGT->numPlyrCurrGame; i++)
	{
		Particle_RenderList(&gGT->pushBuffer[i], gGT->particleList_ordinary);
	}
}

void RenderDispEnv_World(struct GameTracker *gGT)
{
	int i;
	struct PushBuffer *pb;
	for (i = 0; i < gGT->numPlyrCurrGame; i++)
	{
		pb = &gGT->pushBuffer[i];
		PushBuffer_SetDrawEnv_Normal(&pb->ptrOT[0x3ff], pb, gGT->backBuffer, 0, 0);
	}
}

// I need a better name
void RenderAllFlag0x40(struct GameTracker *gGT)
{
	if ((gGT->renderFlags & RENDER_FLAG_EFFECT_BUCKETS) == 0)
	{
		return;
	}

	if (LOAD_IsOpen_RacingOrBattle())
	{
		RB_Player_ToggleInvisible();
		RB_Player_ToggleFlicker();
		RB_Burst_ProcessBucket(gGT->threadBuckets[BURST].thread);
		RB_Blowup_ProcessBucket(gGT->threadBuckets[BLOWUP].thread);

		RB_Spider_DrawWebs(gGT->threadBuckets[SPIDER].thread, &gGT->pushBuffer[0]);
		RB_Follower_ProcessBucket(gGT->threadBuckets[FOLLOWER].thread);
		RB_StartText_ProcessBucket(gGT->threadBuckets[STARTTEXT].thread);
	}

	if (LOAD_IsOpen_AdvHub())
	{
		if ((gGT->gameMode1 & ADVENTURE_ARENA) != 0)
		{
			AH_WarpPad_AllWarppadNum();
		}
	}

	VehTurbo_ProcessBucket(gGT->threadBuckets[TURBO].thread);

	int i;
	struct PushBuffer *pb;
	for (i = 0; i < gGT->numPlyrCurrGame; i++)
	{
		pb = &gGT->pushBuffer[i];
		VehGroundSkids_Main(gGT->threadBuckets[PLAYER].thread, pb);
		VehGroundSkids_Main(gGT->threadBuckets[ROBOT].thread, pb);
	}
}

void RenderAllTitleDPP(struct GameTracker *gGT)
{
	{ static int s_rt = 0; if (s_rt < 80) { s_rt++; Platform_Log("[probe] title-dpp mode1=%08x open=%d\n", (unsigned)gGT->gameMode1, (int)LOAD_IsOpen_MainMenu()); } }
	if ((gGT->gameMode1 & MAIN_MENU) == 0)
	{
		return;
	}
	if (!LOAD_IsOpen_MainMenu())
	{
		return;
	}
	{ static int s_td = 0; if ((s_td++ % 30) == 0) { Platform_Log("[probe] rf13-open f=%d\n", (int)sdata->frameCounter); } }
	MM_Title_SetTrophyDPP();
}

void RenderBucket_ExecuteAllInstances(struct GameTracker *gGT)
{
	if ((gGT->renderFlags & RENDER_FLAG_RENDER_BUCKET) == 0)
	{
		return;
	}

	{ static int s_eb = 0; if ((s_eb++ % 30) == 0) { Platform_Log("[probe] eb base=%08x first=%08x first2=%08x primcur=%08x' + NL + '", (unsigned)(u32)gGT->ptrRenderBucketInstance, (unsigned)((u32 *)gGT->ptrRenderBucketInstance)[0], (unsigned)((u32 *)gGT->ptrRenderBucketInstance)[1], (unsigned)(u32)gGT->backBuffer->primMem.cursor); } }
	RenderBucket_Execute(gGT->ptrRenderBucketInstance, &gGT->backBuffer->primMem);
}

void RenderAllTires(struct GameTracker *gGT)
{
	int numPlyrCurrGame;
	struct PrimMem *gGT_primMem;

	if ((gGT->renderFlags & RENDER_FLAG_TIRES) == 0)
	{
		return;
	}

	gGT_primMem = &gGT->backBuffer->primMem;
	numPlyrCurrGame = gGT->numPlyrCurrGame;

	if (gGT->threadBuckets[PLAYER].thread != 0)
	{
		DrawTires_Solid(gGT->threadBuckets[PLAYER].thread, gGT_primMem, numPlyrCurrGame);
		DrawTires_Reflection(gGT->threadBuckets[PLAYER].thread, gGT_primMem, numPlyrCurrGame);
	}

	if (gGT->numBotsNextGame != 0)
	{
		DrawTires_Solid(gGT->threadBuckets[ROBOT].thread, gGT_primMem, numPlyrCurrGame);
		DrawTires_Reflection(gGT->threadBuckets[ROBOT].thread, gGT_primMem, numPlyrCurrGame);
	}

	if (gGT->threadBuckets[GHOST].thread != 0)
	{
		DrawTires_Solid(gGT->threadBuckets[GHOST].thread, gGT_primMem, numPlyrCurrGame);
		DrawTires_Reflection(gGT->threadBuckets[GHOST].thread, gGT_primMem, numPlyrCurrGame);
	}
}

void RenderAllShadows(struct GameTracker *gGT)
{
	if ((gGT->renderFlags & RENDER_FLAG_SHADOWS) == 0)
	{
		return;
	}
	VehGroundShadow_Main();
}

void RenderAllHeatParticles(struct GameTracker *gGT)
{
	if ((gGT->renderFlags & RENDER_FLAG_HEAT_EFFECT) == 0)
	{
		return;
	}

	Torch_Main(gGT->particleList_heatWarp, &gGT->pushBuffer[0], &gGT->backBuffer->primMem, gGT->numPlyrCurrGame, gGT->swapchainIndex * 0x128);
}

static s32 RenderAllLevelGeometry_ScaleDistanceShift8(s32 distToScreen, s32 scale)
{
	s32 product = CTR_MipsMulLo(distToScreen, scale);

	if (product < 0)
	{
		product = CTR_MipsAddLo(product, 0xff);
	}

	return CTR_MipsSra(product, 8);
}

void RenderAllLevelGeometry(struct GameTracker *gGT, struct Level *level1, struct mesh_info *ptr_mesh_info)
{
	int i;
	s32 distToScreen;
	int numPlyrCurrGame;
	struct MainRenderLevelGeometryScratch *scratch;
	struct PushBuffer *pushBuffer;
	u32 geometryPrimStart;

	if (level1 == 0)
	{
		return;
	}

	if (ptr_mesh_info == 0)
	{
		return;
	}

	numPlyrCurrGame = gGT->numPlyrCurrGame;

	if (numPlyrCurrGame == 1)
	{
		CTR_ClearRenderLists_1P2P(gGT, 1);
		MainFrame_TraceLateRender("clear-lists-exit");

		// === Temporary 60FPS macros ===
		// Emulate 30fps on 60fps for SCVert and OVert

		// if no SCVert
		if ((level1->configFlags & 4) == 0)
		{
			// assume OVert (no primitives generated here)
			AnimateWater1P(gGT->timer, level1->numWaterVertices, level1->ptr_water, level1->ptr_tex_waterEnvMap, gGT->visMem1->visOVertList[0]);
		}

		// if SCVert
		else
		{
			// draw SCVert (no primitives generated here
			AnimateQuad(gGT->timer << 7, level1->numSCVert, level1->ptrSCVert, gGT->visMem1->visSCVertList[0]);
		}

		MainFrame_TraceLateRender("animate-level-exit");
		// camera of player 1
		pushBuffer = &gGT->pushBuffer[0];
		scratch = CTR_SCRATCHPAD_PTR(struct MainRenderLevelGeometryScratch, 0);

		if (
		    // adv character selection screen
		    (gGT->levelID == ADVENTURE_GARAGE) ||

		    // cutscene that's not Crash Bandicoot intro
		    // where he's sleeping and snoring on a hill
		    (((gGT->gameMode1 & GAME_CUTSCENE) != 0) && (gGT->levelID != INTRO_CRASH)))
		{
			// relationship between near-clip and far-clip,
			// for each RenderList LOD set in the level
			scratch->depthScale = 0x1e00;
			scratch->bspLodDistanceThreshold = 0x640;
			scratch->textureLodDepthThreshold0 = 0x640;
			scratch->textureLodDepthThreshold1 = 0x500;
			scratch->topLevelNearDepthThreshold = 0x280;
			scratch->recursiveNearDepthThreshold = 0x140;
			scratch->fullDynamicFadeDepthStart = scratch->bspLodDistanceThreshold + MAIN_RENDER_LEVEL_GEOMETRY_FULL_DYNAMIC_FADE_OFFSET;
		}

		// every non-cutscene,
		// except for Crash Bandicoot intro
		else
		{
			// 0x1c2 in 1P mode
			distToScreen = pushBuffer->distanceToScreen_PREV;

			scratch->depthScale = RenderAllLevelGeometry_ScaleDistanceShift8(distToScreen, 0x2080);
			scratch->bspLodDistanceThreshold = CTR_MipsMulLo(distToScreen, 0x1a);
			scratch->textureLodDepthThreshold0 = CTR_MipsMulLo(distToScreen, 0x18);
			scratch->textureLodDepthThreshold1 = CTR_MipsMulLo(distToScreen, 0xc);
			scratch->topLevelNearDepthThreshold = CTR_MipsMulLo(distToScreen, 7);
			scratch->recursiveNearDepthThreshold = RenderAllLevelGeometry_ScaleDistanceShift8(distToScreen, 0x380);
			scratch->fullDynamicFadeDepthStart = CTR_MipsAddLo(scratch->bspLodDistanceThreshold, MAIN_RENDER_LEVEL_GEOMETRY_FULL_DYNAMIC_FADE_OFFSET);
		}

		RenderLists_PreInit();
		gGT->bspLeafsDrawn = 0;

		gGT->bspLeafsDrawn += RenderLists_Init1P2P(ptr_mesh_info->bspRoot, gGT->visMem1->visLeafList[0], pushBuffer, (u32)&gGT->LevRenderLists[0],
		                                           gGT->visMem1->bspList[0], numPlyrCurrGame);
		MainFrame_TraceLateRender("init-lists-exit");

		geometryPrimStart = (u32)gGT->backBuffer->primMem.cursor;
		// 226-229
		DrawLevelOvr1P(&gGT->LevRenderLists[0], pushBuffer, (struct BSP *)ptr_mesh_info, &gGT->backBuffer->primMem, gGT->visMem1->visFaceList[0],
		               level1->ptr_tex_waterEnvMap); // waterEnvMap?
		MainFrame_TraceLateRender("draw-level-exit");
		#ifdef CTR_NATIVE
		if ((sdata->frameCounter % 120) == 0 && (gGT->boolDemoMode || (u32)(gGT->levelID - INTRO_RACE_TODAY) < 9))
			Platform_Log("[probe] hb level-geom f=%d lvl=%d leaves=%d primBytes=%d vis=%08x bbox=%d,%d,%d/%d,%d,%d\n",
			             (int)sdata->frameCounter, (int)gGT->levelID, (int)gGT->bspLeafsDrawn,
			             (int)((u32)gGT->backBuffer->primMem.cursor - geometryPrimStart),
			             gGT->visMem1->visFaceList[0] ? (unsigned)CTR_ReadU32LE(gGT->visMem1->visFaceList[0]) : 0,
			             (int)pushBuffer->bbox.min.x, (int)pushBuffer->bbox.min.y, (int)pushBuffer->bbox.min.z,
			             (int)pushBuffer->bbox.max.x, (int)pushBuffer->bbox.max.y, (int)pushBuffer->bbox.max.z);
		#endif

		DrawSky_Full(level1->ptr_skybox, pushBuffer, &gGT->backBuffer->primMem);
		MainFrame_TraceLateRender("draw-sky-exit");

		// skybox gradient
		if ((level1->configFlags & 1) != 0)
		{
			goto SkyboxGlow;
		}

		return;
	}

	if (numPlyrCurrGame == 2)
	{
		CTR_ClearRenderLists_1P2P(gGT, 2);

		// if no SCVert
		if ((level1->configFlags & 4) == 0)
		{
			// assume OVert (no primitives generated here)
			AnimateWater2P(gGT->timer, level1->numWaterVertices, level1->ptr_water, level1->ptr_tex_waterEnvMap, gGT->visMem1->visOVertList[0],
			               gGT->visMem1->visOVertList[1]);
		}

		RenderLists_PreInit();
		gGT->bspLeafsDrawn = 0;

		for (i = 0; i < numPlyrCurrGame; i++)
		{
			gGT->bspLeafsDrawn += RenderLists_Init1P2P(ptr_mesh_info->bspRoot, gGT->visMem1->visLeafList[i], &gGT->pushBuffer[i], (u32)&gGT->LevRenderLists[i],
			                                           gGT->visMem1->bspList[i], numPlyrCurrGame);
		}

		// 226-229
		DrawLevelOvr2P(&gGT->LevRenderLists[0], &gGT->pushBuffer[0], (struct BSP *)ptr_mesh_info, &gGT->backBuffer->primMem, gGT->visMem1->visFaceList[0],
		               gGT->visMem1->visFaceList[1],
		               level1->ptr_tex_waterEnvMap); // waterEnvMap?

		goto SkyboxGlow;
	}

	// 3P or 4P
	CTR_ClearRenderLists_3P4P(gGT, numPlyrCurrGame);

	// if no SCVert
	if ((level1->configFlags & 4) == 0)
	{
		if (numPlyrCurrGame == 3)
		{
			// assume OVert (no primitives generated here)
			AnimateWater3P(gGT->timer, level1->numWaterVertices, level1->ptr_water, level1->ptr_tex_waterEnvMap, gGT->visMem1->visOVertList[0],
			               gGT->visMem1->visOVertList[1], gGT->visMem1->visOVertList[2]);
		}

		else // 4P mode
		{
			// assume OVert (no primitives generated here)
			AnimateWater4P(gGT->timer, level1->numWaterVertices, level1->ptr_water, level1->ptr_tex_waterEnvMap, gGT->visMem1->visOVertList[0],
			               gGT->visMem1->visOVertList[1], gGT->visMem1->visOVertList[2], gGT->visMem1->visOVertList[3]);
		}
	}

	RenderLists_PreInit();
	gGT->bspLeafsDrawn = 0;

	for (i = 0; i < numPlyrCurrGame; i++)
	{
		gGT->bspLeafsDrawn += RenderLists_Init3P4P(ptr_mesh_info->bspRoot, gGT->visMem1->visLeafList[i], &gGT->pushBuffer[i], (u32)&gGT->LevRenderLists[i],
		                                           gGT->visMem1->bspList[i]);
	}

	if (numPlyrCurrGame == 3)
	{
		// 226-229
		DrawLevelOvr3P(&gGT->LevRenderLists[0], &gGT->pushBuffer[0], (struct BSP *)ptr_mesh_info, &gGT->backBuffer->primMem, gGT->visMem1->visFaceList[0],
		               gGT->visMem1->visFaceList[1], gGT->visMem1->visFaceList[2],
		               level1->ptr_tex_waterEnvMap); // waterEnvMap?
	}

	else // 4P mode
	{
		// 226-229
		DrawLevelOvr4P(&gGT->LevRenderLists[0], &gGT->pushBuffer[0], (struct BSP *)ptr_mesh_info, &gGT->backBuffer->primMem, gGT->visMem1->visFaceList[0],
		               gGT->visMem1->visFaceList[1], gGT->visMem1->visFaceList[2], gGT->visMem1->visFaceList[3],
		               level1->ptr_tex_waterEnvMap); // waterEnvMap?
	}

SkyboxGlow:

	// skybox gradient
	for (i = 0; i < numPlyrCurrGame; i++)
	{
		pushBuffer = &gGT->pushBuffer[i];
		CAM_SkyboxGlow(&level1->glowGradient[0], pushBuffer, &gGT->backBuffer->primMem, &pushBuffer->ptrOT[0x3ff]);
	}

	return;
}

void WindowBoxLines(struct GameTracker *gGT)
{
	int i;

	// only battle and 3P4P mode allowed
	if ((gGT->gameMode1 & BATTLE_MODE) == 0)
	{
		return;
	}
	if (gGT->numPlyrCurrGame < 3)
	{
		return;
	}

	for (i = 0; i < gGT->numPlyrCurrGame; i++)
	{
		Color color;
		ColorCode_SetPacked(&color, *data.ptrColor[gGT->drivers[i]->BattleHUD.teamID + PLAYER_BLUE]);
		RECTMENU_DrawOuterRect_LowLevel(

		    // dimensions, thickness
		    &gGT->pushBuffer[i].rect, 4, 2,

		    // color data
		    &color,

		    0,

		    // pushBuffer_UI = 0x1388
		    &gGT->pushBuffer_UI.ptrOT[3]);
	}
}

void WindowDivsionLines(struct GameTracker *gGT)
{
	POLY_F4 *p;
	int numPlyrCurrGame;

	numPlyrCurrGame = gGT->numPlyrCurrGame;

	// horizontal bar
	if (numPlyrCurrGame > 1)
	{
		p = gGT->backBuffer->primMem.cursor;

		// set R, G, B, CODE, all to zero,
		// this makes black color, and invalid CODE
		CtrGpu_WriteColorCode(&p->r0, 0);

		// this sets CODE to the proper value
		setPolyF4(p);

		// Make four (x,y) coordinates
		p->y0 = 0x6a;
		p->y1 = 0x6a;
		p->x0 = 0;
		p->x1 = 0x200;

		p->x2 = 0;
		p->y2 = 0x6e;
		p->x3 = 0x200;
		p->y3 = 0x6e;

		// Draw a bar from left to right,
		// dividing the screen in half on top and bottom
		AddPrim(&gGT->pushBuffer_UI.ptrOT[3], p);

		gGT->backBuffer->primMem.cursor = (void *)(p + 1);
	}

	// vertical bar
	if (numPlyrCurrGame > 2)
	{
#if 0
		gGT->drivers[0]->numWumpas = DRIVER_WUMPA_JUICED_COUNT;
		gGT->drivers[0]->heldItemID = HELD_ITEM_TNT;
		gGT->drivers[1]->numWumpas = DRIVER_WUMPA_JUICED_COUNT;
		gGT->drivers[1]->heldItemID = HELD_ITEM_TNT;
#endif

		p = gGT->backBuffer->primMem.cursor;

		// set R, G, B, CODE, all to zero,
		// this makes black color, and invalid CODE
		CtrGpu_WriteColorCode(&p->r0, 0);

		// this sets CODE to the proper value
		setPolyF4(p);

		// Make four (x,y) coordinates
		p->x0 = 0xfd;
		p->x2 = 0xfd;
		p->y0 = 0;
		p->x1 = 0x103;

		p->y1 = 0;
		p->y2 = 0xd8;
		p->x3 = 0x103;
		p->y3 = 0xd8;

		// Draw a bar from left to right,
		// dividing the screen in half on top and bottom
		AddPrim(&gGT->pushBuffer_UI.ptrOT[3], p);

		// backBuffer->primMem.cursor
		gGT->backBuffer->primMem.cursor = (void *)(p + 1);
	}

	// if numPlyrCurrGame is 3
	if (numPlyrCurrGame == '\x03')
	{
		// This is useless, cause it gets cleared
		// to black anyway, even without this block,
		// at least it does it Crash Cove, does it always?

		p = gGT->backBuffer->primMem.cursor;

		// set R, G, B, CODE, all to zero,
		// this makes black color, and invalid CODE
		CtrGpu_WriteColorCode(&p->r0, 0);

		// this sets CODE to the proper value
		setPolyF4(p);

		// xy0
		p->x0 = 0x100;
		p->x2 = 0x100;
		p->y0 = 0x6c;
		p->y1 = 0x6c;
		p->x1 = 0x200;
		p->y2 = 0xd8;
		p->x3 = 0x200;
		p->y3 = 0xd8;

		// Draw a bar from left to right,
		// dividing the screen in half on top and bottom
		AddPrim(&gGT->pushBuffer_UI.ptrOT[3], p);

		// backBuffer->primMem.cursor
		gGT->backBuffer->primMem.cursor = (void *)(p + 1);
	}
}

void RenderDispEnv_UI(struct GameTracker *gGT)
{
	struct PushBuffer *pb = &gGT->pushBuffer_UI;

	PushBuffer_SetDrawEnv_Normal(&pb->ptrOT[4], pb, gGT->backBuffer, 0, 0);
}

int ReadyToFlip(struct GameTracker *gGT)
{
	return
	    // two VSYNCs passed, 30fps lock
	    (sdata->vsyncTillFlip < 1) &&

	    // if DrawOTag finished
	    (gGT->bool_DrawOTag_InProgress == 0);
}

int ReadyToBreak(struct GameTracker *gGT)
{
	return

	    // if more than 6 VSYNCs passed since
	    // the last successful draw, FPS < 10fps
	    gGT->vSync_between_drawSync > 6;
}

void RenderVSYNC(struct GameTracker *gGT)
{
	gGT->clockDurationStall = Timer_GetTime_Total();

	// render checkered flag
	if ((gGT->renderFlags & RENDER_FLAG_CHECKERED_FLAG) != 0)
	{
		// Wait until "next" vsync,
		// Main Menu at 45fps will cap to 30fps
		// Levels+RaceFlag at 25fps will cap to 20fps
		VSync(0);
	}


	while (1)
	{
#ifdef CTR_NATIVE
		// NOTE(aalhendi): Native host sync needs DrawSync polling here; retail
		// falls through to the BreakDraw guard below instead.
		// must be called in the loop,
		// or else it wont properly sync
		DrawSync(0);
#endif

		if (ReadyToFlip(gGT))
		{
			// quit, end of stall
			return;
		}

#ifdef CTR_NATIVE
		// NOTE(aalhendi): Retail waits on GPU/vblank hardware here. Native
		// owns that wait in VSync(), which also emits the VBlank callback.
		VSync(0);
#endif

#ifndef CTR_NATIVE
		if (ReadyToBreak(gGT))
		{
			// just quit and try the next frame
			BreakDraw();
			return;
		}
#endif
	}
}

#ifndef CTR_NATIVE
void RenderFMV()
{
	if (sdata->boolPlayVideoSTR == 1)
	{
		MM_Video_CheckIfFinished(1);

		MoveImage(&sdata->videoSTR_src_vramRect, sdata->videoSTR_dst_vramX, sdata->videoSTR_dst_vramY);

		DrawSync(0);
	}
}
#endif

void RenderSubmit(struct GameTracker *gGT)
{
	// 1 VSYNC = 60fps
	// 2 VSYNCs = 30fps

#if defined(CTR_NATIVE) && defined(CTR_INTERNAL)
	NativePerf_BeginScope(NATIVE_PERF_BUCKET_RENDER_SUBMIT);
#endif

	gGT->clockDurationStall = Timer_GetTime_Elapsed(gGT->clockDurationStall, 0);

#if defined(CTR_NATIVE)

	sdata->vsyncTillFlip = 2;

	// Native still renders immediately through PsyCross, so keep the host GPU's
	// active draw/display envs in step with the retail DB selected this frame.
	PutDrawEnv(&gGT->backBuffer->drawEnv);
	gGT->frontBuffer = &gGT->db[1 - gGT->swapchainIndex];
	PutDispEnv(&gGT->frontBuffer->dispEnv);

#else

	// do I need the "if"? will it ever be nullptr?
	if (gGT->frontBuffer != 0)
	{
		sdata->vsyncTillFlip = 2;
		gGT->unk1cc4[5] = gGT->unk1cc4[0];

		if ((sdata->boolDebugDispEnv & 1) != 0)
			PutDispEnv(&sdata->blank_debug_DispEnv);
		else
			PutDispEnv(&gGT->frontBuffer->dispEnv);
		PutDrawEnv(&gGT->frontBuffer->drawEnv);
		gGT->frontBuffer = 0;
	}

	// swap=0, get db[1]
	// swap=1, get db[0]
	gGT->frontBuffer = &gGT->db[1 - gGT->swapchainIndex];
#endif

	gGT->bool_DrawOTag_InProgress = 1;

	void *ot = &gGT->pushBuffer[0].ptrOT[0x3ff];

	DrawOTag(ot);

	gGT->frameTimer_notPaused = gGT->frameTimer_VsyncCallback;

#if defined(CTR_NATIVE) && defined(CTR_INTERNAL)
	NativePerf_EndScope(NATIVE_PERF_BUCKET_RENDER_SUBMIT);
#endif
}
