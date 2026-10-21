#!/usr/bin/env bash
# Build the game using only the open xSDK toolchain (run on Linux or in WSL).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
: "${XSDK:?Set XSDK to the pinned xenosworks/xsdk checkout}"
: "${VULKAN4XENON:?Set VULKAN4XENON to its pinned checkout}"
: "${XSDK_TOOLCHAIN:?Set XSDK_TOOLCHAIN to the compiler installation prefix}"
: "${XSDK_GLSLANG:?Set XSDK_GLSLANG to a host glslang-xenon executable}"
OUT="${CTR_XSDK_BUILD:-$ROOT/build-xsdk/output}"
JOBS="${JOBS:-1}"
mkdir -p "$OUT"
python3 "$ROOT/tools/ctr360/audit_endian_source.py" --report "$OUT/endian-source.json"
python3 "$ROOT/tools/xsdk/verify_deps.py" "$XSDK" "$VULKAN4XENON"
python3 "$ROOT/tools/xsdk/prepare_sources.py" --root "$ROOT" --out "$ROOT/build-xsdk/gen"
make -C "$XSDK" -j"$JOBS" TOOLCHAIN="$XSDK_TOOLCHAIN/bin/powerpc-xsdk-elf-" build/libxsdk.a build/host/libxsc.so
make -C "$VULKAN4XENON" -j"$JOBS" XSDK="$XSDK" TOOLCHAIN="$XSDK_TOOLCHAIN/bin/powerpc-xsdk-elf-" build/libvulkan4xenon.a
cd "$OUT"
export XSDK_GLSLANG
python3 "$VULKAN4XENON/tools/build_shaders.py" --xost "$XSDK/xenos-toolchain" \
  --glslang "$ROOT/tools/xsdk/glslang.sh" --optimize --output ctr_shaders "$ROOT"/platform/xsdk/shaders/*
CC="$XSDK_TOOLCHAIN/bin/powerpc-xsdk-elf-gcc"
GEN="$ROOT/build-xsdk/gen"
FLAGS=(-mcpu=cell -fno-pic -std=gnu17 -O2 -g -fno-strict-aliasing -fwrapv -mcheck-fpr-alignment -ffunction-sections -fdata-sections
  -DCTR_NATIVE -D_XBOX -DCTR_XSDK -I. -I"$XSDK/include" -I"$XSDK/src" -I"$VULKAN4XENON/include"
  -I"$VULKAN4XENON/third_party/vulkan-headers/include" -I"$GEN/platform/xsdk/compat"
  -I"$GEN/platform/xbox360/sdl_shim" -I"$GEN/include" -I"$GEN")
"$CC" "${FLAGS[@]}" -c "$GEN/platform/xsdk/main_xsdk.c" -o ctr360.o
"$CC" "${FLAGS[@]}" -c ctr_shaders.c -o ctr_shaders.o
"$CC" -mcpu=cell -fno-pic -static -nostdlib -T "$XSDK/src/xsdk.ld" \
  -Wl,--gc-sections,-Map,ctr360.map -o ctr360.elf ctr360.o ctr_shaders.o \
  -Wl,--start-group "$VULKAN4XENON/build/libvulkan4xenon.a" -lstdc++ "$XSDK/build/libxsdk.a" -lc -lm -lgcc -Wl,--end-group
python3 "$ROOT/tools/xsdk/source_snapshot.py" --root "$ROOT" --prepared "$GEN"
python3 "$XSDK/tools/elf2xex.py" ctr360.elf default.xex
"$XSDK_TOOLCHAIN/bin/powerpc-xsdk-elf-readelf" -h ctr360.elf
python3 "$ROOT/tools/xsdk/verify_binary.py" --elf ctr360.elf --xex default.xex --toolchain "$XSDK_TOOLCHAIN"
mkdir -p licenses
cp "$XSDK/LICENSE" licenses/xsdk.txt
cp "$VULKAN4XENON/LICENSE" licenses/vulkan4xenon.txt
cp "$XSDK_TOOLCHAIN/share/ctr360-licenses/"* licenses/
printf 'Built experimental xSDK title: %s/default.xex\n' "$OUT"
