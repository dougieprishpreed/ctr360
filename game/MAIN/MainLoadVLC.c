#include <common.h>

void MainLoadVLC_Callback(struct LoadQueueSlot *param_1)
{
	// VLC is now loaded
	sdata->bool_IsLoaded_VlcTable = 1;
	{ static int s_vc = 0; if (s_vc < 20) { s_vc++; Platform_Log("[probe] vl cb ptr=%08x\n", (unsigned)(u32)param_1->ptrDestination); } }

#ifdef CTR_NATIVE
	// NOTE(aalhendi): Native keeps the loaded VLC pointer in host-visible state.
	sdata->ptrVlcTable = param_1->ptrDestination;
#endif
}

void MainLoadVLC(void)
{
	struct BigHeader *bigfile;
	struct BigEntry *entry;
	int size;

	// VLC is not loaded
	{ static int s_vl = 0; if (s_vl < 20) { s_vl++; Platform_Log("[probe] vl entry isLoaded=%d\n", (int)sdata->bool_IsLoaded_VlcTable); } }
	sdata->bool_IsLoaded_VlcTable = 0;

	bigfile = sdata->ptrBigfileCdPos_2;
	entry = BIG_GETENTRY(bigfile);
	size = (entry[BI_VLCTABLE].size + 0x7ff) & 0xfffff800;
	sdata->ptrVlcTable = MEMPACK_AllocMem(size, NULL);

	// This table is passed as parameter to DecDCTvlc2
	LOAD_AppendQueue(bigfile, LT_SETADDR, BI_VLCTABLE, sdata->ptrVlcTable, MainLoadVLC_Callback);
}
