#!/usr/bin/env bash
# ctr360: compile the mirrored corpus with the Xbox 360 SDK cl.exe (language probe).
# Usage: xdk_smoke.sh [mirror-dir]     (default: <repo>/build-360/gen)
# Log:   build-360/smoke_log.txt
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MIRROR="${1:-$ROOT/build-360/gen}"
XEDK="/c/Program Files (x86)/Microsoft Xbox 360 SDK"

if [ ! -x "$XEDK/bin/win32/cl.exe" ]; then
    echo "XDK cl.exe not found at $XEDK" >&2
    exit 2
fi
if [ ! -d "$MIRROR" ]; then
    echo "mirror not found: $MIRROR" >&2
    exit 2
fi

export INCLUDE='C:\Program Files (x86)\Microsoft Xbox 360 SDK\include\win32;C:\Program Files (x86)\Microsoft Xbox 360 SDK\include\xbox;C:\Program Files (x86)\Microsoft Xbox 360 SDK\include\xbox\sys'
export LIB='C:\Program Files (x86)\Microsoft Xbox 360 SDK\lib\win32;C:\Program Files (x86)\Microsoft Xbox 360 SDK\lib\xbox'

# native tools need native-style paths
WINROOT="$(cygpath -m "$ROOT" 2>/dev/null || echo "$ROOT")"
LOG="$ROOT/build-360/smoke_log.txt"

cd "$MIRROR" || exit 3
"$XEDK/bin/win32/cl.exe" -nologo -c -TC -DCTR_NATIVE -I. -Iinclude \
    "$WINROOT/tools/ctr360/xdk_smoke_360.c" > "$LOG" 2>&1
rc=$?

echo "cl exit: $rc   (log: $LOG)"
echo "errors:  $(grep -c ': error' "$LOG" 2>/dev/null || echo 0)"
echo "warnings:$(grep -c ': warning' "$LOG" 2>/dev/null || echo 0)"
grep ': error' "$LOG" 2>/dev/null | sed 's/^/  /' | head -30
exit $rc
