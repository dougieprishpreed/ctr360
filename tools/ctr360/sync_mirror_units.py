"""Regenerate audited standalone units using the normal mirror AST passes.

These units have no site patches or generated static fixups.
All other inputs and outputs must still match the successful full mirror.
"""
import json
from pathlib import Path
import re
import build_360_mirror as generator


def main():
    root = Path(__file__).resolve().parents[2]
    mirror = root / "build-360/gen"
    # MainHD is a standalone render-only unit: no generated static fixups or
    # site patches. Its actual-function fixture verifies pose/DB/OT rewind;
    # XDK checks the target-only branch in the complete unity build.
    # RefreshCard has no site patches/static fixups; its card/ghost metadata
    # is native state, unlike raw LE asset structures. Parse/transform it using
    # the same AST pipeline after the complete memory-card mirror regeneration.
    # CS_Thread's packet repair is standalone as well; refuse the sync if the
    # AST pipeline ever finds skipped initializers or generated static fixups.
    allowed = {"game/CAM.c", "game/DrawSky.c", "game/Display.c", "game/MAIN/MainFrame.c", "game/MAIN/MainHD.c", "platform/native_gpu.c", "game/RenderBucket/RenderBucket_QueueExecute.c", "game/RefreshCard.c", "game/233/CS_Thread.c"}
    manifest_path = mirror / generator.MIRROR_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (mirror / ".ctr360_mirror.lock").exists():
        raise SystemExit("mirror generator is still running")
    if generator.sha256_file(generator.__file__) != manifest["generator_sha256"]:
        raise SystemExit("generator changed; full mirror regeneration required")
    sources = generator.tree_hashes(str(root), generator.MANIFEST_SOURCE_DIRS)
    if sources == manifest["authoritative_files"]:
        print("mirror standalone units already current")
        return
    changed = {k for k in sources.keys() | manifest["authoritative_files"].keys()
               if sources.get(k) != manifest["authoritative_files"].get(k)}
    if not changed <= allowed:
        raise SystemExit("full mirror regeneration required for changed inputs: " + ", ".join(sorted(changed)))
    outputs = generator.tree_hashes(str(mirror), generator.MANIFEST_SOURCE_DIRS)
    for k, digest in outputs.items():
        if digest != manifest["generated_files"].get(k):
            raise SystemExit("generated file changed: " + k)
    saved = {k: (mirror / k).read_bytes() for k in changed}
    try:
      for relative in sorted(changed):
        key = relative
        target = mirror / relative
        target.write_bytes((root / relative).read_bytes())
        if generator.run_verify(str(mirror), [relative], "clang", print):
            raise RuntimeError(relative + " source parsing failed; refusing to transform a partial AST")
        context = generator.Ctx(str(mirror))
        dump = generator.dump_unit(relative, str(mirror), "clang", print)
        edits, skipped, unions, fixups = generator.collect_edits_for_file(
            dump, relative.lower(), context, print, 0)
        if skipped or fixups:
            raise RuntimeError(relative + " requires skipped initializers or static fixups; use full generator")
        target.write_bytes(generator.apply_edits(target.read_bytes(), edits, print, relative))
        context.forget(relative.lower())
        dump = generator.dump_unit(relative, str(mirror), "clang", print)
        edits, notes = generator.collect_hoists_for_file(dump, relative.lower(), context, print)
        if notes:
            raise RuntimeError(relative + " hoist requires manual review: " + str(notes))
        target.write_bytes(generator.apply_edits(target.read_bytes(), edits, print, relative))
        target.write_bytes(re.sub(rb"\binline\b", b"__inline", target.read_bytes()))
        if generator.run_verify(str(mirror), [relative], "clang", print):
            raise RuntimeError(relative + " syntax verification failed")
        if relative.lower() in generator.scan_designator_lines(str(mirror)):
            raise RuntimeError(relative + " contains unconverted designated initializers")
        manifest["authoritative_files"][key] = generator.sha256_file(root / relative)
        manifest["generated_files"][key] = generator.sha256_file(target)
        print("regenerated and verified", relative)
      manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except BaseException:
        for key, old in saved.items():
            (mirror / key).write_bytes(old)
        raise


if __name__ == "__main__":
    main()
