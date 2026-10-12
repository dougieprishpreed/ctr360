/* ctr360: top-level exception filter.
 *
 * Silent wedges on this port have twice been a stopped guest thread with no
 * log line and no Xenia fault report: the guest faulted (or walked into
 * unmapped memory) and nothing visible happened. This filter runs when an
 * exception reaches the top level and logs the exception code, the faulting
 * instruction (Iar), the link register and the faulting address through the
 * durable log path, so the next silent stop names its own PC.
 *
 * C89-clean on purpose: compiled by the XDK compiler directly (outside the
 * build-360 mirror, like native_xbox360_log.c).
 */
#include <xtl.h>
#include <stddef.h>

#include <macros.h>
#include "platform/native_log.h"

global_variable int g_ctr360_faultHandlerInstalled = 0;

static LONG WINAPI Ctr360_TopLevelExceptionFilter(struct _EXCEPTION_POINTERS *info)
{
	struct _EXCEPTION_RECORD *rec = info->ExceptionRecord;
	CONTEXT *ctx = info->ContextRecord;
	DWORD access = 0;
	DWORD faultAddr = 0;

	if (rec->NumberParameters >= 2)
	{
		access = (DWORD)rec->ExceptionInformation[0];
		faultAddr = (DWORD)rec->ExceptionInformation[1];
	}

	Platform_Log("[fault] TOP-LEVEL code=%08x pc=%08x lr=%08x access=%d faultAddr=%08x r3=%08x r4=%08x r5=%08x\n",
	             (unsigned)rec->ExceptionCode,
	             (ctx != NULL) ? (unsigned)ctx->Iar : 0u,
	             (ctx != NULL) ? (unsigned)ctx->Lr : 0u,
	             (int)access,
	             (unsigned)faultAddr,
	             (ctx != NULL) ? (unsigned)ctx->Gpr3 : 0u,
	             (ctx != NULL) ? (unsigned)ctx->Gpr4 : 0u,
	             (ctx != NULL) ? (unsigned)ctx->Gpr5 : 0u);

	Platform_LogFlush();

	/* Let the default behaviour continue (thread termination). */
	return EXCEPTION_EXECUTE_HANDLER;
}

void Platform_InstallFaultHandler(void)
{
	if (g_ctr360_faultHandlerInstalled)
	{
		return;
	}

	SetUnhandledExceptionFilter(Ctr360_TopLevelExceptionFilter);
	g_ctr360_faultHandlerInstalled = 1;

	Platform_Log("[CTR Native] top-level exception filter installed\n");
}
