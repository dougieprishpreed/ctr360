"""Copy the unchanged Xbox video source into an existing generated mirror.

This is an incremental build shortcut for a file the generator only copies
(apart from its harmless C89 inline spelling pass).  The normal build gate
still verifies every authoritative and generated file against the manifest.
"""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parents[2]
relative = Path("platform/xbox360/native_xbox360_video.c")
source = root / relative
mirror = root / "build-360/gen"
target = mirror / relative
manifest_path = mirror / "_ctr360_mirror_manifest.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
key = relative.as_posix()
old_target = target.read_bytes()
if digest(old_target) != manifest["generated_files"][key]:
    raise SystemExit("mirror video file differs from the recorded generated version")

source_data = source.read_bytes()
target_data = source_data.replace(b" inline ", b" __inline ")
if (digest(source_data) == manifest["authoritative_files"][key]
        and digest(target_data) == manifest["generated_files"][key]):
    print("mirror video already current")
    raise SystemExit(0)
target.write_bytes(target_data)
manifest["authoritative_files"][key] = digest(source_data)
manifest["generated_files"][key] = digest(target_data)
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("synchronized", key)
