#!/usr/bin/env bash
# ctr360: build dist/default.xex from the build-360/gen mirror using MSBuild
# with the Xbox 360 platform toolset (VS2010 + XDK 21256).
#
# Usage: build_xex.sh [Debug|Release]      (default: Release)
# Log:   build-360/xex_build_log.txt
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONFIG="${1:-Release}"
case "$CONFIG" in
    Debug|Release) ;;
    *) echo "Usage: build_xex.sh [Debug|Release]" >&2; exit 2 ;;
esac
MIRROR="$ROOT/build-360/gen"
PROJ="$ROOT/build-360/xex/ctr360.vcxproj"
LOG="$ROOT/build-360/xex_build_log.txt"

# Fail on known mixed-field stores/LE reads of native state before compiling.
# Word-index packet sites remain a review inventory, not automatic swaps.
if ! python "$ROOT/tools/ctr360/audit_endian_source.py" --report "$ROOT/build-360/results/endian-source.json"; then
    echo "FATAL: native byte-order source audit failed" >&2
    exit 2
fi

MSBUILD="/c/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe"
if [ ! -x "$MSBUILD" ]; then
    echo "MSBuild v4.0.30319 not found" >&2
    exit 2
fi
if [ ! -d "$MIRROR" ]; then
    echo "mirror not found: $MIRROR (run build_360_mirror.py first)" >&2
    exit 2
fi

# Keep the XDK project in source control; build-360 is disposable output.
# This also makes a clean checkout buildable without private project files.
mkdir -p "$(dirname "$PROJ")"
if ! cmp -s "$ROOT/tools/ctr360/ctr360.vcxproj" "$PROJ"; then
    cp "$ROOT/tools/ctr360/ctr360.vcxproj" "$PROJ" || exit 2
fi

# The Xbox video backend is copied verbatim by the generator (apart from the
# C89 inline spelling pass). Sync it in seconds after renderer-only edits;
# the manifest check below still rejects any other stale source or output.
if ! python "$ROOT/tools/ctr360/sync_mirror_video.py"; then
    echo "FATAL: incremental video sync failed; regenerate build-360/gen" >&2
    exit 2
fi
if ! python "$ROOT/tools/ctr360/sync_mirror_units.py"; then
    echo "FATAL: incremental unit sync failed; regenerate build-360/gen" >&2
    exit 2
fi

# Do not compile a generated tree unless it still describes the authoritative
# sources and this exact generator.  Timestamps are insufficient here: source
# archives and checkouts can preserve them, and generated files are easy to
# edit by accident.  The generator writes this manifest only after a complete
# fresh transform.
if ! python - "$ROOT" "$MIRROR" <<'PY'
import hashlib
import json
import os
import subprocess
import sys

root, mirror = map(os.path.abspath, sys.argv[1:])
manifest_path = os.path.join(mirror, "_ctr360_mirror_manifest.json")

def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def tree_hashes(base, names):
    result = {}
    for name in names:
        directory = os.path.join(base, name)
        if not os.path.isdir(directory):
            continue
        for path, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d != ".git"]
            for filename in files:
                full = os.path.join(path, filename)
                if os.path.isfile(full):
                    result[os.path.relpath(full, base).replace(os.sep, "/")] = digest(full)
    return dict(sorted(result.items()))

try:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
except (OSError, ValueError) as exc:
    raise SystemExit("FATAL: mirror manifest is missing or invalid: %s (%s)" % (manifest_path, exc))

if manifest.get("format") != 1 or manifest.get("generator") != "tools/ctr360/build_360_mirror.py":
    raise SystemExit("FATAL: mirror manifest has an unsupported format")

expected_generator = manifest.get("generator_sha256")
generator = os.path.join(root, "tools", "ctr360", "build_360_mirror.py")
if not isinstance(expected_generator, str) or not os.path.isfile(generator) or digest(generator) != expected_generator:
    raise SystemExit("FATAL: mirror is stale: build_360_mirror.py changed; regenerate build-360/gen")

try:
    current_commit = subprocess.check_output(
        ["git", "-C", root, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
    ).strip()
except (OSError, subprocess.CalledProcessError) as exc:
    raise SystemExit("FATAL: cannot verify mirror source commit: %s" % exc)
if manifest.get("source_commit") != current_commit:
    raise SystemExit("FATAL: mirror is stale: source commit changed; regenerate build-360/gen")

expected_sources = manifest.get("authoritative_files")
actual_sources = tree_hashes(root, ("game", "include", "platform"))
if not isinstance(expected_sources, dict) or actual_sources != expected_sources:
    raise SystemExit("FATAL: mirror is stale: authoritative game/include/platform sources changed; regenerate build-360/gen")

expected_generated = manifest.get("generated_files")
actual_generated = tree_hashes(mirror, ("game", "include", "platform"))
for name in ("_transform_report.json", "game/_ctr360_fixups.c"):
    path = os.path.join(mirror, *name.split("/"))
    if os.path.isfile(path):
        actual_generated[name] = digest(path)
if not isinstance(expected_generated, dict) or actual_generated != expected_generated:
    raise SystemExit("FATAL: mirror contents differ from its manifest; regenerate build-360/gen")

print("mirror manifest: current")
PY
then
    exit 2
fi

# The Xbox 360 platform targets live under the VS2010 MSBuild tree.
export VCTargetsPath='C:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\'

# The ImageXex step is incremental and, in this project's unity setup, it can
# decide the .xex is up to date even when the linked .exe just changed (the
# .xex is written through a different target than the .exe it consumes). A
# stale .xex means Xenia runs old code while every log and md5 says "new
# build" -- remove the target so the packaging step must run.
rm -f "$ROOT/build-360/xex/$CONFIG/ctr360.xex"

WINPROJ="$(cygpath -w "$PROJ")"
WINMIRROR="$(cygpath -w "$MIRROR")"

# Keep an exact address/name map for real-console fault logs. Release XDBs
# can omit the game's private symbols; generating a map changes no runtime
# optimization or diagnostic behavior.
if ! python - "$PROJ" <<'PY'
import sys
import xml.etree.ElementTree as ET
ns = 'http://schemas.microsoft.com/developer/msbuild/2003'
ET.register_namespace('', ns)
tree = ET.parse(sys.argv[1])
changed = False
for link in tree.getroot().iter('{%s}Link' % ns):
    for key, value in [('GenerateMapFile', 'true'),
                       ('MapFileName', r'$(MSBuildProjectDirectory)\$(Configuration)\ctr360.map')]:
        node = link.find('{%s}%s' % (ns, key))
        if node is None:
            node = ET.SubElement(link, '{%s}%s' % (ns, key))
        if node.text != value:
            node.text = value
            changed = True
if changed:
    tree.write(sys.argv[1], encoding='utf-8', xml_declaration=True)
PY
then
    echo "FATAL: could not enable linker map for console fault reports" >&2
    exit 3
fi

"$MSBUILD" "$WINPROJ" -nologo -v:minimal -m \
    -p:Configuration="$CONFIG" "-p:Platform=Xbox 360" \
    -p:MirrorRoot="$WINMIRROR" > "$LOG" 2>&1
rc=$?

echo "msbuild exit: $rc   (log: $LOG)"
ERROR_LINES=$(grep -c ': error' "$LOG" 2>/dev/null)
ERROR_LINES=${ERROR_LINES:-0}
echo "errors:   $ERROR_LINES"
echo "warnings: $(grep -c ': warning' "$LOG" 2>/dev/null || echo 0)"
grep ': error' "$LOG" 2>/dev/null | sed 's/^/  /' | head -40

# Hard gate: MSBuild has been observed to exit 0 with ': error' lines in the
# log, which (with an unchanged .exe/.xex pair) silently runs stale code.
if [ "$rc" -ne 0 ] || [ "$ERROR_LINES" -gt 0 ]; then
    echo "FATAL: build failed (msbuild exit $rc, $ERROR_LINES error line(s)) -- not staging anything" >&2
    exit 3
fi

# Content freshness: the linked PE must be at least as new as every source in
# the mirror, otherwise a compile step was dropped and the .exe is stale.
CONFIG_DIR="$ROOT/build-360/xex/$CONFIG"
if [ -f "$CONFIG_DIR/ctr360.exe" ]; then
    STALE_SRC=$(find "$MIRROR" -type f \( -name '*.c' -o -name '*.h' \) -newer "$CONFIG_DIR/ctr360.exe" 2>/dev/null | head -5)
    if [ -n "$STALE_SRC" ]; then
        echo "FATAL: ctr360.exe is older than mirrored source(s):" >&2
        echo "$STALE_SRC" | sed 's/^/  /' >&2
        exit 3
    fi
fi

# Freshness assertion: the packaged .xex must not be older than the linked PE,
# otherwise the run would exercise stale code.
if [ -f "$CONFIG_DIR/ctr360.exe" ] && [ -f "$CONFIG_DIR/ctr360.xex" ]; then
    if [ "$CONFIG_DIR/ctr360.exe" -nt "$CONFIG_DIR/ctr360.xex" ]; then
        echo "FATAL: ctr360.xex is OLDER than ctr360.exe -- packaging step was skipped" >&2
        exit 3
    fi
fi

# The ImageXex target writes <config>/<project>.xex; stage it as the console
# convention name next to the data layout prepared by prep_test.sh.
BUILT_XEX="$ROOT/build-360/xex/$CONFIG/ctr360.xex"
if [ $rc -eq 0 ] && [ -f "$BUILT_XEX" ]; then
    mkdir -p "$ROOT/build-360/xex/dist"
    cp -f "$BUILT_XEX" "$ROOT/build-360/xex/dist/default.xex"
    # Xenia loads symbols from <xex name>.xdb; stage it under the same name so
    # function-level tracing and the debugger UI have the guest's symbols.
    # The XDK writes it beside the xex in dist/ (Release|Debug/ on some setups).
    for cand in "$ROOT/build-360/xex/dist/ctr360.xdb" "$ROOT/build-360/xex/$CONFIG/ctr360.xdb"; do
        if [ -f "$cand" ]; then
            cp -f "$cand" "$ROOT/build-360/xex/dist/default.xdb"
            break
        fi
    done
    ls -la "$ROOT/build-360/xex/dist/default.xex" | awk '{print "xex:", $5, "bytes", $9}'
    echo "$BUILT_XEX"
fi
exit $rc
