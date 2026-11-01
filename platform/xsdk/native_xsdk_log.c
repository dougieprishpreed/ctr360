#include <platform/native_log.h>
#include <xsdk/log.h>
#include <xsdk/kernel.h>
#include <xsdk/thread.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
/* The SDK writes bytes synchronously, in chunks of at most 511. Coalesce the
 * many short game probes, keeping diagnostics available within one second.
 * Driver messages continue to use the SDK's own immediate, locked sink. */
enum { XSDK_LOG_BUFFER_BYTES=8192, XSDK_LOG_THRESHOLD=4096 };
static RTL_CRITICAL_SECTION xsdkGameLogLock;
static char xsdkGameLogBuffer[XSDK_LOG_BUFFER_BYTES];
static unsigned xsdkGameLogLength,xsdkGameLogLastFlush;
static void XsdkLogFlushLocked(void)
{
    if(xsdkGameLogLength)xsdk_log_write_bytes(xsdkGameLogBuffer,xsdkGameLogLength);
    xsdkGameLogLength=0;xsdkGameLogLastFlush=GetTickCount();
}
static void XsdkLogV(const char *fmt, va_list args,int force)
{
    char text[2048]; vsnprintf(text,sizeof(text),fmt,args);
    unsigned category=Platform_TraceClassify(text);
    if (category && !Platform_TraceEnabled(category)) return;
    size_t length=strlen(text);
    int immediate=force || !strncmp(text,"[boot]",6) || !strncmp(text,"[fault]",7) ||
        !strncmp(text,"[CTR Native]",12) || !strncmp(text,"[vulkan",7) ||
        !strncmp(text,"[memcard]",9) || strstr(text,"guard") || strstr(text,"invalid");
    RtlEnterCriticalSection(&xsdkGameLogLock);
    if(xsdkGameLogLength+length>sizeof(xsdkGameLogBuffer))XsdkLogFlushLocked();
    memcpy(xsdkGameLogBuffer+xsdkGameLogLength,text,length);xsdkGameLogLength+=(unsigned)length;
    if(immediate || xsdkGameLogLength>=XSDK_LOG_THRESHOLD || GetTickCount()-xsdkGameLogLastFlush>=1000)
        XsdkLogFlushLocked();
    RtlLeaveCriticalSection(&xsdkGameLogLock);
}
/* Hang watchdog. The frame loop beats once a frame; when no beat comes for
 * 3 s, a thread of its own writes where the main thread last was straight to
 * the SDK's sink, so a hard lock leaves its place in default.log, and again
 * every 10 s while it lasts. tick is the thread tick being run, if any: look
 * it up in that build's ctr360.map. */
static const char *volatile xsdkWatchStage="boot";
static const void *volatile xsdkWatchTick;
static volatile unsigned xsdkWatchBeat;
/* The freeze trace (native_log.h). A console that stops keeps neither the
 * buffered lines nor what the file system hadn't written yet, and the podium
 * hang stopped the watchdog too, so these lines go to a file of their own and
 * are synced one by one. Test builds only (build.sh with FREEZE_TRACE=1). */
#ifndef CTR360_FREEZE_TRACE
#define CTR360_FREEZE_TRACE 0
#endif
static int xsdkFreezeFd=-1,xsdkFreezeOpened;
static unsigned xsdkFreezeFrames,xsdkFreezeClose,xsdkFreezeStartMs;
static void XsdkFreezeLineV(const char *fmt,va_list args)
{
    char line[256];
    int length=snprintf(line,sizeof(line),"%7u ms f%u ",(unsigned)(GetTickCount()-xsdkFreezeStartMs),xsdkWatchBeat);
    if(length<0 || xsdkFreezeFd<0) return;
    int room=(int)sizeof(line)-1-length,more=vsnprintf(line+length,(size_t)room,fmt,args);
    length+=more<0 ? 0 : more<room ? more : room-1;
    line[length++]='\n';
    if(write(xsdkFreezeFd,line,(size_t)length)!=length || fsync(xsdkFreezeFd)!=0)
    {
        close(xsdkFreezeFd);xsdkFreezeFd=-1;xsdkFreezeFrames=xsdkFreezeClose=0;
    }
}
static void XsdkFreezeLine(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkFreezeLineV(fmt,args); va_end(args); }
void Platform_FreezeTraceOpen(const char *why,unsigned frames,unsigned closeFrames)
{
    if(!CTR360_FREEZE_TRACE) return;
    if(!xsdkFreezeOpened)
    {
        xsdkFreezeOpened=1;xsdkFreezeStartMs=GetTickCount();
        xsdkFreezeFd=open("game:/freeze_trace.log",O_WRONLY|O_CREAT|O_TRUNC,0666);
        if(xsdkFreezeFd<0) Platform_LogWarn("[freeze-trace] game:/freeze_trace.log couldn't be opened\n");
    }
    if(xsdkFreezeFd<0) return;
    if(frames>xsdkFreezeFrames) xsdkFreezeFrames=frames;
    if(closeFrames>xsdkFreezeClose) xsdkFreezeClose=closeFrames;
    XsdkFreezeLine("open: %s, for %u frames, stages for %u",why,xsdkFreezeFrames,xsdkFreezeClose);
}
void Platform_FreezeTrace(const char *fmt,...)
{
    if(!xsdkFreezeFrames) return;
    va_list args; va_start(args,fmt); XsdkFreezeLineV(fmt,args); va_end(args);
}
void Platform_WatchStage(const char *stage) { xsdkWatchStage=stage; if(xsdkFreezeClose) XsdkFreezeLine("stage %s",stage); }
void Platform_WatchTick(const void *tick) { xsdkWatchTick=tick; }
void Platform_WatchBeat(void)
{
    xsdkWatchBeat++;
    if(!xsdkFreezeFrames) return;
    struct GameTracker *gGT=sdata->gGT;
    XsdkFreezeLine("frame shown: level=%d mode1=%08x mode2=%08x",gGT?(int)gGT->levelID:-1,
        gGT?(unsigned)gGT->gameMode1:0u,gGT?(unsigned)gGT->gameMode2:0u);
    if(xsdkFreezeClose) xsdkFreezeClose--;
    if(!--xsdkFreezeFrames) XsdkFreezeLine("closed");
}
static uint32_t XsdkWatchdog(void *context)
{
    (void)context;
    unsigned last=xsdkWatchBeat,stalledMs=0;
    for(;;) {
        xsdk_thread_sleep(500);
        unsigned beat=xsdkWatchBeat;
        if(beat!=last) { last=beat;stalledMs=0;continue; }
        stalledMs+=500;
        if(stalledMs<3000 || (stalledMs-3000)%10000) continue;
        struct GameTracker *gGT=sdata->gGT;
        char line[256];
        snprintf(line,sizeof(line),"[watchdog] no frame for %u ms after frame %u: stage=%s tick=%08x level=%d mode1=%08x mode2=%08x\n",
            stalledMs,beat,xsdkWatchStage,(unsigned)(uintptr_t)xsdkWatchTick,gGT?(int)gGT->levelID:-1,
            gGT?(unsigned)gGT->gameMode1:0u,gGT?(unsigned)gGT->gameMode2:0u);
        /* The buffered lines first, unless the stuck thread holds the buffer. */
        if(RtlTryEnterCriticalSection(&xsdkGameLogLock)) { XsdkLogFlushLocked();RtlLeaveCriticalSection(&xsdkGameLogLock); }
        xsdk_log_write_bytes(line,strlen(line));
    }
    return 0;
}
int Platform_LogSetPath(const char *p) { (void)p; return 0; }
const char *Platform_LogGetPath(void) { return "game:/default.log"; }
void Platform_LogInit(const char *name)
{
    (void)name;RtlInitializeCriticalSection(&xsdkGameLogLock);
    xsdkGameLogLength=0;xsdkGameLogLastFlush=GetTickCount();
    HANDLE watchdog;
    if(xsdk_thread_create_on(&watchdog,0,XsdkWatchdog,NULL,5)<0) xsdk_log_write_bytes("[watchdog] not started\n",23);
}
void Platform_LogFlush(void)
{
    RtlEnterCriticalSection(&xsdkGameLogLock);XsdkLogFlushLocked();RtlLeaveCriticalSection(&xsdkGameLogLock);
}
void Platform_LogShutdown(void) { Platform_LogFlush(); }
void Platform_Log(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args,0); va_end(args); }
void Platform_LogWarn(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args,1); va_end(args); }
void Platform_LogError(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args,1); va_end(args); }
