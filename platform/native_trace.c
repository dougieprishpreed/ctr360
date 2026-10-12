/* ctr360: trace categories and the runtime category mask (IMPLEMENTATION_PLAN
 * Phase 0.1).
 *
 * Every diagnostic line is classified by its leading marker and tag at the log
 * sink, so how verbose a run is becomes a *runtime* property: the mask is read
 * from cache:\ctr360_trace.txt at log init (and re-read on request) instead of
 * being compiled in. The default mask carries the essentials only: build
 * identity, phase changes, frame heartbeat, [fault] and *-guard lines, packet
 * integrity failures and capture results.
 *
 * Lines that do not start with a [trace]/[probe] marker (fault reports, boot
 * banners, audio pump heartbeats, GPU/asset errors) are always emitted.
 *
 * C89-clean on purpose: this file is compiled by the XDK compiler directly
 * through the unity translation unit.
 */
#include <macros.h>

#include "platform/native_log.h"
#include "platform/native_perf.h"

#include <stdio.h>
#include <string.h>

#ifdef _XBOX
#include <xtl.h>
#endif

/* Tag -> category table. Tags are the token right after the [trace]/[probe]
 * marker (see HANDOFF section 5 for the probe inventory). A tag missing here
 * falls back to CTR_TRACE_MISC, so a new probe is off by default and becomes
 * visible the moment its tag is added. */
typedef struct
{
	const char *tag;
	unsigned category;
} Ctr360TraceTag;

static const Ctr360TraceTag s_traceTags[] = {
	/* frame loop / phases (MainFrame) */
	{ "hbm", CTR_TRACE_BOOT },
	{ "hb", CTR_TRACE_BOOT },
	{ "mbank", CTR_TRACE_BOOT },
	{ "l1m", CTR_TRACE_BOOT },
	{ "l2m", CTR_TRACE_BOOT },
	{ "l3m", CTR_TRACE_BOOT },
	{ "g1m", CTR_TRACE_BOOT },
	{ "g2m", CTR_TRACE_BOOT },
	{ "g3m", CTR_TRACE_BOOT },
	{ "g4m", CTR_TRACE_BOOT },
	{ "g5m", CTR_TRACE_BOOT },
	{ "g6m", CTR_TRACE_BOOT },
	{ "g7m", CTR_TRACE_BOOT },
	{ "pa", CTR_TRACE_BOOT },
	{ "pd", CTR_TRACE_BOOT },
	{ "pe", CTR_TRACE_BOOT },
	{ "pf", CTR_TRACE_BOOT },
	{ "pg", CTR_TRACE_BOOT },
	{ "frame", CTR_TRACE_BOOT },
	{ "stage", CTR_TRACE_BOOT },
	{ "stage5", CTR_TRACE_BOOT },
	{ "stage9", CTR_TRACE_BOOT },
	{ "howl", CTR_TRACE_BOOT },
	{ "song", CTR_TRACE_BOOT },
	{ "memcard", CTR_TRACE_BOOT },
	{ "save", CTR_TRACE_BOOT },
	{ "mempack", CTR_TRACE_BOOT },
	{ "finalize", CTR_TRACE_BOOT },

	/* title/menu state (sparse) */
	{ "title-init", CTR_TRACE_TITLE },
	{ "title-menu", CTR_TRACE_TITLE },
	{ "title-dpp", CTR_TRACE_TITLE },
	{ "jump-to-title-first-time", CTR_TRACE_TITLE },
	{ "tcp", CTR_TRACE_TITLE },
	{ "rf13-open", CTR_TRACE_TITLE },

	/* framebuffer capture / upload */
	{ "vram", CTR_TRACE_VRAM },
	{ "vramcap", CTR_TRACE_VRAM },
	{ "readback", CTR_TRACE_VRAM },
	{ "UpdateVRAM:", CTR_TRACE_VRAM },
	{ "cap", CTR_TRACE_VRAM },

	/* GPU packet walker */
	{ "walk", CTR_TRACE_PACKET },
	{ "pack", CTR_TRACE_PACKET },
	{ "pvr", CTR_TRACE_PACKET },
	{ "vb", CTR_TRACE_PACKET },
	{ "dfq", CTR_TRACE_PACKET },
	{ "DrawOTag#", CTR_TRACE_PACKET },
	{ "BeginScene", CTR_TRACE_PACKET },
	{ "EndScene:", CTR_TRACE_PACKET },
	{ "EnsureRT", CTR_TRACE_PACKET },
	{ "DrawAllSplits:", CTR_TRACE_PACKET },
	{ "->", CTR_TRACE_PACKET },
	{ "pw", CTR_TRACE_PACKET },
	{ "pp", CTR_TRACE_PACKET },
	{ "cb1", CTR_TRACE_PACKET },
	{ "cb2", CTR_TRACE_PACKET },
	{ "cnr", CTR_TRACE_PACKET },
	{ "dsp", CTR_TRACE_PACKET },
	{ "case1", CTR_TRACE_PACKET },
	{ "nonghost", CTR_TRACE_PACKET },
	{ "split", CTR_TRACE_PACKET },
	{ "d1", CTR_TRACE_PACKET },
	{ "dw", CTR_TRACE_PACKET },
	{ "d2", CTR_TRACE_PACKET },
	{ "d3", CTR_TRACE_PACKET },
	{ "d4", CTR_TRACE_PACKET },
	{ "pc", CTR_TRACE_PACKET },
	{ "cdm", CTR_TRACE_PACKET },
	{ "qm", CTR_TRACE_PACKET },
	{ "q5", CTR_TRACE_PACKET },
	{ "q6", CTR_TRACE_PACKET },
	{ "q7", CTR_TRACE_PACKET },
	{ "q8", CTR_TRACE_PACKET },
	{ "q9", CTR_TRACE_PACKET },
	{ "vsw", CTR_TRACE_PACKET },
	{ "vehbirth", CTR_TRACE_PACKET },
	{ "vw2", CTR_TRACE_PACKET },
	{ "vpw", CTR_TRACE_PACKET },

	/* render-bucket queue + cull */
	{ "rbe", CTR_TRACE_CULL },
	{ "qall", CTR_TRACE_CULL },
	{ "qb", CTR_TRACE_CULL },
	{ "qd1", CTR_TRACE_CULL },
	{ "qd2", CTR_TRACE_CULL },
	{ "qd3", CTR_TRACE_CULL },
	{ "qd4", CTR_TRACE_CULL },
	{ "qd5", CTR_TRACE_CULL },
	{ "qd6", CTR_TRACE_CULL },
	{ "eb", CTR_TRACE_CULL },
	{ "qi", CTR_TRACE_CULL },
	{ "qc", CTR_TRACE_CULL },
	{ "qw", CTR_TRACE_CULL },
	{ "lp", CTR_TRACE_CULL },
	{ "pj", CTR_TRACE_CULL },
	{ "pk", CTR_TRACE_CULL },
	{ "bdx", CTR_TRACE_CULL },
	{ "bdy", CTR_TRACE_CULL },
	{ "bdz", CTR_TRACE_CULL },
	{ "bdx2", CTR_TRACE_CULL },
	{ "bdy2", CTR_TRACE_CULL },
	{ "otnull", CTR_TRACE_CULL },
	{ "otrange", CTR_TRACE_CULL },
	{ "otfull", CTR_TRACE_CULL },
	{ "xq", CTR_TRACE_CULL },
	{ "xs", CTR_TRACE_CULL },
	{ "xs-pick", CTR_TRACE_CULL },
	{ "xz", CTR_TRACE_CULL },
	{ "xt", CTR_TRACE_CULL },

	/* field watches */
	{ "w1", CTR_TRACE_WATCH },
	{ "w2", CTR_TRACE_WATCH },
	{ "w3", CTR_TRACE_WATCH },
	{ "w4", CTR_TRACE_WATCH },
	{ "wch", CTR_TRACE_WATCH },
	{ "csb", CTR_TRACE_WATCH },
	{ "spr", CTR_TRACE_WATCH },
	{ "spw", CTR_TRACE_WATCH },
	{ "mhs", CTR_TRACE_WATCH },
	{ "b3s", CTR_TRACE_WATCH },
	{ "sm", CTR_TRACE_WATCH },
	{ "rl", CTR_TRACE_WATCH },
	{ "mf", CTR_TRACE_WATCH },
	{ "cc", CTR_TRACE_WATCH },
	{ "ota", CTR_TRACE_WATCH },
	{ "otd", CTR_TRACE_WATCH },
	{ "am", CTR_TRACE_WATCH },
	{ "hd", CTR_TRACE_WATCH },
	{ "cm", CTR_TRACE_WATCH },
	{ "s1", CTR_TRACE_WATCH },
	{ "s2", CTR_TRACE_WATCH },
	{ "t1", CTR_TRACE_WATCH },
	{ "tt", CTR_TRACE_WATCH },
	{ "tim", CTR_TRACE_WATCH },
	{ "vl", CTR_TRACE_WATCH },
	{ "lg", CTR_TRACE_WATCH },

	/* level geometry / OT / splits */
	{ "ovr", CTR_TRACE_GEOM },
	{ "lg-in", CTR_TRACE_GEOM },
	{ "lg-out", CTR_TRACE_GEOM },
	{ "rf-in", CTR_TRACE_GEOM },
	{ "render-enter", CTR_TRACE_GEOM },
	{ "render-exit", CTR_TRACE_GEOM },
	{ "rf7", CTR_TRACE_GEOM },
	{ "rf8", CTR_TRACE_GEOM },
	{ "rf9", CTR_TRACE_GEOM },
	{ "rf14", CTR_TRACE_GEOM },
	{ "rf15", CTR_TRACE_GEOM },
	{ "ndbox", CTR_TRACE_GEOM },
	{ "setconsts", CTR_TRACE_GEOM },
	{ "gpu", CTR_TRACE_GEOM },
	{ NULL, 0 }
};

static unsigned s_traceMask = CTR_TRACE_DEFAULT;

unsigned Platform_TraceMask(void)
{
	return s_traceMask;
}

void Platform_TraceSetMask(unsigned mask)
{
	s_traceMask = mask;
}

int Platform_TraceEnabled(unsigned mask)
{
	return (s_traceMask & mask) != 0;
}

/* Does the text start with the given tag? Tags are matched as a whole word:
 * the tag must be followed by a space, '=', ':', '#' or end of string, so "d1"
 * does not swallow "d10" and "walk" still matches "walk#17". */
static int Ctr360TraceTagMatch(const char *text, const char *tag)
{
	size_t i = 0;
	char next;

	while (tag[i] != '\0')
	{
		if (text[i] != tag[i])
		{
			return 0;
		}
		i++;
	}

	next = text[i];
	return ((next == '\0') || (next == ' ') || (next == '=') || (next == ':') || (next == '#'));
}

unsigned Platform_TraceClassify(const char *text)
{
	int i;

	if ((text[0] != '[') || (text[1] == '\0'))
	{
		return CTR_TRACE_ESSENTIAL;
	}

	if ((strncmp(text, "[trace] ", 8) != 0) && (strncmp(text, "[probe] ", 8) != 0))
	{
		/* [fault], [boot], [CTR Audio], [CTR Native], GPU errors, guards: always on. */
		return CTR_TRACE_ESSENTIAL;
	}

	/* The trace-config confirmation must survive its own filter. */
	if (strncmp(text, "[trace] config", 14) == 0)
	{
		return CTR_TRACE_ESSENTIAL;
	}

	/* Quiet performance runs still need sparse frame progress and integrity
	 * failures. Legacy guard probes otherwise fall through to MISC. */
	if (strncmp(text + 8, "hb f=", 5) == 0 || Ctr360TraceTagMatch(text + 8, "hbm") ||
	    strstr(text + 8, "-guard") != NULL || strstr(text + 8, "invalid") != NULL ||
	    strstr(text + 8, "overshoot") != NULL || strstr(text + 8, "OT walk") != NULL)
	{
		return CTR_TRACE_ESSENTIAL;
	}
	/* Nested heartbeats are detailed old frame/instance probes, sometimes
	 * thousands of lines per second. Only the sparse top-level hb is always
	 * on; integrity failures above remain unconditional. */
	if (Ctr360TraceTagMatch(text + 8, "hb"))
	{
		return CTR_TRACE_WATCH;
	}

	for (i = 0; s_traceTags[i].tag != NULL; i++)
	{
		if (Ctr360TraceTagMatch(text + 8, s_traceTags[i].tag) != 0)
		{
			return s_traceTags[i].category;
		}
	}

	return CTR_TRACE_MISC;
}

/* Optional OutputDebugStringA mirror; off unless the config asks for it. */
static int s_traceOds = 0;

int Platform_TraceOdsEnabled(void)
{
	return s_traceOds;
}

static const struct
{
	const char *name;
	unsigned category;
} s_traceNames[] = {
	{ "boot", CTR_TRACE_BOOT },
	{ "packet", CTR_TRACE_PACKET },
	{ "cull", CTR_TRACE_CULL },
	{ "title", CTR_TRACE_TITLE },
	{ "vram", CTR_TRACE_VRAM },
	{ "geom", CTR_TRACE_GEOM },
	{ "misc", CTR_TRACE_MISC },
	{ "watch", CTR_TRACE_WATCH },
	{ NULL, 0 }
};

/* Parse "boot,cull packet" style text. Returns 1 when at least one category
 * was recognised (and clears the mask first, so the file is authoritative). */
static int Ctr360TraceParseConfig(const char *text, unsigned *maskOut, int *odsOut, int *perfOut)
{
	unsigned mask = 0;
	int found = 0;
	int i = 0;

	while (text[i] != '\0')
	{
		char word[32];
		int n = 0;
		int k;

		while ((text[i] == ' ') || (text[i] == ',') || (text[i] == '\t') || (text[i] == '\r') || (text[i] == '\n'))
		{
			i++;
		}

		while ((text[i] != '\0') && (text[i] != ',') && (text[i] != ' ') && (text[i] != '\t') && (text[i] != '\r') && (text[i] != '\n'))
		{
			if (n < (int)(sizeof(word) - 1))
			{
				word[n++] = text[i];
			}
			i++;
		}
		word[n] = '\0';

		if (n == 0)
		{
			continue;
		}

		if (strcmp(word, "all") == 0)
		{
			mask = CTR_TRACE_ALL;
			found = 1;
			continue;
		}
		if ((strcmp(word, "none") == 0) || (strcmp(word, "quiet") == 0))
		{
			mask = CTR_TRACE_ESSENTIAL;
			found = 1;
			continue;
		}
		if ((strcmp(word, "ods") == 0) || (strcmp(word, "debug") == 0))
		{
			*odsOut = 1;
			found = 1;
			continue;
		}
		if ((strcmp(word, "perf") == 0) || (strcmp(word, "timing") == 0))
		{
			*perfOut = 1;
			found = 1;
			continue;
		}

		for (k = 0; s_traceNames[k].name != NULL; k++)
		{
			if (strcmp(word, s_traceNames[k].name) == 0)
			{
				mask |= s_traceNames[k].category;
				found = 1;
				break;
			}
		}
	}

	*maskOut = mask;
	return found;
}

/* Read cache:\ctr360_trace.txt (falling back to the other device roots) and
 * apply it. A missing file keeps the default mask. */
#ifdef _XBOX
void Platform_TraceLoadConfig(void)
{
	static const char *roots[4] = { "cache:\\", "game:\\", "hdd1:\\", "usb0:\\" };
	int i;

	for (i = 0; i < 4; i++)
	{
		char path[512];
		FILE *f;
		char text[1024];
		size_t got;
		int perf = 0;

		_snprintf(path, sizeof(path) - 1, "%sctr360_trace.txt", roots[i]);
		path[sizeof(path) - 1] = '\0';

		f = fopen(path, "rb");
		if (f == NULL)
		{
			continue;
		}

		got = fread(text, 1, sizeof(text) - 1, f);
		fclose(f);
		text[got] = '\0';

		if (Ctr360TraceParseConfig(text, &s_traceMask, &s_traceOds, &perf) != 0)
		{
			Platform_LogWarn("[trace] config %s -> mask=%08x ods=%d perf=%d\n", path, s_traceMask, s_traceOds, perf);
		}

		/* "perf" turns on the existing NativePerf frame capture (the same
		 * switch the host build takes from --perf); it writes per-frame and
		 * per-bucket timing to cache:\perf so a slow frame can be attributed
		 * without a rebuild. */
		if (perf != 0)
		{
			static char *perfArgv[3];
			perfArgv[0] = (char *)"ctr360";
			perfArgv[1] = (char *)"--perf-dir";
			perfArgv[2] = (char *)"cache:\\perf";
			if (NativePerf_ConfigureFromArgs(3, perfArgv) != 0)
			{
				Platform_LogWarn("[trace] perf capture failed to start\n");
			}
		}
		return;
	}
}
#else
/* Host builds have no device roots: keep the default mask. */
void Platform_TraceLoadConfig(void)
{
}
#endif
