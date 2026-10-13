#include <common.h>

// Dont get confused, packID is LOAD_GetAdvPackIndex(),
// which gives the pack of the hub you're NOT on, because the
// game does 3-GetAdvPackIndex to load the hub you ARE on
void LOAD_TalkingMask(int packID, int maskID)
{
#ifdef CTR_NATIVE
	/* A hub preload owns this pack until its final callback. The normal
	 * hint request waits across frames; direct callers must also finish the
	 * old batch before resetting memory or appending mask files behind it. */
	while (sdata->load_inProgress || sdata->queueLength || !sdata->queueReady)
	{
		LOAD_NextQueuedFile();
		CDSYS_XAPauseAtEnd();
		VSync(0);
	}
#endif

	sdata->modelMaskHints3D = 0;

	// invalidate alternative-hub, because
	// the mask will load in that level's RAM
#ifdef CTR_NATIVE
	/* Keep the intended destination ID, but invalidate its resident pointer.
	 * A door can reach the swap trigger after a greeting reused this pack,
	 * without crossing the preload trigger again. SwapNow must reload it. */
	sdata->gGT->level2 = NULL;
#else
	sdata->gGT->levID_in_each_mempack[packID] = -1;
#endif

	// Swap to pack of hub you're NOT on,
	// wipe the pack to reload the new MASK
	MEMPACK_SwapPacks(packID);
	MEMPACK_ClearLowMem();
#ifdef CTR_NATIVE
	Platform_Log("[load] mask begin pack=%d mask=%d free=%d destination=%d\n", packID, maskID,
	             MEMPACK_GetFreeBytes(), sdata->gGT->levID_in_each_mempack[packID]);
#endif

	sdata->load_inProgress = 1;

	int offset = maskID * 4 + (packID - 1) * 2;

	// NOTE(aalhendi): Retail queues legacy VRAM type 3 with no final callback.
	LOAD_AppendQueue(sdata->ptrBigfileCdPos_2, LT_VRAM, BI_UKAHEAD + offset, NULL, NULL);

	LOAD_AppendQueue(sdata->ptrBigfileCdPos_2, LT_GETADDR, BI_UKAHEAD + offset + 1, NULL, LOAD_Callback_MaskHints3D);
}

void LOAD_LevelFile(int levelID)
{
	struct GameTracker *gGT = sdata->gGT;

	// why here?
	sdata->modelMaskHints3D = 0;

	gGT->hudFlags &= HUD_FLAG_CLEAR_RACE_HUD_MASK;

	gGT->prevLEV = gGT->levelID;
	gGT->levelID = levelID;

	// disable all rendering except checkeredFlag
	gGT->renderFlags &= RENDER_FLAG_CHECKERED_FLAG;

	if (RaceFlag_IsFullyOffScreen())
	{
		RaceFlag_BeginTransition(1);
	}

	// start loading
	sdata->Loading.stage = LOAD_TEN_STAGES_0;
}
