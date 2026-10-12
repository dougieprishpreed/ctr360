#include <common.h>

void MainDrawCb_DrawSync()
{
	struct GameTracker *gGT;
	gGT = sdata->gGT;

	if (gGT->bool_DrawOTag_InProgress == 1)
	{
		gGT->bool_DrawOTag_InProgress = 0;
	}

	return;
}

// NOTE(aalhendi): CTR_NATIVE keeps native input/audio/VRAM bridge work.
void MainDrawCb_Vsync()
{
	struct GameTracker *gGT;
#ifdef CTR_NATIVE
	if (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722)
		Platform_Log("[probe] hb vsync f=%d step=enter\n", (int)sdata->frameCounter);
#endif

	gGT = sdata->gGT;
	gGT->frameTimer_VsyncCallback++;
	if ((gGT->gameMode1 & PAUSE_ALL) == 0)
	{
		gGT->frameTimer_Confetti++;
	}

	sdata->vsyncTillFlip--;
	gGT->vSync_between_drawSync++;

	// NOTE(aalhend): accumulate root-counter 1 units between VSync callbacks; Timer_GetTime_Total converts them through the retail 0x147e divisor.
	sdata->rcntTotalUnits += GetRCnt(0xf2000001);
	ResetRCnt(0xf2000001);

#ifdef CTR_NATIVE
	// NOTE(aalhendi): Retail calls HOWL unconditionally. Native skips only while
	// channel lists are mid-edit.
	if (sdata->criticalSectionCount == 0)
#endif
	{
		howl_PlayAudio_Update();
	}
#ifdef CTR_NATIVE
	if (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722)
		Platform_Log("[probe] hb vsync f=%d step=howl-exit\n", (int)sdata->frameCounter);
#endif

#ifdef CTR_NATIVE
	// NOTE(aalhendi): Native owns host input and writes PSX-shaped pad
	// snapshots before retail GAMEPAD_PollVsync consumes them.
	Platform_PollInput();
#endif

	GAMEPAD_PollVsync(sdata->gGamepads);
#ifdef CTR_NATIVE
	if (sdata->frameCounter >= 1708 && sdata->frameCounter <= 1722)
		Platform_Log("[probe] hb vsync f=%d step=pad-exit\n", (int)sdata->frameCounter);
#endif

	return;
}
