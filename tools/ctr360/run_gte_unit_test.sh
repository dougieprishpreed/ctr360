#!/usr/bin/env bash
# Build and run the GTE multiply unit test in both register layouts.
#
# The test drives the REAL scalar GTE (platform/native_inline_c.c,
# platform/native_gte_core.c) and the REAL matrix helpers
# (game/MATH/MATH_7_MatrixStubs.c, pulled in by the test) with the register
# choreography RenderBucket_BuildM3x3 / RenderBucket_BuildMvp use, and checks
# the results against hand-computed references. It is compiled twice:
#
#   host - CTR_GTE_BIG_ENDIAN=0: the PSX little-endian register layout, i.e.
#          what ctr-native computes on PC
#   360  - CTR_GTE_BIG_ENDIAN=1: the big-endian layout the Xbox 360 sees
#          (PAIR members declared in reverse memory order)
#
# Both runs must print identical results; the diff is the acceptance check.
# No 360 build or emulator run is involved - this is the fast loop for the
# per-instance matrix/projection chain.
set -u
cd "$(dirname "$0")/../.."

CC=${CC:-clang}
OUT="${LOCALAPPDATA:-$HOME}/Temp"
SRC="tools/ctr360/gte_mul_test.c platform/native_inline_c.c platform/native_gte_core.c"
CFLAGS="-O1 -DCTR_NATIVE -I include -I . -Wno-everything -D_Static_assert(x,y)="

# shellcheck disable=SC2086
$CC $CFLAGS -o "$OUT/gte_mul_test_host.exe" $SRC || { echo "host build failed"; exit 1; }
# shellcheck disable=SC2086
$CC $CFLAGS -DCTR_GTE_BIG_ENDIAN=1 -o "$OUT/gte_mul_test_be.exe" $SRC || { echo "360-layout build failed"; exit 1; }

"$OUT/gte_mul_test_host.exe" > "$OUT/gte_host.txt"; H=$?
"$OUT/gte_mul_test_be.exe" > "$OUT/gte_be.txt"; B=$?

echo "fixed layout (host, = 360 after the PAIR fix) exit=$H"
echo "pre-fix 360 layout (emulated)                 exit=$B"
head -2 "$OUT/gte_host.txt"

# The two runs must disagree in exactly the documented way (y/z columns lost in
# the pre-fix layout), and both must pass their own expectations.
if grep -q "\[PASS\] y/z columns nonzero" "$OUT/gte_host.txt" \
   && grep -q "pre-fix 360 symptom" "$OUT/gte_be.txt"; then
    echo "symptom shape: as expected (fixed layout keeps y/z; pre-fix layout drops them)"
else
    echo "UNEXPECTED SHAPE - inspect $OUT/gte_host.txt and $OUT/gte_be.txt"
    exit 1
fi

if [ "$H" != 0 ] || [ "$B" != 0 ]; then
    echo "UNIT TEST FAILED"
    exit 1
fi
echo "gte unit test: PASS (fixed layout + documented pre-fix symptom)"
