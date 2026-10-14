#include <common.h>

void MainRaceTrack_StartLoad(s16 levelID)
{
	// clear backup,
	// keep music,
	// destroy "most" fx, let menu fx play to end
	howl_StopAudio(1, 0, 0);

	ElimBG_Deactivate(sdata->gGT);

	LOAD_LevelFile(levelID);
	return;
}

void MainRaceTrack_RequestLoad(s16 levelID)
{
#ifdef CTR_NATIVE
	/* Hidden flags are used by cutscenes. A race request from a live hub
	 * must restore visibility: drawing owns the cover-transition advance,
	 * and MainMain cannot begin IO until that transition reaches zero. */
	if (sdata->Loading.stage != LOAD_REQUESTED)
		Platform_Log("[load] request from=%d to=%d flag=%d anim=%d canDraw=%d flags=%08x hint=%d\n",
		             (int)sdata->gGT->levelID, (int)levelID, (int)sdata->RaceFlag_Position,
		             (int)sdata->RaceFlag_AnimationType, (int)sdata->RaceFlag_CanDraw,
		             (unsigned)sdata->gGT->renderFlags, (int)sdata->AkuAkuHintState);
	if ((sdata->gGT->gameMode1 & ADVENTURE_ARENA) != 0)
	{
		RaceFlag_SetCanDraw(1);
		if ((sdata->gGT->renderFlags & RENDER_FLAG_CHECKERED_FLAG) == 0 && !RaceFlag_IsFullyOnScreen())
			RaceFlag_BeginTransition(1);
	}
#endif
	// Turn off HUD
	sdata->gGT->hudFlags &= HUD_FLAG_CLEAR_RACE_HUD_MASK;

	if (RaceFlag_IsFullyOffScreen())
	{
		RaceFlag_BeginTransition(1);
	}
	RaceFlag_ResetTextAnim();

	sdata->Loading.stage = LOAD_REQUESTED;
	sdata->Loading.Lev_ID_To_Load = levelID;
	return;
}
