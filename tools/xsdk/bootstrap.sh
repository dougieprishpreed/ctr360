#!/usr/bin/env bash
# Fetch pinned open dependencies and build their compiler and host shader tool.
# Install prerequisites from README first. No Microsoft files are used.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEPS="${CTR_XSDK_DEPS:-$ROOT/build-xsdk/deps}"
PREFIX="${XSDK_TOOLCHAIN:-$ROOT/build-xsdk/toolchain}"
JOBS="${JOBS:-1}"
mkdir -p "$DEPS"
fetch() {
  local name="$1" ref="$2" sha="$3"
  if [ ! -d "$DEPS/$name/.git" ]; then
    git clone --depth 1 --branch "$ref" "https://github.com/xenosworks/$name.git" "$DEPS/$name"
  fi
  if [ "$(git -C "$DEPS/$name" rev-parse HEAD)" != "$sha" ]; then
    git -C "$DEPS/$name" fetch --depth 1 origin "$sha"
    git -C "$DEPS/$name" checkout --detach "$sha"
  fi
}
fetch xsdk main 8c58c7a3fb37bb261c5a11a8a1f4fa8a8bfd0d28
fetch vulkan4xenon main df25dc50e6296d89822626b433f4080db05bccc8
fetch glslang-xenon xenon d2f00185cf5feaa449f6e15c1894fb232b2b6bcd
(cd "$DEPS/xsdk"; PREFIX="$PREFIX" WORK="$DEPS/toolchain-work" JOBS="$JOBS" bash tools/toolchain/build.sh)
mkdir -p "$PREFIX/share/ctr360-licenses"
cp "$DEPS"/toolchain-work/src/newlib-*/COPYING.NEWLIB "$PREFIX/share/ctr360-licenses/newlib.txt"
cp "$DEPS"/toolchain-work/src/gcc-*/COPYING3 "$PREFIX/share/ctr360-licenses/GPL-3.0.txt"
cp "$DEPS"/toolchain-work/src/gcc-*/COPYING.RUNTIME "$PREFIX/share/ctr360-licenses/GCC-runtime-exception.txt"
(cd "$DEPS/glslang-xenon"; python3 update_glslang_sources.py)
cmake -S "$DEPS/glslang-xenon" -B "$DEPS/glslang-xenon/build-host" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_OPT=ON -DENABLE_GLSLANG_BINARIES=ON -DBUILD_TESTING=OFF -DGLSLANG_TESTS=OFF
cmake --build "$DEPS/glslang-xenon/build-host" -j"$JOBS"
printf '\nUse these paths with tools/xsdk/build.sh:\nXSDK=%s\nVULKAN4XENON=%s\nXSDK_TOOLCHAIN=%s\nXSDK_GLSLANG=%s\n' \
 "$DEPS/xsdk" "$DEPS/vulkan4xenon" "$PREFIX" "$DEPS/glslang-xenon/build-host/StandAlone/glslang"
