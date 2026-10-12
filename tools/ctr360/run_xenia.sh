#!/usr/bin/env bash
# Drive Xenia Canary with the staged ctr360 build for N seconds, then kill it
# and print the guest log's key lines. Usage: run_xenia.sh [seconds] [pattern]
set -u

SECS="${1:-45}"
PATTERN="${2:-}"

XENIA_DIR="/f/downloads/xenia_canary_windows"
XEX="F:\\downloads\\temp\\python\\hermes\\ctrport\\ctr360\\build-360\\xex\\dist\\default.xex"
LOG="$XENIA_DIR/cache/ctr360.log"

cd "$XENIA_DIR" || exit 1
rm -f "$LOG"
export CTR360_XENIA_EXE="$(cygpath -w "$XENIA_DIR/xenia_canary.exe")"
export CTR360_XEX_PATH="$XEX"
WINDOW_STYLE="Minimized"
if [ "${CTR360_VISIBLE:-0}" = "1" ]; then
    WINDOW_STYLE="Normal"
fi
export CTR360_WINDOW_STYLE="$WINDOW_STYLE"
# Optional per-run CPU readback for guest framebuffer diagnostics. Passing it
# on the command line keeps the user's persistent Xenia configuration intact.
export CTR360_READBACK="${CTR360_READBACK:-}"
case "$CTR360_READBACK" in
    ""|none|fast|full) ;;
    *) echo 'CTR360_READBACK must be none, fast, or full' >&2; exit 2 ;;
esac
# Match the writable USB/HDD launch folder used on real hardware. Keep this
# per launch so the user's global emulator configuration is unchanged.
XPID=$(powershell -NoProfile -Command '$launchArgs=@($env:CTR360_XEX_PATH,"--allow_game_relative_writes=true"); if($env:CTR360_READBACK){$launchArgs += "--readback_resolve=$env:CTR360_READBACK"}; $p=Start-Process -FilePath $env:CTR360_XENIA_EXE -ArgumentList $launchArgs -WorkingDirectory (Split-Path $env:CTR360_XENIA_EXE) -WindowStyle $env:CTR360_WINDOW_STYLE -PassThru; Write-Output $p.Id')
if [ -z "$XPID" ]; then
    echo "failed to start Xenia Canary" >&2
    exit 2
fi
sleep "$SECS"

# CPU sample while still running (blocked vs spinning)
powershell -NoProfile -Command '$p=Get-Process xenia_canary -ErrorAction SilentlyContinue; if($p){$c1=$p.TotalProcessorTime.TotalSeconds; Start-Sleep -Seconds 3; $c2=(Get-Process xenia_canary).TotalProcessorTime.TotalSeconds; Write-Output ("CPU over 3s wall: " + [math]::Round($c2-$c1,2) + "s")}'

echo "==== frames:"
grep -c 'frame .* presented' "$LOG" 2>/dev/null || echo "no log"
grep 'frame .* presented' "$LOG" 2>/dev/null | tail -4
echo "==== last 20 guest lines (non-pump):"
grep -v 'pump callbacks' "$LOG" 2>/dev/null | tail -20
if [ -n "$PATTERN" ]; then
	echo "==== matches for '$PATTERN':"
	grep -n "$PATTERN" "$LOG" 2>/dev/null | tail -25
fi
echo "==== log size: $(wc -l < "$LOG" 2>/dev/null) lines, last pump:"
grep 'pump callbacks' "$LOG" 2>/dev/null | tail -1

powershell -NoProfile -Command "Stop-Process -Name xenia_canary -Force -ErrorAction SilentlyContinue" >/dev/null 2>&1
exit 0
