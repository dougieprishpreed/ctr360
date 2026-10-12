#ifndef NATIVE_LOG_H
#define NATIVE_LOG_H

#include <macros.h>

int Platform_LogSetPath(const char *path);
const char *Platform_LogGetPath(void);
void Platform_LogInit(const char *appName);
void Platform_LogShutdown(void);
void Platform_LogFlush(void);
void Platform_Log(const char *fmt, ...) CTR_PRINTF_FORMAT(1, 2);
void Platform_LogWarn(const char *fmt, ...) CTR_PRINTF_FORMAT(1, 2);
void Platform_LogError(const char *fmt, ...) CTR_PRINTF_FORMAT(1, 2);

/* ctr360 trace categories (IMPLEMENTATION_PLAN Phase 0.1).
 *
 * Diagnostic lines are classified by their leading [trace]/[probe] tag at the
 * log sink, so verbosity is a runtime property: the mask comes from
 * cache:\ctr360_trace.txt (names: boot, packet, cull, title, vram, geom, misc,
 * watch, all, none, ods) and defaults to the essentials - build identity,
 * phase changes, frame heartbeat, [fault] and *-guard lines, packet-integrity
 * failures and capture results. Lines without a [trace]/[probe] marker are
 * always emitted. See platform/native_trace.c for the tag table. */
#define CTR_TRACE_ESSENTIAL 0x0000u /* always emitted (no marker) */
#define CTR_TRACE_BOOT      0x0001u
#define CTR_TRACE_PACKET    0x0002u
#define CTR_TRACE_CULL      0x0004u
#define CTR_TRACE_TITLE     0x0008u
#define CTR_TRACE_VRAM      0x0010u
#define CTR_TRACE_GEOM      0x0020u
#define CTR_TRACE_MISC      0x0040u
#define CTR_TRACE_WATCH     0x0080u
#define CTR_TRACE_DEFAULT   (CTR_TRACE_BOOT | CTR_TRACE_TITLE)
#define CTR_TRACE_ALL       0xffffffffu

unsigned Platform_TraceMask(void);
void Platform_TraceSetMask(unsigned mask);
int Platform_TraceEnabled(unsigned mask);
void Platform_TraceLoadConfig(void);
int Platform_TraceOdsEnabled(void);
unsigned Platform_TraceClassify(const char *text);

#endif
