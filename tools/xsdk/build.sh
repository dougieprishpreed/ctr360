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
python3 "$ROOT/tools/xsdk/test_vertex_fetch.py" --xsdk "$XSDK" --vulkan "$VULKAN4XENON"
python3 "$ROOT/tools/xsdk/test_render_targets.py" --vulkan "$VULKAN4XENON" --out "$OUT/target-tests"
python3 "$ROOT/tools/xsdk/test_render_memory.py" --vulkan "$VULKAN4XENON" --out "$OUT/memory-tests"
python3 "$ROOT/tools/xsdk/test_vram_sampler.py" --vulkan "$VULKAN4XENON" --out "$OUT/sampler-tests"
python3 "$ROOT/tools/xsdk/test_boot_readback.py" --vulkan "$VULKAN4XENON" --out "$OUT/readback-tests"
python3 "$ROOT/tools/xsdk/test_hud_glow.py" --out "$OUT/hud-tests"
python3 "$ROOT/tools/xsdk/test_midpoint_gate.py" --out "$OUT/midpoint-tests"
python3 "$ROOT/tools/xsdk/test_draw_routing.py" --vulkan "$VULKAN4XENON" --out "$OUT/routing-tests"
python3 "$ROOT/tools/xsdk/test_present_submit.py" --vulkan "$VULKAN4XENON" --out "$OUT/present-tests"
python3 "$ROOT/tools/xsdk/test_frame_slots.py" --vulkan "$VULKAN4XENON" --out "$OUT/slot-tests"
python3 "$ROOT/tools/xsdk/test_background_fill.py" --vulkan "$VULKAN4XENON" --out "$OUT/fill-tests"
python3 "$ROOT/tools/xsdk/test_matrix_bake.py" --out "$OUT/matrix-tests"
python3 "$ROOT/tools/xsdk/test_midpoint_spin.py" --out "$OUT/spin-tests"
python3 "$ROOT/tools/xsdk/test_split_hud.py" --out "$OUT/split-hud-tests"
python3 "$ROOT/tools/xsdk/test_pause_background.py" --out "$OUT/pause-tests"
python3 "$ROOT/tools/xsdk/test_log_buffer.py" --out "$OUT/log-tests"
python3 "$ROOT/tools/xsdk/test_xa_stride.py" --out "$OUT/xa-tests"
python3 "$ROOT/tools/xsdk/prepare_sources.py" --root "$ROOT" --out "$ROOT/build-xsdk/gen"
make -C "$XSDK" -j"$JOBS" TOOLCHAIN="$XSDK_TOOLCHAIN/bin/powerpc-xsdk-elf-" build/libxsdk.a build/host/libxsc.so
make -C "$VULKAN4XENON" -j"$JOBS" XSDK="$XSDK" TOOLCHAIN="$XSDK_TOOLCHAIN/bin/powerpc-xsdk-elf-" build/libvulkan4xenon.a
cd "$OUT"
export XSDK_GLSLANG
python3 "$ROOT/tools/xsdk/prepare_shaders.py" --out "$OUT/shader-source"
python3 "$VULKAN4XENON/tools/build_shaders.py" --xost "$XSDK/xenos-toolchain" \
  --glslang "$ROOT/tools/xsdk/glslang.sh" --optimize --output ctr_shaders "$OUT"/shader-source/*
python3 "$ROOT/tools/xsdk/test_interpolator_registers.py" --xsdk "$XSDK" --bundle "$OUT/ctr_shaders.c"
python3 "$ROOT/tools/xsdk/test_shader_pixels.py" --xsdk "$XSDK" --bundle "$OUT/ctr_shaders.c"
python3 "$ROOT/tools/xsdk/test_data_fetch.py" --xsdk "$XSDK" --bundle "$OUT/ctr_shaders.c"
python3 "$ROOT/tools/xsdk/test_present_pixels.py" --xsdk "$XSDK" --bundle "$OUT/ctr_shaders.c"
python3 "$ROOT/tools/xsdk/test_dither_work.py" --xsdk "$XSDK" --bundle "$OUT/ctr_shaders.c"
python3 "$ROOT/tools/xsdk/test_vertex_shader.py" --xsdk "$XSDK" --bundle "$OUT/ctr_shaders.c"
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
