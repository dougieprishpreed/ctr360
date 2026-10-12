/* ctr360: Xbox 360 logging backend (implements platform/native_log.h).
 *
 * Writes the log beside the executable, searching roots in the order the
 * hello-world probe established (and the user confirmed):
 *   cache:\ - writable under Xenia (where hello360.log landed) and on console
 *   game:\  - the xex folder: READ-ONLY under Xenia, opportunistic on RGH
 *   hdd1:\, usb0:\ - later options (RGH storage)
 * If no root is writable the log degrades to OutputDebugString only.
 *
 * Session 9 (IMPLEMENTATION_PLAN 0.1): lines are classified into trace
 * categories (platform/native_trace.c) and only the enabled categories reach
 * the sinks, and enabled lines are *buffered* instead of flushed per line.
 * The old per-line fflush + OutputDebugStringA cost kept the guest at ~2 fps;
 * with the flood filtered out the frame loop runs at normal speed. Fault,
 * guard, error, phase and capture lines still flush immediately, so a wedge
 * can never swallow the line that explains it.
 *
 * C89-clean on purpose: this file is compiled by the XDK compiler directly
 * (it lives outside the build-360 mirror, so the mirror's transforms do not
 * touch it).
 */
#include <xtl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <macros.h>
#include "platform/native_log.h"

global_variable FILE *s_logStream = NULL;
global_variable char s_logPath[512];

static const char *s_logRoots[4] = { "cache:\\", "game:\\", "hdd1:\\", "usb0:\\" };

/* Buffered sink: 64 KB of pending text, flushed on the policy below. */
#define LOG_BUFFER_SIZE (64 * 1024)
#define LOG_FLUSH_THRESHOLD (48 * 1024)
#define LOG_FLUSH_INTERVAL_MS 1000

static char s_logBuffer[LOG_BUFFER_SIZE];
static int s_logBufferLen = 0;
static unsigned s_logLastFlushMs = 0;

/* The game thread and the audio callback thread both log. The buffer, its
 * length and the stream must move together, so every sink write takes this
 * spinlock (session 9: unsynchronised appends tore lines apart). */
static volatile LONG s_logLock = 0;

static void Platform_LogLock(void)
{
	while (InterlockedCompareExchange(&s_logLock, 1, 0) != 0)
	{
		Sleep(0);
	}
}

static void Platform_LogUnlock(void)
{
	InterlockedExchange(&s_logLock, 0);
}

static void Platform_LogFlushBufferLocked(void)
{
	if ((s_logStream != NULL) && (s_logBufferLen > 0))
	{
		fwrite(s_logBuffer, 1, (size_t)s_logBufferLen, s_logStream);
		/* Drain the CRT buffer too, so an early exit leaves the last
		 * checkpoint in the actual file. This runs only at batch flush. */
		fflush(s_logStream);
		s_logBufferLen = 0;
	}
	s_logLastFlushMs = GetTickCount();
}

/* A line that must reach the durable sink immediately: a fault, a guard trip,
 * a packet-integrity failure, a phase/capture marker or an error. */
static int Platform_LogIsImmediate(const char *text)
{
	if ((strncmp(text, "[fault]", 7) == 0) || (strncmp(text, "[boot]", 6) == 0))
	{
		return 1;
	}
	if ((strstr(text, "guard") != NULL) || (strstr(text, "invalid") != NULL))
	{
		return 1;
	}
	if ((strstr(text, "vram.tga") != NULL) || (strstr(text, "==== ") != NULL))
	{
		return 1;
	}
	if (strncmp(text, "[CTR Native]", 12) == 0)
	{
		return 1;
	}
	if (strncmp(text, "[trace] config", 14) == 0)
	{
		return 1;
	}
	if (strstr(text, "Error") != NULL)
	{
		return 1;
	}
	return 0;
}

internal void Platform_LogWrite(FILE *consoleStream, const char *text)
{
	FILE *stream = (consoleStream != NULL) ? consoleStream : stdout;
	unsigned category = Platform_TraceClassify(text);
	size_t len = strlen(text);
	int immediate;

	if ((category != CTR_TRACE_ESSENTIAL) && (Platform_TraceEnabled(category) == 0))
	{
		return;
	}

	immediate = Platform_LogIsImmediate(text);

	Platform_LogLock();

	if (Platform_TraceOdsEnabled() != 0)
	{
		OutputDebugStringA(text);
	}

	/* Buffer the durable copy; flush on the policy, never per line. */
	if (s_logStream != NULL)
	{
		if (len >= LOG_BUFFER_SIZE)
		{
			Platform_LogFlushBufferLocked();
			fwrite(text, 1, len, s_logStream);
		}
		else
		{
			if ((s_logBufferLen + (int)len) > LOG_FLUSH_THRESHOLD)
			{
				Platform_LogFlushBufferLocked();
			}

			memcpy(s_logBuffer + s_logBufferLen, text, len);
			s_logBufferLen += (int)len;
		}

		if (immediate != 0)
		{
			Platform_LogFlushBufferLocked();
		}
		else if ((GetTickCount() - s_logLastFlushMs) >= LOG_FLUSH_INTERVAL_MS)
		{
			Platform_LogFlushBufferLocked();
		}
	}

	/* The console copy is for the essential lines only: the guest stdout
	 * write is part of what made the trace-heavy builds slow. */
	if (category == CTR_TRACE_ESSENTIAL && immediate)
	{
		/* The guest CRT's stderr stream has never delivered a byte in any run
		 * and its first write wedged the thread; stdout is proven healthy in
		 * every run. Route error text through stdout so the console-stream
		 * copy cannot kill a diagnostic path again. */
		if (stream == stderr)
		{
			stream = stdout;
		}

		fputs(text, stream);
	}

	Platform_LogUnlock();
}

internal void Platform_LogV(FILE *consoleStream, const char *fmt, va_list args)
{
	char text[4096];
	int written = _vsnprintf(text, sizeof(text) - 1, fmt, args);

	if (written < 0)
	{
		text[sizeof(text) - 1] = '\0';
	}
	else
	{
		text[sizeof(text) - 1] = '\0';
	}

	Platform_LogWrite(consoleStream, text);
}

int Platform_LogSetPath(const char *path)
{
	if (s_logStream != NULL)
	{
		return 0;
	}

	if ((path == NULL) || (path[0] == '\0'))
	{
		s_logPath[0] = '\0';
		return 1;
	}

	if (strlen(path) >= sizeof(s_logPath))
	{
		s_logPath[0] = '\0';
		OutputDebugStringA("[ctr360] Error: log path is too long\n");
		return 0;
	}

	strcpy(s_logPath, path);
	return 1;
}

const char *Platform_LogGetPath(void)
{
	return s_logPath;
}

void Platform_LogInit(const char *appName)
{
	int i;

	/* Idempotent: main() initialises the log before asset setup and
	 * Platform_Init calls in again. Re-opening the file we already hold
	 * open fails on the console (the CRT delete-then-create cannot remove
	 * an open file), which used to kill all later file logging - keep the
	 * stream we already have. */
	if (s_logStream != NULL)
	{
		return;
	}

	if (s_logPath[0] == '\0')
	{
		/* search the device roots for the first writable location */
		for (i = 0; i < 4; i++)
		{
			char candidate[512];

			_snprintf(candidate, sizeof(candidate) - 1, "%s%s.log", s_logRoots[i], appName);
			candidate[sizeof(candidate) - 1] = '\0';

			s_logStream = fopen(candidate, "wb");
			if (s_logStream != NULL)
			{
				strcpy(s_logPath, candidate);
				break;
			}
		}
	}
	else
	{
		s_logStream = fopen(s_logPath, "wb");
	}

	if (s_logStream == NULL)
	{
		OutputDebugStringA("[ctr360] Error: cannot create log file on any root\n");
		s_logPath[0] = '\0';
		return;
	}

	/* Runtime verbosity: cache:\ctr360_trace.txt, else the default mask. */
	Platform_TraceLoadConfig();
	Platform_LogWarn("[boot] trace mask=%08x (0=essentials-only)\n", Platform_TraceMask());
}

void Platform_LogShutdown(void)
{
	Platform_LogWarn("---- LOG CLOSED ----\n");

	Platform_LogLock();
	Platform_LogFlushBufferLocked();

	if (s_logStream != NULL)
	{
		fclose(s_logStream);
	}

	s_logStream = NULL;
	Platform_LogUnlock();
}

void Platform_LogFlush(void)
{
	Platform_LogLock();
	Platform_LogFlushBufferLocked();
	Platform_LogUnlock();
}

void Platform_Log(const char *fmt, ...)
{
	va_list args;

	va_start(args, fmt);
	Platform_LogV(stdout, fmt, args);
	va_end(args);
}

void Platform_LogWarn(const char *fmt, ...)
{
	va_list args;

	va_start(args, fmt);
	Platform_LogV(stdout, fmt, args);
	va_end(args);
}

void Platform_LogError(const char *fmt, ...)
{
	va_list args;

	va_start(args, fmt);
	Platform_LogV(stderr, fmt, args);
	va_end(args);
}
