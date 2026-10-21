/* xSDK output for the existing SPU/XA mixer. Kernel callbacks only copy words;
 * mixing and 44.1 -> 48 kHz resampling run on hardware thread 2. */
#include <SDL3/SDL.h>
#include <xsdk/kernel.h>
#include <xsdk/thread.h>
#include <pthread.h>
#include <string.h>
#include <stdint.h>
enum { XA_SAMPLES=256, XA_CHANNELS=6, XA_WORDS=1536, XA_RING=8, SRC_RING=4096 };
struct SDL_AudioStream {
    SDL_AudioSpec spec;
    SDL_AudioStreamCallback callback;
    void *userdata;
    pthread_mutex_t mutex;
    pthread_t worker;
    uint32_t running,driver,read,write;
    uint32_t ready[XA_RING][XA_WORDS];
    uint32_t *frames;
    uint32_t next;
    s16 source[SRC_RING][2];
    unsigned sourceRead,sourceWrite,phase;
};
static SDL_AudioStream xsAudio;
static int xsAudioOpen;
static void XsdkAudioCallback(const uint32_t *context)
{
    (void)context;
    SDL_AudioStream *s=&xsAudio;
    uint32_t driver=__atomic_load_n(&s->driver,__ATOMIC_ACQUIRE);
    if (!driver) return;
    uint32_t read=__atomic_load_n(&s->read,__ATOMIC_RELAXED);
    uint32_t write=__atomic_load_n(&s->write,__ATOMIC_ACQUIRE);
    uint32_t *frame=s->frames+(s->next++%2)*XA_WORDS;
    if (read!=write) {
        memcpy(frame,s->ready[read%XA_RING],XA_WORDS*sizeof(uint32_t));
        __atomic_store_n(&s->read,read+1,__ATOMIC_RELEASE);
    } else memset(frame,0,XA_WORDS*sizeof(uint32_t));
    XAudioSubmitRenderDriverFrame(driver,(const float *)frame);
}
static void *XsdkAudioWorker(void *arg)
{
    SDL_AudioStream *s=arg;
    xsdk_thread_move(2);
    while (__atomic_load_n(&s->running,__ATOMIC_ACQUIRE)) {
        unsigned write=__atomic_load_n(&s->write,__ATOMIC_RELAXED);
        unsigned read=__atomic_load_n(&s->read,__ATOMIC_ACQUIRE);
        if (write-read>=4) { xsdk_thread_sleep(1); continue; }
        pthread_mutex_lock(&s->mutex);
        memset(s->ready[write%XA_RING],0,XA_WORDS*sizeof(uint32_t));
        for (unsigned i=0;i<XA_SAMPLES;i++) {
            if (s->sourceWrite-s->sourceRead<2)
                s->callback(s->userdata,s,1024,1024);
            if (s->sourceWrite-s->sourceRead<2) {
                s->source[s->sourceWrite++%SRC_RING][0]=0;
                s->source[(s->sourceWrite-1)%SRC_RING][1]=0;
                continue;
            }
            const s16 *a=s->source[s->sourceRead%SRC_RING];
            const s16 *b=s->source[(s->sourceRead+1)%SRC_RING];
            float frac=(float)s->phase/48000.0f;
            for (unsigned channel=0;channel<2;channel++) {
                float sample=((float)a[channel]+((float)b[channel]-a[channel])*frac)/32768.0f;
                memcpy(&s->ready[write%XA_RING][channel*XA_SAMPLES+i],&sample,sizeof(sample));
            }
            s->phase+=44100;
            if (s->phase>=48000) { s->phase-=48000;s->sourceRead++; }
        }
        pthread_mutex_unlock(&s->mutex);
        __atomic_store_n(&s->write,write+1,__ATOMIC_RELEASE);
    }
    return NULL;
}
int SDL_InitSubSystem(u32 flags) { (void)flags;return 1; }
void SDL_QuitSubSystem(u32 flags) { (void)flags; }
SDL_AudioStream *SDL_OpenAudioDeviceStream(SDL_AudioDeviceID device,const SDL_AudioSpec *spec,SDL_AudioStreamCallback callback,void *userdata)
{
    (void)device;
    if (xsAudioOpen || spec->freq!=44100 || spec->channels!=2 || spec->format!=SDL_AUDIO_S16) return NULL;
    SDL_AudioStream *s=&xsAudio;
    /* Retain callback-visible physical storage until the title exits. */
    uint32_t *frames=s->frames;
    memset(s,0,sizeof(*s));s->frames=frames;
    if (!s->frames) s->frames=MmAllocatePhysicalMemoryEx(0,2*XA_WORDS*4,PAGE_READWRITE,0,UINT32_MAX,0);
    if (!s->frames) return NULL;
    s->spec=*spec;s->callback=callback;s->userdata=userdata;
    pthread_mutexattr_t attr;pthread_mutexattr_init(&attr);
    pthread_mutexattr_settype(&attr,PTHREAD_MUTEX_RECURSIVE);
    pthread_mutex_init(&s->mutex,&attr);pthread_mutexattr_destroy(&attr);
    xsAudioOpen=1;return s;
}
int SDL_ResumeAudioStreamDevice(SDL_AudioStream *s)
{
    if (__atomic_load_n(&s->running,__ATOMIC_ACQUIRE)) return 1;
    __atomic_store_n(&s->running,1,__ATOMIC_RELEASE);
    if (pthread_create(&s->worker,NULL,XsdkAudioWorker,s)) { s->running=0;return 0; }
    /* Prime the queue before the kernel can ask for its first frame. */
    while (__atomic_load_n(&s->write,__ATOMIC_ACQUIRE)<2) xsdk_thread_sleep(1);
    XAUDIO_RENDER_DRIVER_CLIENT client={.callback=XsdkAudioCallback,.context=0};
    uint32_t driver=0;
    if (XAudioRegisterRenderDriverClient(&client,&driver)!=ERROR_SUCCESS) {
        __atomic_store_n(&s->running,0,__ATOMIC_RELEASE);pthread_join(s->worker,NULL);return 0;
    }
    __atomic_store_n(&s->driver,driver,__ATOMIC_RELEASE);return 1;
}
void SDL_DestroyAudioStream(SDL_AudioStream *s)
{
    uint32_t driver=__atomic_exchange_n(&s->driver,0,__ATOMIC_ACQ_REL);
    if (driver) XAudioUnregisterRenderDriverClient(driver);
    if (__atomic_exchange_n(&s->running,0,__ATOMIC_ACQ_REL)) pthread_join(s->worker,NULL);
    pthread_mutex_destroy(&s->mutex);xsAudioOpen=0;
}
int SDL_PutAudioStreamData(SDL_AudioStream *s,const void *data,int bytes)
{
    if (bytes<0 || bytes%4 || (unsigned)(bytes/4)>SRC_RING-(s->sourceWrite-s->sourceRead)) return 0;
    const s16 *samples=data;
    for(int i=0;i<bytes/4;i++) { unsigned slot=s->sourceWrite++%SRC_RING;s->source[slot][0]=samples[2*i];s->source[slot][1]=samples[2*i+1]; }
    return 1;
}
int SDL_GetAudioStreamQueued(SDL_AudioStream *s) { return (int)((s->sourceWrite-s->sourceRead)*4); }
int SDL_ClearAudioStream(SDL_AudioStream *s) { SDL_LockAudioStream(s);s->sourceRead=s->sourceWrite;s->phase=0;SDL_UnlockAudioStream(s);return 1; }
int SDL_LockAudioStream(SDL_AudioStream *s) { return pthread_mutex_lock(&s->mutex)==0; }
int SDL_UnlockAudioStream(SDL_AudioStream *s) { return pthread_mutex_unlock(&s->mutex)==0; }
SDL_AudioDeviceID SDL_GetAudioStreamDevice(SDL_AudioStream *s) { (void)s;return 1; }
int SDL_GetAudioDeviceFormat(SDL_AudioDeviceID id,SDL_AudioSpec *spec,int *frames) { (void)id;*spec=xsAudio.spec;if(frames)*frames=256;return 1; }
int SDL_GetAudioStreamFormat(SDL_AudioStream *s,SDL_AudioSpec *src,SDL_AudioSpec *dst) { if(src)*src=s->spec;if(dst)*dst=s->spec;return 1; }
const char *SDL_GetCurrentAudioDriver(void) { return "xsdk"; }
const char *SDL_GetError(void) { return "xSDK audio output unavailable"; }
const char *SDL_GetHint(const char *name) { (void)name;return NULL; }
int SDL_SetHint(const char *name,const char *value) { (void)name;(void)value;return 1; }
