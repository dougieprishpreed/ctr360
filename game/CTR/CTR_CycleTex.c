#include <common.h>
/* ctr360 walk instruments: bound the model / header / animtex-chain walks
 * and trace them on menu frames (mode1 MAIN_MENU, not LOADING). */
int g_ctr360_modelWalkGuard = 0;
int g_ctr360_hdrGuard = 0;
int g_ctr360_ctxWalkGuard = 0;

void CTR_CycleTex_LEV(struct AnimTex *animtex, int timer)
{
	int frameCurr;
	struct AnimTex *curAnimTex = animtex;
	{ g_ctr360_ctxWalkGuard = 0; }

	// Termination is determined by pointer to First AnimTex
	while (*(int *)curAnimTex != (int)animtex)
	{
		// which texture to draw this frame
		{ static int s_cm = 0; g_ctr360_ctxWalkGuard++; if (g_ctr360_ctxWalkGuard > 4096) { Platform_Log("[probe] cm-guard a=%08x cur=%08x\n", (unsigned)(u32)animtex, (unsigned)(u32)curAnimTex); break; } if ((s_cm < 300) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_cm++; Platform_Log("[probe] cm f=%d a=%08x cur=%08x nf=%d fo=%d fs=%d link=%08x\n", (int)sdata->frameCounter, (unsigned)(u32)animtex, (unsigned)(u32)curAnimTex, (int)curAnimTex->numFrames, (int)curAnimTex->frameOffset, (int)curAnimTex->frameSkip, (unsigned)(u32)*(int *)curAnimTex); } }
		frameCurr = timer + curAnimTex->frameOffset;

		// allow frames to skip updating (like 60fps hacks)
		frameCurr = frameCurr >> curAnimTex->frameSkip;

		// loop back to index[0] after finished cycle
		frameCurr = frameCurr % curAnimTex->numFrames;

		// save result
		curAnimTex->frameCurr = frameCurr;

		struct IconGroup4 **ptrArray = ANIMTEX_GETARRAY(curAnimTex);

		// Save new frame
		// For levels, this is just a pointer
		curAnimTex->ptrActiveTex = (int *)ptrArray[frameCurr];

		// Go to next AnimTex, which comes after this AnimTex's ptrarray
		curAnimTex = (struct AnimTex *)&ptrArray[curAnimTex->numFrames];
	}
}

void CTR_CycleTex_Model(struct AnimTex *animtex, int timer)
{
	int frameCurr;
	struct AnimTex *curAnimTex = animtex;
	{ g_ctr360_ctxWalkGuard = 0; }

	// Termination is determined by pointer to First AnimTex
	while (*(int *)curAnimTex != (int)animtex)
	{
		// which texture to draw this frame
		{ static int s_cm = 0; g_ctr360_ctxWalkGuard++; if (g_ctr360_ctxWalkGuard > 4096) { Platform_Log("[probe] cm-guard a=%08x cur=%08x\n", (unsigned)(u32)animtex, (unsigned)(u32)curAnimTex); break; } if ((s_cm < 300) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_cm++; Platform_Log("[probe] cm f=%d a=%08x cur=%08x nf=%d fo=%d fs=%d link=%08x\n", (int)sdata->frameCounter, (unsigned)(u32)animtex, (unsigned)(u32)curAnimTex, (int)curAnimTex->numFrames, (int)curAnimTex->frameOffset, (int)curAnimTex->frameSkip, (unsigned)(u32)*(int *)curAnimTex); } }
		frameCurr = timer + curAnimTex->frameOffset;

		// allow frames to skip updating (like 60fps hacks)
		frameCurr = frameCurr >> curAnimTex->frameSkip;

		// loop back to index[0] after finished cycle
		frameCurr = frameCurr % curAnimTex->numFrames;

		// save result
		curAnimTex->frameCurr = frameCurr;

		struct IconGroup4 **ptrArray = ANIMTEX_GETARRAY(curAnimTex);

		// Save new frame
		// For Model, this is a pointer to a pointer
		*curAnimTex->ptrActiveTex = (int)ptrArray[frameCurr];

		// Go to next AnimTex, which comes after this AnimTex's ptrarray
		curAnimTex = (struct AnimTex *)&ptrArray[curAnimTex->numFrames];
	}
}

void CTR_CycleTex_AllModels(u32 numModels, struct Model **pModelArray, int timer)
{
	struct Model *pModel;
	struct ModelHeader *pHeader;

	{ g_ctr360_modelWalkGuard = 0; }

	if (pModelArray == NULL)
	{
		return;
	}

	if (numModels == 0)
	{
		return;
	}

	while (true)
	{
		{ g_ctr360_modelWalkGuard++; g_ctr360_hdrGuard = 0; g_ctr360_ctxWalkGuard = 0; if (g_ctr360_modelWalkGuard > 512) { Platform_Log("[probe] am-guard num=%d arr=%08x\n", (int)numModels, (unsigned)(u32)pModelArray); return; } }
		pModel = *pModelArray;
		{ static int s_am = 0; if ((s_am < 300) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_am++; Platform_Log("[probe] am f=%d num=%d arr=%08x m=%08x\n", (int)sdata->frameCounter, (int)numModels, (unsigned)(u32)pModelArray, (unsigned)(u32)pModel); } }
		if (pModel == NULL)
		{
			return;
		}

		// iterate over all model headers
		for (int j = 0; j < pModel->numHeaders; j++)
		{
			pHeader = &pModel->headers[j];
			{ static int s_hd = 0; g_ctr360_hdrGuard++; if (g_ctr360_hdrGuard > 1024) { Platform_Log("[probe] hd-guard nh=%d m=%08x\n", (int)pModel->numHeaders, (unsigned)(u32)pModel); break; } if ((s_hd < 300) && ((sdata->gGT->gameMode1 & 0x2000) != 0)) { s_hd++; Platform_Log("[probe] hd f=%d j=%d hdr=%08x atx=%08x fl=%04x\n", (int)sdata->frameCounter, (int)j, (unsigned)(u32)pHeader, (unsigned)(u32)pHeader->animtex, (unsigned)(pHeader->flags)); } }

			if ((pHeader->animtex != NULL) && ((pHeader->flags & 2) == 0))
			{
				CTR_CycleTex_Model(pHeader->animtex, timer);
			}
		}

		numModels--;
		if (numModels == 0)
		{
			return;
		}

		pModelArray++;
	}
}

void CTR_CycleTex_2p3p4pWumpaHUD(u32 *ptrActiveTex, u32 *ptrArray, int numFrames)
{
	ptrArray[0] = ptrActiveTex[0];
	ptrActiveTex[0] = CtrGpu_PrimToOTLink24(&ptrArray[numFrames - 1]);
}
