/* ctr360: Xbox 360 platform layer.
 *
 * Ports platform/native_platform.c (the SDL host backend) onto XTL:
 *  - wall clock: KeQueryPerformanceCounter via QueryPerformanceCounter
 *  - wait: Sleep(1) chunks plus a short final spin, same shape as the
 *    SDL_DelayPrecise + spin-window scheme (no high-res waitable timer use on
 *    purpose: console scheduler wakeups land within a millisecond and the
 *    vblank schedule is absolute, so late wakeups do not drift)
 *  - events: XInput hot-plug polling + a Back+Start quit chord instead of a
 *    window message loop
 *
 * The VBlank emitter, VSync() and the catch-up logic are ported verbatim
 * because the game's whole frame cadence hangs off them.
 *
 * C89-clean on purpose: the XDK compiler builds this directly.
 */

#include <xtl.h>
#if defined(CTR_XSDK)
#include <xsdk/present.h>
#endif

#include <macros.h>
#include <platform.h>
#include <stdio.h>

#include "platform/native_audio.h"
#include "platform/native_config.h"
#include "platform/native_gpu.h"
#include "platform/native_input.h"
#include "platform/native_log.h"
#include "platform/native_renderer.h"

extern int g_cfg_bilinearFiltering;
extern int g_dbg_texturelessMode;
extern int g_dbg_wireframeMode;
extern int g_windowHeight;
extern int g_windowWidth;

global_variable int s_platformInitialized = 0;
global_variable int s_platformBeginScene = 0;
global_variable int s_pinnedVramDisplayFrames = 0;
global_variable int s_pinnedVramDisplayCustomRect = 0;
global_variable int s_pinnedVramDisplayX = 0;
global_variable int s_pinnedVramDisplayY = 0;
global_variable int s_pinnedVramDisplayW = 0;
global_variable int s_pinnedVramDisplayH = 0;
global_variable int s_fpsFrameCount = 0;
global_variable u64 s_fpsLastCounter = 0;

#define NATIVE_FPS_REPORT_FRAME_WINDOW 2000

internal u64 X360_GetCounter(void)
{
	LARGE_INTEGER now;
	QueryPerformanceCounter(&now);
	return (u64)now.QuadPart;
}

internal u64 X360_GetFrequency(void)
{
	LARGE_INTEGER freq;
	QueryPerformanceFrequency(&freq);
	return (u64)freq.QuadPart;
}

internal double Native_CounterToMs(u64 delta)
{
	const u64 freq = X360_GetFrequency();

	if (freq == 0)
	{
		return 0.0;
	}
	return ((double)delta * 1000.0) / (double)freq;
}

internal void Platform_CalcFPS(void)
{
	const u64 freq = X360_GetFrequency();
	const u64 now = X360_GetCounter();

	if (freq == 0)
	{
		return;
	}

	if (s_fpsLastCounter == 0)
	{
		s_fpsLastCounter = now;
		s_fpsFrameCount = 0;
		return;
	}

	s_fpsFrameCount++;
	if (s_fpsFrameCount < NATIVE_FPS_REPORT_FRAME_WINDOW)
	{
		return;
	}

	if (now > s_fpsLastCounter)
	{
		const f64 elapsedSeconds = (f64)(now - s_fpsLastCounter) / (f64)freq;
		const f64 fps = (f64)s_fpsFrameCount / elapsedSeconds;

		Platform_Log("[CTR Native] FPS: %.2f (last %d frames)\n", fps, s_fpsFrameCount);
	}

	s_fpsFrameCount = 0;
	s_fpsLastCounter = now;
}

void Platform_Init(const char *title, int width, int height)
{
	Platform_LogInit(title);

	Platform_Log("[CTR Native] Initialising platform (Xbox 360)\n");

	/* Before the renderer and input read their settings. */
	if (NativeConfig_CreateDefault("game:/ctr360.ini", "game:/ctr360.example.ini"))
	{
		Platform_Log("[CTR Native] created ctr360.ini from ctr360.example.ini\n");
	}

	/* Device creation lives in the renderer, same split as the SDL build. */
	if (!NativeRenderer_InitialiseRender((char *)title, width, height, 0))
	{
		Platform_LogError("[CTR Native] Failed to initialise D3D9 device\n");
		Platform_LogShutdown();
		return;
	}

	if (!NativeRenderer_InitialisePSX())
	{
		Platform_LogError("[CTR Native] Failed to initialise PSX renderer state\n");
		Platform_Shutdown();
		return;
	}

	s_platformInitialized = 1;

	Platform_InputInit();
}

void Platform_Exit(int status)
{
	/* XDK CRT exit/return-to-CRT terminates with KeBugCheck, not a title
	 * switch. Use the same explicit dashboard launch as the quit chord,
	 * also when the Homebrew App Store started the game. */
	Platform_Log("[CTR Native] returning to dashboard status=%d\n", status);
	Platform_LogFlush();
	Platform_Shutdown();
	Platform_LogShutdown();
	XLaunchNewImage(NULL, NULL);
	for (;;)
	{
		Sleep(1000);
	}
}

void Platform_Shutdown(void)
{
	if (s_platformInitialized == 0)
	{
		return;
	}

	s_platformInitialized = 0;

	Platform_InputShutdown();
	NativeAudio_Shutdown();
	NativeRenderer_Shutdown();

	Platform_LogShutdown();
}

void Platform_BeginFrame(void)
{
	/* Same note as the SDL backend: normal rendering begins from DrawOTag after
	 * the current draw env is installed; no host scene is started here. */
}

int Platform_BeginScene(void)
{
	if (s_platformBeginScene)
	{
		return 0;
	}

	NativeRenderer_BeginScene();

	if (activeDrawEnv.isbg)
	{
		const RECT16 clipenv = activeDrawEnv.clip;
		const u8 r = activeDrawEnv.r0;
		const u8 g = activeDrawEnv.g0;
		const u8 b = activeDrawEnv.b0;

		NativeRenderer_Clear(clipenv.x, clipenv.y, clipenv.w, clipenv.h, r, g, b);
	}

	s_platformBeginScene = 1;

	return 1;
}

void Platform_EndScene(void)
{
	u64 tStart;
	u64 tEndScene;
	u64 tPresent;
	u64 tEndGpu;
	static int s_endSceneTimingTrace = 0;
	static u64 s_lastEndSceneCounter = 0;
	static u64 s_periodMax = 0;
	static u64 s_periodSum = 0;
	static int s_periodFrames = 0;
	static DWORD s_periodReportMs = 0;

	if (!s_platformBeginScene)
	{
		return;
	}

	tStart = X360_GetCounter();

	/* Frame period = wall time between consecutive EndScene calls, i.e. the
	 * whole frame. Comparing it with the endScene/present/swap numbers below
	 * attributes the remaining time to the game-side work (session 9: the
	 * frame loop runs far below the 60 Hz vblank rate and the log volume was
	 * ruled out, so the split needs to be visible). */
	s_endSceneTimingTrace++;
	if (s_lastEndSceneCounter != 0)
	{
		u64 period = tStart - s_lastEndSceneCounter;
		DWORD nowMs = GetTickCount();
		s_periodSum += period;
		if (period > s_periodMax) s_periodMax = period;
		s_periodFrames++;
		if (nowMs - s_periodReportMs >= 5000)
		{
			Platform_Log("[perf] level=%d mode=%08x frames=%d periodAvg=%.1fms periodMax=%.1fms\n",
			             sdata->gGT->levelID, (unsigned)sdata->gGT->gameMode1, s_periodFrames,
			             Native_CounterToMs(s_periodSum) / s_periodFrames, Native_CounterToMs(s_periodMax));
			s_periodMax = 0; s_periodSum = 0; s_periodFrames = 0; s_periodReportMs = nowMs;
		}
	}
	else s_periodReportMs = GetTickCount();
	s_lastEndSceneCounter = tStart;

	s_platformBeginScene = 0;

	Platform_WatchStage("end-scene");
	NativeRenderer_EndScene();
	tEndScene = X360_GetCounter();

	if (s_pinnedVramDisplayFrames > 0)
	{
		static int s_pinnedDumpCount = 0;
		int dumpX;
		int dumpY;
		int dumpW;
		int dumpH;

		/* TEMPORARY: whole-display text map of what is actually shown, so a
		 * black screen can be told apart from "the right pixels are there but
		 * the wrong region/page is presented". Sampled a few times per run. */
		dumpW = (s_pinnedVramDisplayCustomRect != 0) ? s_pinnedVramDisplayW : 320;
		dumpH = (s_pinnedVramDisplayCustomRect != 0) ? s_pinnedVramDisplayH : 240;
		dumpX = (s_pinnedVramDisplayCustomRect != 0) ? s_pinnedVramDisplayX : activeDispEnv.disp.x;
		dumpY = (s_pinnedVramDisplayCustomRect != 0) ? s_pinnedVramDisplayY : activeDispEnv.disp.y;

		if ((s_pinnedDumpCount < 3) || ((s_pinnedDumpCount % 300) == 299))
		{
			NativeRenderer_DebugDumpVRAMRaw("pinned-display");
			NativeRenderer_DebugDumpVRAM(dumpX, dumpY, dumpW, dumpH, "pinned-display");
		}
		s_pinnedDumpCount++;

		if (s_pinnedVramDisplayCustomRect)
		{
			NativeRenderer_PresentVRAMRect(s_pinnedVramDisplayX, s_pinnedVramDisplayY, s_pinnedVramDisplayW, s_pinnedVramDisplayH);
		}
		else
		{
			NativeRenderer_PresentVRAMDisplay();
		}
		tPresent = X360_GetCounter();
		NativeRenderer_EndGpuFrame();
		tEndGpu = X360_GetCounter();
		NativeRenderer_SwapWindow();
		Platform_WatchBeat();
		s_pinnedVramDisplayFrames--;
		if (s_pinnedVramDisplayFrames <= 0)
		{
			s_pinnedVramDisplayCustomRect = 0;
		}

		if ((s_endSceneTimingTrace <= 4) || ((s_endSceneTimingTrace % 32) == 0))
		{
			Platform_Log("[timing] endScene=%.1fms present=%.1fms endGpu=%.1fms swap=%.1fms total=%.1fms\n",
			             Native_CounterToMs(tEndScene - tStart), Native_CounterToMs(tPresent - tEndScene),
			             Native_CounterToMs(tEndGpu - tPresent), Native_CounterToMs(X360_GetCounter() - tEndGpu),
			             Native_CounterToMs(X360_GetCounter() - tStart));
		}
		return;
	}

	/* Keep the displayed VRAM region current for screen-copy effects. */
	Platform_WatchStage("present");
	NativeRenderer_StoreFrameBuffer(activeDispEnv.disp.x, activeDispEnv.disp.y, activeDispEnv.disp.w, activeDispEnv.disp.h);
	NativeRenderer_PresentVRAMRect(activeDispEnv.disp.x, activeDispEnv.disp.y, activeDispEnv.disp.w, activeDispEnv.disp.h);
	tPresent = X360_GetCounter();
	Platform_WatchStage("end-gpu-frame");
	NativeRenderer_EndGpuFrame();
	tEndGpu = X360_GetCounter();
	Platform_WatchStage("swap");
	NativeRenderer_SwapWindow();
	Platform_WatchStage("game");
	Platform_WatchBeat();

	if ((s_endSceneTimingTrace <= 4) || ((s_endSceneTimingTrace % 32) == 0))
	{
		Platform_Log("[timing] endScene=%.1fms present=%.1fms endGpu=%.1fms swap=%.1fms total=%.1fms\n",
		             Native_CounterToMs(tEndScene - tStart), Native_CounterToMs(tPresent - tEndScene),
		             Native_CounterToMs(tEndGpu - tPresent), Native_CounterToMs(X360_GetCounter() - tEndGpu),
		             Native_CounterToMs(X360_GetCounter() - tStart));
	}
}

void Platform_EndFrame(void)
{
	Platform_EndScene();
	Platform_CalcFPS();
}

void Platform_PresentVRAMDisplay(void)
{
	Platform_PinVRAMDisplayFrames(1);
	Platform_BeginScene();
	Platform_EndFrame();
}

void Platform_PinVRAMDisplayFrames(int frameCount)
{
	if (frameCount > s_pinnedVramDisplayFrames)
	{
		s_pinnedVramDisplayFrames = frameCount;
		s_pinnedVramDisplayCustomRect = 0;
	}
}

void Platform_PinVRAMDisplayRect(int x, int y, int w, int h, int frameCount)
{
	if ((frameCount <= 0) || (w <= 0) || (h <= 0))
	{
		return;
	}

	s_pinnedVramDisplayX = x;
	s_pinnedVramDisplayY = y;
	s_pinnedVramDisplayW = w;
	s_pinnedVramDisplayH = h;
	s_pinnedVramDisplayFrames = frameCount;
	s_pinnedVramDisplayCustomRect = 1;
}

void Platform_PollHostEvents(void)
{
	XINPUT_STATE state;
	DWORD result;

	/* Quit chord: Back + Start, the console convention for "return to
	 * dashboard". Debug builds in Xenia can use the emulator's own quit. */
	result = XInputGetState(0, &state);
	if (result == ERROR_SUCCESS)
	{
		const WORD quitChord = XINPUT_GAMEPAD_BACK | XINPUT_GAMEPAD_START;
		if ((state.Gamepad.wButtons & quitChord) == quitChord)
		{
			Platform_Log("[CTR Native] quit chord pressed\n");
			Platform_Exit(0);
		}
#if defined(CTR_XSDK)
		/* Screenshots in test builds (SCREENSHOTS=1): Back + LB + RB, once per press. */
		{
			extern void NativeRenderer_RequestCapture(void);
			const WORD captureChord = XINPUT_GAMEPAD_BACK | XINPUT_GAMEPAD_LEFT_SHOULDER | XINPUT_GAMEPAD_RIGHT_SHOULDER;
			static int captureHeld;
			const int held = (state.Gamepad.wButtons & captureChord) == captureChord;
			if (held && !captureHeld)
			{
				NativeRenderer_RequestCapture();
			}
			captureHeld = held;
		}
#endif
	}
}

int Platform_PollInput(void)
{
	Platform_PollHostEvents();
	Platform_InputUpdate();
	return 1;
}

int NikoGetEnterKey(void)
{
	/* No host keyboard on console; the game's keyboard path is unused. */
	return 0;
}

/* ---------------------------------------------------------------------------------------
 * VBlank clock (ported from native_platform.c, wall clock swapped to QPC)
 * --------------------------------------------------------------------------------------- */

#define NATIVE_VBLANK_GPU_CYCLES 897619ull /* 3413 * 263 */
#define NATIVE_GPU_CLOCK_HZ      53693175ull
#define NATIVE_VSYNC_CATCHUP_MAX 8
#define NATIVE_VSYNC_SPIN_US     200
#define NATIVE_VSYNC_SLEEP_MS    1

global_variable u64 s_nextVBlankCounter = 0;
global_variable u64 s_vblankRemainder = 0;
global_variable int s_nativeVBlankCount = 0;

internal u64 Native_CounterFromMicroseconds(u64 freq, u64 microseconds)
{
	return (freq * microseconds) / 1000000;
}

internal void Native_AdvanceVBlankTarget(void)
{
	const u64 freq = X360_GetFrequency();
	const u64 numer = freq * NATIVE_VBLANK_GPU_CYCLES;

	s_nextVBlankCounter += numer / NATIVE_GPU_CLOCK_HZ;
	s_vblankRemainder += numer % NATIVE_GPU_CLOCK_HZ;
	if (s_vblankRemainder >= NATIVE_GPU_CLOCK_HZ)
	{
		s_nextVBlankCounter++;
		s_vblankRemainder -= NATIVE_GPU_CLOCK_HZ;
	}
}

internal void Native_EnsureVBlankTarget(void)
{
	const u64 now = X360_GetCounter();

	if (s_nextVBlankCounter == 0)
	{
		s_nextVBlankCounter = now;
		s_vblankRemainder = 0;
		Native_AdvanceVBlankTarget();
	}
}

internal void Native_WaitUntilVBlankTarget(void)
{
	const u64 freq = X360_GetFrequency();
	const u64 spinWindow = Native_CounterFromMicroseconds(freq, NATIVE_VSYNC_SPIN_US);

	while (1)
	{
		const u64 now = X360_GetCounter();

		if (now >= s_nextVBlankCounter)
		{
			return;
		}

		{
			const u64 remaining = s_nextVBlankCounter - now;
			if (remaining <= spinWindow)
			{
				/* Final window: spin so the emitter is paced by our clock. */
				while (X360_GetCounter() < s_nextVBlankCounter)
				{
				}
				return;
			}

			Sleep(NATIVE_VSYNC_SLEEP_MS);
		}
	}
}

#if defined(CTR_XSDK)
/* The TV's own vblanks, which xsdk_present_stats counts in its vblank
 * interrupt once vulkan4xenon has the display, are what frames show at. The
 * game's VBlanks follow them there. A frame's GPU work starts at its VBlank
 * (RenderVSYNC, then the present), so it now starts as the last frame flips,
 * with the whole refresh ahead of it. QPC's 59.83 Hz drifted against the
 * TV's 60 Hz, and the gap between the two came out of the GPU's time: frames
 * that fitted a refresh showed a refresh late, a few times a second, which
 * made the 30 updates a second uneven. QPC keeps the time before the display
 * opens and should its count stop. */
#define NATIVE_DISPLAY_SPIN_US  2000
#define NATIVE_DISPLAY_STALL_MS 100

global_variable int s_displayClock = 0;      /* the game's VBlanks follow the TV's */
global_variable u32 s_displayVBlank = 0;     /* the TV's vblank the last game VBlank stood for */
global_variable u32 s_displayProbe = 0;      /* the count seen while QPC kept the time */
global_variable u64 s_displaySeenAt = 0;     /* when a vblank was seen coming, by looking closely */
global_variable u32 s_displaySeenVBlank = 0;
global_variable u64 s_displayAnchorAt = 0;   /* the first vblank seen so, for the refresh's length */
global_variable u32 s_displayAnchorVBlank = 0;
global_variable u64 s_displayPeriod = 0;     /* a refresh in counter ticks */

internal u32 Native_DisplayVBlanks(void)
{
	XsdkPresentStats stats;

	xsdk_present_stats(&stats);
	return stats.vblanks;
}

internal int Native_DisplayClock(void)
{
	u32 shown;

	if (s_displayClock)
	{
		return 1;
	}

	/* A count that moves: the display is open and its interrupt runs. */
	shown = Native_DisplayVBlanks();
	if ((shown == 0) || (s_displayProbe == 0) || (shown == s_displayProbe))
	{
		s_displayProbe = shown;
		return 0;
	}

	s_displayClock = 1;
	s_displayVBlank = shown;
	s_displaySeenAt = 0;
	s_displayAnchorAt = 0;
	s_displayPeriod = X360_GetFrequency() / 60;
	Platform_Log("[timing] VBlanks follow the display's from its vblank %u\n", (unsigned)shown);
	return 1;
}

internal void Native_SeeDisplayVBlank(u64 at, u32 vblank)
{
	const u64 freq = X360_GetFrequency();

	if (s_displayAnchorAt == 0)
	{
		s_displayAnchorAt = at;
		s_displayAnchorVBlank = vblank;
	}
	else if (vblank - s_displayAnchorVBlank >= 60)
	{
		const u64 period = (at - s_displayAnchorAt) / (u64)(vblank - s_displayAnchorVBlank);

		if ((period > freq / 62) && (period < freq / 58))
		{
			s_displayPeriod = period;
		}
	}
	s_displaySeenAt = at;
	s_displaySeenVBlank = vblank;
}

/* Waits for the TV's vblank after s_displayVBlank: sleeps until it's near,
 * then looks for it closely. 0 when the count stopped. */
internal int Native_WaitForDisplayVBlank(void)
{
	const u64 freq = X360_GetFrequency();
	const u64 spinWindow = Native_CounterFromMicroseconds(freq, NATIVE_DISPLAY_SPIN_US);
	const u64 stall = Native_CounterFromMicroseconds(freq, (u64)NATIVE_DISPLAY_STALL_MS * 1000);
	const u64 start = X360_GetCounter();
	int looking = 0;

	while (1)
	{
		const u32 shown = Native_DisplayVBlanks();
		const u64 now = X360_GetCounter();

		if (shown != s_displayVBlank)
		{
			if (looking && (shown == s_displayVBlank + 1))
			{
				Native_SeeDisplayVBlank(now, shown);
			}
			return 1;
		}
		if (now - start > stall)
		{
			return 0;
		}
		if ((s_displaySeenAt != 0) &&
		    (now + spinWindow < s_displaySeenAt + s_displayPeriod * (u64)(s_displayVBlank + 1 - s_displaySeenVBlank)))
		{
			looking = 0;
			Sleep(NATIVE_VSYNC_SLEEP_MS);
		}
		else
		{
			looking = 1;
		}
	}
}
#endif

internal void Native_EmitVBlank(void)
{
	NativeRCnt_EmitVBlank();

	if (vsync_callback != NULL)
	{
		vsync_callback();
	}

	NativeAudio_StepVBlank();
	s_nativeVBlankCount++;
}

internal int Native_CatchUpDueVBlanks(void)
{
	int emittedVBlanks = 0;

#if defined(CTR_XSDK)
	if (Native_DisplayClock())
	{
		const u32 shown = Native_DisplayVBlanks();

		if (shown - s_displayVBlank > NATIVE_VSYNC_CATCHUP_MAX)
		{
			s_displayVBlank = shown;
			return 0;
		}
		while (s_displayVBlank != shown)
		{
			Native_EmitVBlank();
			emittedVBlanks++;
			s_displayVBlank++;
		}
		return emittedVBlanks;
	}
#endif

	Native_EnsureVBlankTarget();

	{
		const u64 now = X360_GetCounter();

		if (now >= s_nextVBlankCounter)
		{
			const u64 freq = X360_GetFrequency();
			const u64 step = (freq * NATIVE_VBLANK_GPU_CYCLES) / NATIVE_GPU_CLOCK_HZ;
			const u64 dueApprox = ((now - s_nextVBlankCounter) / step) + 1;

			if (dueApprox > NATIVE_VSYNC_CATCHUP_MAX)
			{
				s_nextVBlankCounter = now;
				s_vblankRemainder = 0;
				Native_AdvanceVBlankTarget();
				return 0;
			}
		}
	}

	while (X360_GetCounter() >= s_nextVBlankCounter)
	{
		const u64 now = X360_GetCounter();

		Native_EmitVBlank();
		emittedVBlanks++;

		if (emittedVBlanks >= NATIVE_VSYNC_CATCHUP_MAX)
		{
			s_nextVBlankCounter = now;
			s_vblankRemainder = 0;
			Native_AdvanceVBlankTarget();
			break;
		}

		Native_AdvanceVBlankTarget();
	}

	return emittedVBlanks;
}

internal void Native_WaitAndEmitVBlank(void)
{
	u64 tWaitStart = X360_GetCounter();
	u64 tWaitEnd;
	u64 tEmitEnd;
	static int s_vblankTimingTrace = 0;

	Platform_WatchStage("vblank-wait");
#if defined(CTR_XSDK)
	if (Native_DisplayClock())
	{
		if (Native_WaitForDisplayVBlank())
		{
			s_displayVBlank++;
		}
		else
		{
			Platform_Log("[timing] the display's vblanks stopped at %u; VBlanks follow QPC\n", (unsigned)s_displayVBlank);
			s_displayClock = 0;
			s_displayProbe = 0;
			s_nextVBlankCounter = 0;
		}
	}
	if (!s_displayClock)
#endif
	{
		Native_EnsureVBlankTarget();
		Native_WaitUntilVBlankTarget();
	}
	tWaitEnd = X360_GetCounter();
	Platform_WatchStage("vblank-emit");
	Native_EmitVBlank();
	tEmitEnd = X360_GetCounter();
	Native_AdvanceVBlankTarget();

	s_vblankTimingTrace++;
	if ((s_vblankTimingTrace <= 4) || ((s_vblankTimingTrace % 64) == 0))
	{
#if defined(CTR_XSDK)
		if (s_displayClock)
		{
			Platform_Log("[timing] vblank wait=%.1fms emit=%.1fms display=%u refresh=%.3fms\n",
			             Native_CounterToMs(tWaitEnd - tWaitStart), Native_CounterToMs(tEmitEnd - tWaitEnd),
			             (unsigned)s_displayVBlank, Native_CounterToMs(s_displayPeriod));
			return;
		}
#endif
		Platform_Log("[timing] vblank wait=%.1fms emit=%.1fms nextTargetIn=%.1fms\n",
		             Native_CounterToMs(tWaitEnd - tWaitStart), Native_CounterToMs(tEmitEnd - tWaitEnd),
		             Native_CounterToMs((s_nextVBlankCounter > tEmitEnd) ? (s_nextVBlankCounter - tEmitEnd) : 0));
	}
}

int VSync(int mode)
{
	int emittedVBlanks;
	int requestedVBlanks;
	static int s_vsyncTrace = 0;

	if (mode < 0)
	{
		return s_nativeVBlankCount;
	}

	requestedVBlanks = (mode == 0) ? 1 : mode;
	emittedVBlanks = 0;

	s_vsyncTrace++;
	if ((s_vsyncTrace <= 8) || ((s_vsyncTrace % 256) == 0))
	{
		Platform_Log("[trace] VSync#%d enter mode=%d\n", s_vsyncTrace, mode);
	}

	emittedVBlanks += Native_CatchUpDueVBlanks();

	{
		s32 i;
		for (i = 0; i < requestedVBlanks; i++)
		{
			Native_WaitAndEmitVBlank();
			emittedVBlanks++;
		}
	}

	if ((s_vsyncTrace <= 8) || ((s_vsyncTrace % 256) == 0))
	{
		Platform_Log("[trace] VSync#%d exit vblankCount=%d\n", s_vsyncTrace, s_nativeVBlankCount);
	}

	return s_nativeVBlankCount;
}

int Platform_GetVBlankCount(void)
{
	return s_nativeVBlankCount;
}

void Platform_CatchUpVBlanks(void)
{
	Native_CatchUpDueVBlanks();
}

void Platform_WaitUntilVBlank(int targetVBlank)
{
	int emittedVBlanks = 0;
	const int requestedVBlanks = targetVBlank - s_nativeVBlankCount;

	if (requestedVBlanks <= 0)
	{
		return;
	}

	emittedVBlanks += Native_CatchUpDueVBlanks();

	while (s_nativeVBlankCount < targetVBlank)
	{
		Native_WaitAndEmitVBlank();
		emittedVBlanks++;
	}
}
