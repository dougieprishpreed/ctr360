#!/usr/bin/env bash
# Stage a console/Xenia layout using the user's own converted disc image.
# Usage: prep_test.sh [--cooked <image> | --raw]
# With no arguments, use build-360/ctr-u-360.bin.
# --raw is retained only for platform diagnostics, not normal play.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT_ROOT="$(cd "$ROOT/.." && pwd)"
DIST="$ROOT/build-360/xex/dist"
MODE="cooked"
IMAGE="$ROOT/build-360/ctr-u-360.bin"
case "${1:-}" in
    "") ;;
    --cooked)
        [ "$#" -eq 2 ] || { echo 'Usage: prep_test.sh --cooked <image>' >&2; exit 2; }
        IMAGE="$2"
        ;;
    --raw)
        [ "$#" -eq 1 ] || exit 2
        MODE="raw"
        IMAGE="$PORT_ROOT/CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin"
        ;;
    *) echo 'Usage: prep_test.sh [--cooked <image> | --raw]' >&2; exit 2 ;;
esac

if [ ! -f "$DIST/default.xex" ]; then
    echo "default.xex missing - run tools/ctr360/build_xex.sh first" >&2
    exit 2
fi
if [ ! -f "$IMAGE" ]; then
    echo "disc image not found: $IMAGE" >&2
    exit 2
fi
if [ "$(realpath "$IMAGE")" = "$(realpath -m "$DIST/assets/ctr-u.bin")" ]; then
    echo 'source image must be outside the staging destination' >&2
    exit 2
fi

mkdir -p "$DIST/assets"
rm -f "$DIST/assets/ctr-u.bin"
# Hardlink on the same volume to avoid duplicating a 600MB image; copy otherwise.
export CTR360_STAGE_SOURCE="$(cygpath -w "$IMAGE")"
export CTR360_STAGE_DEST="$(cygpath -w "$DIST/assets/ctr-u.bin")"
if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -Command 'New-Item -ItemType HardLink -Path $env:CTR360_STAGE_DEST -Target $env:CTR360_STAGE_SOURCE | Out-Null' >/dev/null 2>&1 || true
fi
if [ -f "$DIST/assets/ctr-u.bin" ]; then
    echo "linked:  $IMAGE"
else
    cp "$IMAGE" "$DIST/assets/ctr-u.bin"
    echo "copied:  $IMAGE"
fi

cat > "$DIST/assets/ctr360_graphics.example.txt" <<'EOF'
interpolation 1
texture_filter 1
edge_aa 1
EOF

cat > "$DIST/README.txt" <<'EOF'
CTR360 - Crash Team Racing (Xbox 360 native), development build
=============================================================

Copy this whole folder to writable USB/HDD storage and launch default.xex
from a homebrew-capable console dashboard. The assets/ctr-u.bin file must be
the converted NTSC-U image made from your own disc dump with cook_disc.py.

Layout:
  default.xex        executable
  assets/ctr-u.bin   converted disc image
  memcards/         persistent saves, created by the game's save menus

Keep and back up memcards/ when updating. These are CTR360 virtual card files,
not raw PSX card images. No Xbox profile or storage-selection dialog is needed.

The controller follows the original layout: A/Cross, B/Circle, X/Square,
Y/Triangle, LB/L1, RB/R1, LT/L2, RT/R2. Start pauses. Back + Start exits.

Graphics defaults: 1280x720, expanded 16:9 world view, filtered textures,
and edge smoothing. Single-player races target 60 FPS render / 30 Hz
simulation. Adventure hubs, menus and other modes keep their normal cadence.
This is a development build; performance and stability issues can remain.

To change graphics, copy assets/ctr360_graphics.example.txt to
assets/ctr360_graphics.txt. Keys interpolation, texture_filter and edge_aa
accept 0 (off) or 1 (on). Restart after changes. Set interpolation 0 for the
30 FPS rendering fallback while keeping 720p and widescreen.

If reporting a fault, describe the mode/course and reproduction steps and
include ctr360.log. The first writable root is used: cache:\, game:\,
hdd1:\, usb0:\. Routine diagnostics are batched to reduce storage overhead.

For optional Xenia Canary testing, use --allow_game_relative_writes=true
so the game can write saves beside the executable.

Source and build instructions: https://github.com/dougieprishpreed/ctr360
EOF
if [ "$MODE" = "raw" ]; then
    printf '\nDIAGNOSTIC LAYOUT: raw disc image; not suitable for normal play.\n' >> "$DIST/README.txt"
fi

echo "staged:  $DIST"
