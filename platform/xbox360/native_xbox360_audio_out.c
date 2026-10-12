/* ctr360: Xbox 360 audio output device layer.
 *
 * Implements the SDL3 audio-stream surface declared by
 * platform/xbox360/sdl_shim/SDL3/SDL.h, so platform/native_audio.c (the
 * SPU/XA emulation) runs unmodified.
 *
 * XAudio2 owns the device clock. A bounded queue pulls the SPU/XA mixer only
 * as source buffers are consumed; their PCM stays alive until playback ends.
 *
 * C89-clean; the XDK compiler builds this directly.
 */

#include <xtl.h>
#include <xaudio2.h>

#ifdef _DEBUG
#pragma comment(lib, "xaudiod2.lib")
#pragma comment(lib, "xmcored.lib")
#else
#pragma comment(lib, "xaudio2.lib")
#pragma comment(lib, "xmcore.lib")
#endif

#include <macros.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sdl_shim/SDL3/SDL.h"
#include <platform/native_log.h>

#define X360_AUDIO_PULL_FRAMES      512
#define X360_AUDIO_BUFFER_COUNT     8
#define X360_AUDIO_TARGET_BUFFERS   3
#define X360_AUDIO_BUFFER_BYTES     (X360_AUDIO_PULL_FRAMES * 2 * sizeof(s16))
#define X360_AUDIO_CAPTURE_FRAMES   (44100 * 10)

struct SDL_AudioStream
{
	SDL_AudioSpec spec;
	SDL_AudioStreamCallback callback;
	void *userdata;
	CRITICAL_SECTION lock;
	HANDLE thread;
	volatile LONG running;
	volatile LONG resumed;
	volatile LONG pullCount;
	IXAudio2 *engine;
	IXAudio2MasteringVoice *master;
	IXAudio2SourceVoice *voice;
	s16 pcm[X360_AUDIO_BUFFER_COUNT][X360_AUDIO_PULL_FRAMES * 2];
	u32 writeBuffer;
	u32 submitFailures;
	u32 nonzeroSamples;
	int captureEnabled;
	int captureDone;
	int raceCaptureStarted;
	FILE *capture;
	u32 capturedFrames;
};

global_variable int s_audioSubsystemInitialized = 0;
global_variable SDL_AudioStream *s_openStream = NULL;
global_variable char s_sdlError[128] = "no error";
global_variable char s_hintAudioDriver[64] = "";
global_variable char s_hintSampleFrames[64] = "";

internal void X360Audio_SetError(const char *operation, HRESULT result)
{
	_snprintf(s_sdlError, sizeof(s_sdlError) - 1, "%s failed: %08x", operation, (unsigned)result);
	s_sdlError[sizeof(s_sdlError) - 1] = '\0';
	Platform_Log("[CTR Audio] %s\n", s_sdlError);
}

internal void X360Audio_ReleaseVoices(SDL_AudioStream *stream)
{
	if (stream->voice != NULL) IXAudio2SourceVoice_DestroyVoice(stream->voice);
	if (stream->master != NULL) IXAudio2MasteringVoice_DestroyVoice(stream->master);
	if (stream->engine != NULL) IXAudio2_Release(stream->engine);
}

/* Opt-in capture contains only this game's mix, never system audio. The Xbox
 * PCM is native BE; the exported ordinary WAV uses explicit LE byte writes. */
internal void X360Audio_CaptureTitle(SDL_AudioStream *stream, const s16 *pcm, int frames)
{
	u8 bytes[X360_AUDIO_BUFFER_BYTES];
	u8 header[44];
	int i;
	if (!stream->captureEnabled) return;
	if (stream->captureDone)
	{
		if (stream->raceCaptureStarted || GAME_TRACKER == NULL ||
		    GAME_TRACKER->levelID != CRASH_COVE || sdata->Loading.stage != LOAD_IDLE ||
		    (GAME_TRACKER->gameMode1 & START_OF_RACE) != 0) return;
		stream->raceCaptureStarted = 1;
		stream->captureDone = 0;
		stream->capturedFrames = 0;
	}
	if (stream->capture == NULL)
	{
		if (!stream->raceCaptureStarted && (GAME_TRACKER == NULL || GAME_TRACKER->levelID != MAIN_MENU_LEVEL ||
		    D230.titleMenuState != TITLE_MENU_STATE_IN_MENU)) return;
		stream->capture = fopen(stream->raceCaptureStarted ? "cache:\\ctr360_race_audio.wav" : "cache:\\ctr360_title_audio.wav", "wb");
		if (stream->capture == NULL)
		{
			stream->captureDone = 1;
			Platform_Log("[CTR Audio] %s capture open failed\n", stream->raceCaptureStarted ? "race" : "title");
			return;
		}
		memset(header, 0, sizeof(header));
		fwrite(header, 1, sizeof(header), stream->capture);
		Platform_Log("[CTR Audio] %s capture started\n", stream->raceCaptureStarted ? "race" : "title");
	}
	if ((u32)frames > X360_AUDIO_CAPTURE_FRAMES - stream->capturedFrames)
		frames = X360_AUDIO_CAPTURE_FRAMES - stream->capturedFrames;
	for (i = 0; i < frames * 2; i++)
	{
		bytes[i * 2] = (u8)pcm[i];
		bytes[i * 2 + 1] = (u8)((u16)pcm[i] >> 8);
	}
	fwrite(bytes, 4, frames, stream->capture);
	stream->capturedFrames += frames;
	if (stream->capturedFrames == X360_AUDIO_CAPTURE_FRAMES)
	{
		memset(header, 0, sizeof(header));
		memcpy(header, "RIFF", 4);
		CTR_WriteU32LE(header + 4, 36 + stream->capturedFrames * 4);
		memcpy(header + 8, "WAVEfmt ", 8);
		CTR_WriteU32LE(header + 16, 16);
		CTR_WriteU16LE(header + 20, 1);
		CTR_WriteU16LE(header + 22, 2);
		CTR_WriteU32LE(header + 24, stream->spec.freq);
		CTR_WriteU32LE(header + 28, stream->spec.freq * 4);
		CTR_WriteU16LE(header + 32, 4);
		CTR_WriteU16LE(header + 34, 16);
		memcpy(header + 36, "data", 4);
		CTR_WriteU32LE(header + 40, stream->capturedFrames * 4);
		fseek(stream->capture, 0, SEEK_SET);
		fwrite(header, 1, sizeof(header), stream->capture);
		fclose(stream->capture);
		stream->capture = NULL;
		stream->captureDone = 1;
		Platform_Log("[CTR Audio] %s capture finished: %u frames\n", stream->raceCaptureStarted ? "race" : "title", stream->capturedFrames);
	}
}

internal DWORD WINAPI X360Audio_ThreadProc(LPVOID parameter)
{
	SDL_AudioStream *stream = (SDL_AudioStream *)parameter;
	const int requestBytes = X360_AUDIO_PULL_FRAMES * stream->spec.channels * (int)sizeof(s16);
	DWORD lastReport = GetTickCount();
	XAUDIO2_VOICE_STATE state;
	LONG reportPulls;
	u32 reportNonzero;
	u32 reportFailures;
	int report;

	while (stream->running)
	{
		report = 0;
		Sleep(1);
		RtlEnterCriticalSection(&stream->lock);
		IXAudio2SourceVoice_GetState(stream->voice, &state, 0);
		if (stream->resumed && state.BuffersQueued < X360_AUDIO_TARGET_BUFFERS && stream->callback != NULL)
		{
			stream->callback(stream->userdata, stream, requestBytes, 0);
			stream->pullCount++;
		}
		if (GetTickCount() - lastReport >= 5000)
		{
			reportPulls = stream->pullCount;
			reportNonzero = stream->nonzeroSamples;
			reportFailures = stream->submitFailures;
			report = 1;
			lastReport = GetTickCount();
		}
		RtlLeaveCriticalSection(&stream->lock);
		/* A durable USB log flush can block. Never hold the SPU/mixer lock
		 * across it: game-side sound register writes take this same lock. */
		if (report)
			Platform_Log("[CTR Audio] device callbacks=%d buffers=%u played=%I64u nonzero=%u failures=%u\n",
			             reportPulls, state.BuffersQueued, state.SamplesPlayed, reportNonzero, reportFailures);
	}
	return 0;
}

int SDL_InitSubSystem(u32 flags)
{
	if ((flags & SDL_INIT_AUDIO) != 0)
	{
		s_audioSubsystemInitialized = 1;
	}

	return 1;
}

void SDL_QuitSubSystem(u32 flags)
{
	if ((flags & SDL_INIT_AUDIO) != 0)
	{
		s_audioSubsystemInitialized = 0;
	}
}

SDL_AudioStream *SDL_OpenAudioDeviceStream(SDL_AudioDeviceID devid, const SDL_AudioSpec *spec, SDL_AudioStreamCallback callback, void *userdata)
{
	SDL_AudioStream *stream;
	DWORD threadId = 0;
	WAVEFORMATEX format;
	HRESULT result;
	FILE *captureConfig;

	(void)devid;

	if (spec == NULL || spec->format != SDL_AUDIO_S16 || spec->channels != 2 || spec->freq != 44100)
	{
		return NULL;
	}

	stream = (SDL_AudioStream *)malloc(sizeof(struct SDL_AudioStream));
	if (stream == NULL)
	{
		return NULL;
	}

	memset(stream, 0, sizeof(*stream));
	stream->spec = *spec;
	stream->callback = callback;
	stream->userdata = userdata;
	RtlInitializeCriticalSection(&stream->lock);
	memset(&format, 0, sizeof(format));
	format.wFormatTag = WAVE_FORMAT_PCM;
	format.nChannels = (WORD)spec->channels;
	format.nSamplesPerSec = spec->freq;
	format.wBitsPerSample = 16;
	format.nBlockAlign = (WORD)(spec->channels * sizeof(s16));
	format.nAvgBytesPerSec = format.nSamplesPerSec * format.nBlockAlign;
	result = XAudio2Create(&stream->engine, 0, XAUDIO2_DEFAULT_PROCESSOR);
	if (SUCCEEDED(result))
		result = IXAudio2_CreateMasteringVoice(stream->engine, &stream->master, 2, 48000, 0, 0, NULL);
	if (SUCCEEDED(result))
		result = IXAudio2_CreateSourceVoice(stream->engine, &stream->voice, &format, 0, XAUDIO2_DEFAULT_FREQ_RATIO, NULL, NULL, NULL);
	if (FAILED(result))
	{
		X360Audio_SetError("device creation", result);
		X360Audio_ReleaseVoices(stream);
		RtlDeleteCriticalSection(&stream->lock);
		free(stream);
		return NULL;
	}
	captureConfig = fopen("cache:\\ctr360_audio_capture.txt", "rb");
	if (captureConfig != NULL)
	{
		stream->captureEnabled = fgetc(captureConfig) == '1';
		fclose(captureConfig);
	}
	stream->running = 1;

	Platform_Log("[CTR Audio] device stream opened: %d Hz / %d ch / fmt 0x%08X\n", spec->freq, spec->channels, (unsigned)spec->format);
	stream->thread = CreateThread(NULL, 0, X360Audio_ThreadProc, stream, 0, &threadId);
	if (stream->thread == NULL)
	{
		X360Audio_ReleaseVoices(stream);
		RtlDeleteCriticalSection(&stream->lock);
		free(stream);
		return NULL;
	}

	/* The audio pull thread is not latency critical and must never contend
	 * with the render thread for a core; keep it on a hardware thread the
	 * game does not use for its main loop where possible. */
	XSetThreadProcessor(stream->thread, 4);

	s_openStream = stream;
	return stream;
}

SDL_AudioDeviceID SDL_GetAudioStreamDevice(SDL_AudioStream *stream)
{
	(void)stream;
	return SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK;
}

int SDL_GetAudioDeviceFormat(SDL_AudioDeviceID devid, SDL_AudioSpec *spec, int *sampleFrames)
{
	(void)devid;

	if (spec == NULL)
	{
		return 0;
	}

	if (s_openStream != NULL)
	{
		*spec = s_openStream->spec;
	}
	else
	{
		spec->format = SDL_AUDIO_S16;
		spec->channels = 2;
		spec->freq = 44100;
	}

	if (sampleFrames != NULL)
	{
		*sampleFrames = X360_AUDIO_PULL_FRAMES;
	}
	spec->freq = 48000;

	return 1;
}

int SDL_GetAudioStreamFormat(SDL_AudioStream *stream, SDL_AudioSpec *srcSpec, SDL_AudioSpec *dstSpec)
{
	if (stream == NULL)
	{
		return 0;
	}

	if (srcSpec != NULL)
	{
		*srcSpec = stream->spec;
	}
	if (dstSpec != NULL)
	{
		*dstSpec = stream->spec;
		dstSpec->freq = 48000;
	}

	return 1;
}

int SDL_ResumeAudioStreamDevice(SDL_AudioStream *stream)
{
	HRESULT result;
	if (stream == NULL) return 0;
	RtlEnterCriticalSection(&stream->lock);
	result = IXAudio2SourceVoice_Start(stream->voice, 0, 0);
	if (SUCCEEDED(result)) stream->resumed = 1;
	else X360Audio_SetError("voice start", result);
	RtlLeaveCriticalSection(&stream->lock);
	return SUCCEEDED(result);
}

void SDL_DestroyAudioStream(SDL_AudioStream *stream)
{
	if (stream == NULL)
	{
		return;
	}

	InterlockedExchange(&stream->running, 0);

	if (stream->thread != NULL)
	{
		/* Do not free mixer state while its worker still owns it. */
		WaitForSingleObject(stream->thread, INFINITE);
		CloseHandle(stream->thread);
	}
	if (stream->capture != NULL) fclose(stream->capture);
	X360Audio_ReleaseVoices(stream);
	RtlDeleteCriticalSection(&stream->lock);
	free(stream);

	if (s_openStream == stream)
	{
		s_openStream = NULL;
	}
}

int SDL_PutAudioStreamData(SDL_AudioStream *stream, const void *data, int len)
{
	XAUDIO2_BUFFER buffer;
	XAUDIO2_VOICE_STATE state;
	HRESULT result;
	s16 *pcm;
	int i;
	if (stream == NULL || data == NULL || len <= 0 || (u32)len > X360_AUDIO_BUFFER_BYTES || len % 4 != 0)
	{
		return 0;
	}

	RtlEnterCriticalSection(&stream->lock);
	IXAudio2SourceVoice_GetState(stream->voice, &state, XAUDIO2_VOICE_NOSAMPLESPLAYED);
	if (state.BuffersQueued >= X360_AUDIO_TARGET_BUFFERS)
	{
		RtlLeaveCriticalSection(&stream->lock);
		return 0;
	}
	pcm = stream->pcm[stream->writeBuffer];
	/* Stop/flush is asynchronous. A retained current buffer may be far from
	 * the newest submissions after repeated clears; never reuse its storage. */
	if (state.pCurrentBufferContext == pcm)
	{
		stream->writeBuffer = (stream->writeBuffer + 1) % X360_AUDIO_BUFFER_COUNT;
		pcm = stream->pcm[stream->writeBuffer];
	}
	memcpy(pcm, data, len);
	memset(&buffer, 0, sizeof(buffer));
	buffer.AudioBytes = len;
	buffer.pAudioData = (const BYTE *)pcm;
	buffer.pContext = pcm;
	/* XDK PCM16 input uses native samples (see ATG WaveFile::ReadSample). */
	result = IXAudio2SourceVoice_SubmitSourceBuffer(stream->voice, &buffer, NULL);
	if (SUCCEEDED(result))
	{
		stream->writeBuffer = (stream->writeBuffer + 1) % X360_AUDIO_BUFFER_COUNT;
		for (i = 0; i < len / (int)sizeof(s16); i++)
			if (pcm[i] != 0) stream->nonzeroSamples++;
		X360Audio_CaptureTitle(stream, pcm, len / 4);
	}
	else
	{
		stream->submitFailures++;
		if (stream->submitFailures == 1) X360Audio_SetError("buffer submission", result);
	}
	RtlLeaveCriticalSection(&stream->lock);
	return SUCCEEDED(result);
}

int SDL_GetAudioStreamQueued(SDL_AudioStream *stream)
{
	XAUDIO2_VOICE_STATE state;

	if (stream == NULL)
	{
		return 0;
	}

	RtlEnterCriticalSection(&stream->lock);
	IXAudio2SourceVoice_GetState(stream->voice, &state, XAUDIO2_VOICE_NOSAMPLESPLAYED);
	RtlLeaveCriticalSection(&stream->lock);

	return (int)(state.BuffersQueued * X360_AUDIO_BUFFER_BYTES);
}

int SDL_ClearAudioStream(SDL_AudioStream *stream)
{
	if (stream == NULL)
	{
		return 0;
	}

	RtlEnterCriticalSection(&stream->lock);
	IXAudio2SourceVoice_Stop(stream->voice, 0, 0);
	IXAudio2SourceVoice_FlushSourceBuffers(stream->voice);
	if (stream->resumed) IXAudio2SourceVoice_Start(stream->voice, 0, 0);
	RtlLeaveCriticalSection(&stream->lock);

	return 1;
}

int SDL_LockAudioStream(SDL_AudioStream *stream)
{
	if (stream == NULL)
	{
		return 0;
	}

	RtlEnterCriticalSection(&stream->lock);
	return 1;
}

int SDL_UnlockAudioStream(SDL_AudioStream *stream)
{
	if (stream == NULL)
	{
		return 0;
	}

	RtlLeaveCriticalSection(&stream->lock);
	return 1;
}

const char *SDL_GetCurrentAudioDriver(void)
{
	return "xbox360-xaudio2";
}

const char *SDL_GetError(void)
{
	return s_sdlError;
}

const char *SDL_GetHint(const char *name)
{
	if (name == NULL)
	{
		return NULL;
	}

	if (strcmp(name, SDL_HINT_AUDIO_DRIVER) == 0)
	{
		return s_hintAudioDriver[0] != '\0' ? s_hintAudioDriver : NULL;
	}
	if (strcmp(name, SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES) == 0)
	{
		return s_hintSampleFrames[0] != '\0' ? s_hintSampleFrames : NULL;
	}

	return NULL;
}

int SDL_SetHint(const char *name, const char *value)
{
	if ((name == NULL) || (value == NULL))
	{
		return 0;
	}

	if (strcmp(name, SDL_HINT_AUDIO_DRIVER) == 0)
	{
		strncpy(s_hintAudioDriver, value, sizeof(s_hintAudioDriver) - 1);
		return 1;
	}
	if (strcmp(name, SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES) == 0)
	{
		strncpy(s_hintSampleFrames, value, sizeof(s_hintSampleFrames) - 1);
		return 1;
	}

	return 1;
}
