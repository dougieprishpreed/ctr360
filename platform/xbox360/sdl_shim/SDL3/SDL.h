/* ctr360: minimal SDL3 surface for the Xbox 360 build.
 *
 * Only platform/native_audio.c includes <SDL3/SDL.h> in this build (the SDL
 * window/input/perf backends are replaced by platform/xbox360/*.c), and it
 * needs exactly the audio-output symbols below. Keeping the shim to that
 * bounded surface means native_audio.c stays byte-identical to upstream and
 * the port lets the SPU/XA emulation run unchanged, with the device layer
 * implemented once, in native_xbox360_audio_out.c.
 *
 * C89-clean; the XDK compiler builds this directly.
 */

#ifndef CTR360_SDL3_SHIM_H
#define CTR360_SDL3_SHIM_H

#include <macros.h>

#define SDLCALL

#define SDL_INIT_AUDIO 0x00000010u

typedef u32 SDL_AudioDeviceID;
typedef struct SDL_AudioStream SDL_AudioStream;

#define SDL_AUDIO_S16 0x8010

typedef struct SDL_AudioSpec
{
	int format;
	int channels;
	int freq;
} SDL_AudioSpec;

#define SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK ((SDL_AudioDeviceID)0xFFFFFFFFu)

#define SDL_HINT_AUDIO_DRIVER               "SDL_AUDIO_DRIVER"
#define SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES "SDL_AUDIO_DEVICE_SAMPLE_FRAMES"

typedef void(SDLCALL *SDL_AudioStreamCallback)(void *userdata, SDL_AudioStream *stream, int additionalAmount, int totalAmount);

/* Implemented in native_xbox360_audio_out.c */
int SDL_InitSubSystem(u32 flags);
void SDL_QuitSubSystem(u32 flags);

SDL_AudioStream *SDL_OpenAudioDeviceStream(SDL_AudioDeviceID devid, const SDL_AudioSpec *spec, SDL_AudioStreamCallback callback, void *userdata);
SDL_AudioDeviceID SDL_GetAudioStreamDevice(SDL_AudioStream *stream);
int SDL_GetAudioDeviceFormat(SDL_AudioDeviceID devid, SDL_AudioSpec *spec, int *sampleFrames);
int SDL_GetAudioStreamFormat(SDL_AudioStream *stream, SDL_AudioSpec *srcSpec, SDL_AudioSpec *dstSpec);
int SDL_ResumeAudioStreamDevice(SDL_AudioStream *stream);
void SDL_DestroyAudioStream(SDL_AudioStream *stream);

int SDL_PutAudioStreamData(SDL_AudioStream *stream, const void *data, int len);
int SDL_GetAudioStreamQueued(SDL_AudioStream *stream);
int SDL_ClearAudioStream(SDL_AudioStream *stream);
int SDL_LockAudioStream(SDL_AudioStream *stream);
int SDL_UnlockAudioStream(SDL_AudioStream *stream);

const char *SDL_GetCurrentAudioDriver(void);
const char *SDL_GetError(void);
const char *SDL_GetHint(const char *name);
int SDL_SetHint(const char *name, const char *value);

#endif
