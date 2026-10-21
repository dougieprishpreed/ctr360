#!/usr/bin/env bash
# Fetch pinned open dependencies and build their compiler and host shader tool.
# Install prerequisites from README first. No Microsoft files are used.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEPS="${CTR_XSDK_DEPS:-$ROOT/build-xsdk/deps}"
PREFIX="${XSDK_TOOLCHAIN:-$ROOT/build-xsdk/toolchain}"
JOBS="${JOBS:-8}"
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
fetch xsdk main 49307c7b5fe6cc0e262da7b31af58e4e309aa18e
fetch vulkan4xenon main 05549ffd76f5c8c65e68b29d14ffb67183287116
fetch glslang-xenon xenon a607c3a930b3d287357e5a928777e0d13dba10fa
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
