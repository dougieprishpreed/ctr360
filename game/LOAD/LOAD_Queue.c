#include <common.h>

static void LOAD_TraceDemoQueue(const char *step)
{
#ifdef CTR_NATIVE
	if (sdata->gGT->boolDemoMode && sdata->gGT->levelID == CRASH_COVE && sdata->Loading.stage >= 0)
		Platform_Log("[probe] hb demo-queue f=%d step=%s queue=%d ready=%d type=%d file=%d dst=%08x bytes=%d\n",
		             (int)sdata->frameCounter, step, (int)sdata->queueLength, (int)sdata->queueReady,
		             (int)data.currSlot.type_UNUSED, (int)data.currSlot.subfileIndex,
		             (unsigned)(u32)data.currSlot.ptrDestination, (int)data.currSlot.size_UNUSED);
#endif
}

void LOAD_AppendQueue(struct BigHeader *bigfile, int type, int fileIndex, void *destinationPtr, void (*callback)(struct LoadQueueSlot *))
{
	if (sdata->queueLength >= LOAD_QUEUE_SLOT_COUNT)
	{
		return;
	}

	struct LoadQueueSlot *lqs = &sdata->queueSlots[(s32)sdata->queueLength];
	lqs->ptrBigfileCdPos_UNUSED = bigfile;
	lqs->flags = 0;
	lqs->type_UNUSED = type;
	lqs->subfileIndex = fileIndex;
	lqs->ptrDestination = destinationPtr;
	lqs->size_UNUSED = 0;
	lqs->callbackFuncPtr = callback;

	sdata->queueLength++;
}

void LOAD_CDRequestCallback(struct LoadQueueSlot *lqs)
{
	LOAD_TraceDemoQueue("callback-enter");
	if (lqs->callbackFuncPtr != NULL)
	{
		lqs->callbackFuncPtr(lqs);
	}

	sdata->queueReady = 1;
	LOAD_TraceDemoQueue("callback-exit");
}

void LOAD_NextQueuedFile()
{
	struct LoadQueueSlot *curr = &data.currSlot;
	LOAD_TraceDemoQueue("enter");

	if ((sdata->queueReady != 0) && (sdata->XA_State == 0) && (sdata->queueLength != 0))
	{
		sdata->queueReady = 0;

		if (sdata->queueRetry != 0)
		{
			sdata->queueRetry = 0;
		}
		else
		{
			*curr = sdata->queueSlots[0];

			for (int i = LOAD_QUEUE_FIRST_PENDING_SLOT; i < sdata->queueLength; i++)
			{
				sdata->queueSlots[i - 1] = sdata->queueSlots[i];
			}
		}

		LOAD_TraceDemoQueue("file-enter");
		switch (curr->type_UNUSED)
		{
		case LT_RAW:
			curr->ptrDestination = LOAD_ReadFile_ex(curr->ptrBigfileCdPos_UNUSED, LT_SETADDR, curr->subfileIndex, curr->ptrDestination, &curr->size_UNUSED,
			                                        LOAD_CDRequestCallback);
			break;

		case LT_DRAM:
			curr->ptrDestination =
			    LOAD_DramFile(curr->ptrBigfileCdPos_UNUSED, curr->subfileIndex, curr->ptrDestination, &curr->size_UNUSED, (int)(s32)curr->callbackFuncPtr);
			break;

		case LT_VRAM:
			curr->ptrDestination =
			    LOAD_VramFile(curr->ptrBigfileCdPos_UNUSED, curr->subfileIndex, curr->ptrDestination, &curr->size_UNUSED, (int)(s32)curr->callbackFuncPtr);
			break;
		}

		LOAD_TraceDemoQueue("file-exit");
		sdata->queueLength--;
	}

	if (sdata->frameFinishedVRAM != 0)
	{
		if ((u32)(sdata->gGT->frameTimer_VsyncCallback - sdata->frameFinishedVRAM) >= LOAD_QUEUE_VRAM_CALLBACK_DELAY_FRAMES)
		{
			if (curr->callbackFuncPtr != NULL)
			{
				LOAD_TraceDemoQueue("vram-callback-enter");
				curr->callbackFuncPtr(curr);
				LOAD_TraceDemoQueue("vram-callback-exit");
			}

			sdata->frameFinishedVRAM = 0;

#if defined(CTR_NATIVE)
			// NOTE(aalhendi): CTR_NATIVE marks Mempack allocations with a host-only
			// flag while the retail path uses LT_SETADDR for the same ownership.
			if ((curr->flags & (LT_SETADDR | LT_MEMPACK)) != 0)
#else
			if ((curr->flags & LT_SETADDR) != 0)
#endif
			{
				MEMPACK_PopState();
			}

			sdata->queueReady = 1;
		}
	}
	LOAD_TraceDemoQueue("exit");
}
