#include <platform/native_log.h>
#include <xsdk/log.h>
#include <stdarg.h>
#include <stdio.h>
static void XsdkLogV(const char *fmt, va_list args)
{
    char text[2048]; vsnprintf(text,sizeof(text),fmt,args);
    unsigned category=Platform_TraceClassify(text);
    if (category && !Platform_TraceEnabled(category)) return;
    xsdk_log_write_bytes(text,strlen(text));
}
int Platform_LogSetPath(const char *p) { (void)p; return 0; }
const char *Platform_LogGetPath(void) { return "game:/default.log"; }
void Platform_LogInit(const char *name) { (void)name; }
void Platform_LogShutdown(void) {}
void Platform_LogFlush(void) {}
void Platform_Log(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args); va_end(args); }
void Platform_LogWarn(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args); va_end(args); }
void Platform_LogError(const char *fmt,...) { va_list args; va_start(args,fmt); XsdkLogV(fmt,args); va_end(args); }
