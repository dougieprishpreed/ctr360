#include <platform/native_log.h>
#include <xsdk/log.h>
#include <xsdk/kernel.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
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
int Platform_LogSetPath(const char *p) { (void)p; return 0; }
const char *Platform_LogGetPath(void) { return "game:/default.log"; }
void Platform_LogInit(const char *name)
{
    (void)name;RtlInitializeCriticalSection(&xsdkGameLogLock);
    xsdkGameLogLength=0;xsdkGameLogLastFlush=GetTickCount();
}
void Platform_LogFlush(void)
{
    RtlEnterCriticalSection(&xsdkGameLogLock);XsdkLogFlushLocked();RtlLeaveCriticalSection(&xsdkGameLogLock);
}
void Platform_LogShutdown(void) { Platform_LogFlush(); }
void Platform_Log(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args,0); va_end(args); }
void Platform_LogWarn(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args,1); va_end(args); }
void Platform_LogError(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args,1); va_end(args); }
