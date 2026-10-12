/* ctr360: XDK compatibility shims.
 *
 * Include this immediately after <xtl.h> and before any project header. The
 * XDK headers define a number of macros whose names the PSX/game sources use
 * as ordinary identifiers; undefining them here keeps the mirrored sources
 * byte-identical to upstream. Found by intersecting every #define in
 * include/xbox with the identifiers the mirror actually uses
 * (tools/ctr360/find_macro_collisions.py).
 *
 * C89-clean: the XDK compiler builds this directly.
 */

#ifndef CTR360_COMPAT_H
#define CTR360_COMPAT_H

/* windef.h: legacy segment qualifiers defined as empty macros. The game uses
 * `far`/`near` as struct member and variable names. */
#ifdef far
#undef far
#endif
#ifdef near
#undef near
#endif

/* winsock2.h: `#define s_addr S_un.S_addr` collides with struct EXEC's field. */
#ifdef s_addr
#undef s_addr
#endif

/* winbase.h: `#define OpenEvent OpenEventA` collides with the PSX event API. */
#ifdef OpenEvent
#undef OpenEvent
#endif

/* winbase.h defines INVALID_FILE_ATTRIBUTES; the XDK headers do not. */
#ifndef INVALID_FILE_ATTRIBUTES
#define INVALID_FILE_ATTRIBUTES ((DWORD)0xFFFFFFFF)
#endif

/* The mirror's log macros use C99's __func__; the XDK compiler in C mode
 * provides __FUNCTION__ instead (same string, function name). */
#define __func__ __FUNCTION__

/* The XDK CRT exports the underscore-prefixed C89 names; the mirrored sources
 * use the C99 spellings. Signatures match (buffer, size, format, ...). */
#define snprintf  _snprintf
#define vsnprintf _vsnprintf

/* winbase.h maps the critical-section helpers onto Rtl* functions. The game's
 * PSX-style sections are no-ops in the host build too (main.c defines them
 * away before including the same sources), so mirror that here. The console
 * backends that need real locking (audio output) call the Rtl* functions
 * directly instead. */
#ifdef EnterCriticalSection
#undef EnterCriticalSection
#endif
#ifdef ExitCriticalSection
#undef ExitCriticalSection
#endif
#define EnterCriticalSection()
#define ExitCriticalSection()

#endif
