/* Experimental open xSDK / Vulkan title. C17 union initializers are kept
 * by the patched GCC compiler; no XDK mirror or Microsoft runtime is used. */

#include <xtl.h>





#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "platform/native_assets.h"
#include "platform/native_log.h"
#include "platform/native_memory.h"
#include "platform/native_perf.h"
#include "platform/native_replay_scheduler.h"
#include "platform/native_savestate.h"

#include <platform.h>

#include "game/game_unity.h"

#include "game/zGlobal_RDATA.c"
#include "game/zGlobal_DATA.c"
#include "game/zGlobal_SDATA.c"




#undef RECT

/* Mirrored platform files (identical to main.c's list minus the host backends
 * that platform/xbox360 replaces: renderer, platform, input, glad, log). */
#include "platform/native_disc_image.c"
#include "platform/native_assets.c"
#include "platform/native_audio.c"
#include "platform/native_memory.c"
#include "platform/native_checkpoint.c"
#include "platform/native_checkpoint_file.c"
#include "platform/native_cd.c"
#include "platform/native_gpu_links.c"
#include "platform/native_gpu.c"
#include "platform/native_gte_core.c"
#include "platform/native_inline_c.c"
#include "platform/native_libapi.c"
#include "platform/native_libetc.c"
#include "platform/native_libgte.c"
#include "platform/native_libgpu.c"
#include "platform/native_libpad.c"
#include "platform/native_libspu.c"
#include "platform/xsdk/native_xsdk_file.c"
#include "platform/native_memcard.c"
#include "platform/native_memcard_adapter.c"
#include "platform/native_perf.c"
#include "platform/native_trace.c"
#include "platform/native_replay_scheduler.c"
#include "platform/native_savestate.c"
#include "platform/native_state.c"
#include "platform/native_str.c"

/* Open xSDK backends and the shared console cadence/input implementation. */
#include "platform/native_config.c"
#include "platform/xsdk/native_xsdk_log.c"
#include "platform/xsdk/native_xsdk_fault.c"
#include "platform/xsdk/native_xsdk_audio.c"
#include "platform/xsdk/native_xsdk_video.c"
#include "platform/xbox360/native_xbox360_platform.c"
#include "platform/xbox360/native_xbox360_input.c"

#ifndef CTR_NATIVE_VERSION
#define CTR_NATIVE_VERSION "0.0.0-dev"
#endif

#ifndef CTR_NATIVE_BUILD_ID
#define CTR_NATIVE_BUILD_ID "built " __DATE__ " " __TIME__
#endif

int main(void)
{
	const char *basePath = "game:\\";
	int result;

	Platform_LogInit("ctr360");
	Platform_InstallFaultHandler();
	Platform_Log("[CTR Native] Starting (xSDK/Vulkan experimental)\n");
	Platform_Log("[CTR Native] Version: %s (%s)\n", CTR_NATIVE_VERSION, CTR_NATIVE_BUILD_ID);
	/* GCC preserves the C17 static union initializers. */
	Platform_Log("[boot] asset-paths begin root=%s\n", basePath);

	if (!NativeAssets_Init(basePath))
	{
		Platform_LogError("[CTR Native] Failed to initialize asset paths.\n");
		Platform_LogShutdown();
		Platform_Exit(1);
		return 1;
	}

	Platform_Log("[CTR Native] Base: %s\n", NativeAssets_GetBaseDir());
	Platform_Log("[CTR Native] Assets: %s\n", NativeAssets_GetAssetDir());

	/* XDK has no process CWD. Asset validation checks the absolute paths. */
	Platform_Log("[boot] asset-validation begin\n");
	if (!NativeAssets_Validate())
	{
		Platform_LogError("[boot] asset-validation FAILED\n");
		Platform_LogShutdown();
		Platform_Exit(1);
		return 1;
	}

	Platform_Log("[CTR Native] Assets validated\n");
	Platform_Log("[boot] memcard-root begin\n");

	/* Xbox has no CWD. Keep both virtual cards on the same writable USB/HDD
	 * as this XEX, independently of the launcher and of cache:\\ cleanup. */
	if (NativeMemcard_SetRoot("game:\\memcards") != NATIVE_MEMCARD_OK)
	{
		Platform_LogError("[memcard] Failed to configure game:\\memcards\n");
		Platform_LogShutdown();
		Platform_Exit(1);
		return 1;
	}
	Platform_Log("[memcard] root=game:\\memcards (beside default.xex)\n");

	Platform_Log("[boot] platform-init begin\n");
	Platform_Init("Crash Team Racing", 1280, 720);
	if (!s_platformInitialized)
	{
		Platform_LogError("[boot] platform-init FAILED\n");
		Platform_LogShutdown();
		Platform_Exit(1);
		return 1;
	}
	Platform_Log("[CTR Native] Platform ready\n");

	Platform_Log("[boot] scratchpad-init begin\n");
	Platform_InitScratchpad();
	Platform_Log("[boot] resident-pointer-repair begin\n");
	Platform_RepairResidentPointers(0);

	Platform_Log("[CTR Native] Entering CTR_Main\n");
	result = CTR_Main();
	Platform_Log("[CTR Native] CTR_Main returned %d\n", result);

	Platform_Exit(result);

	return result;
}
