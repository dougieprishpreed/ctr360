#!/usr/bin/env sh
exec "${XSDK_GLSLANG:-glslang}" -Os "$@"
