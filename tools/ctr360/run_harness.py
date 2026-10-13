"""ctr360 run harness (IMPLEMENTATION_PLAN Phase 0.3).

One command per experiment: it stages nothing, but it records everything a
result needs to be trustworthy - XEX and asset hashes, the trace categories in
force, the guest log, the framebuffer captures with their pixel sums and wall
times - and prints one outcome line:

    PASS / FAULT / PACKET_INVALID / STALLED / TIMEOUT / ASSET_MISMATCH /
    CAPTURE_MISSING / PIXELS_UNCHANGED

Usage:
    python tools/ctr360/run_harness.py [--secs 90] [--trace cull,packet]
                                       [--tag name] [--expect-frame 700]
                                       [--expect-capture '*_f0700_vram.tga']
                                       [--expect-pixel-change]
                                       [--no-launch] [--keep-log]

--trace writes cache:\\ctr360_trace.txt for this run (see
platform/native_trace.c for the category names); without it the file is
removed and the build's default mask applies. Results land in
build-360/results/<stamp>_<tag>/.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import fnmatch
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
XENIA_DIR = r"F:\downloads\xenia_canary_windows"
CACHE = os.path.join(XENIA_DIR, "cache")
GUEST_LOG = os.path.join(CACHE, "ctr360.log")
XENIA_LOG = os.path.join(XENIA_DIR, "xenia.log")
TRACE_FILE = os.path.join(CACHE, "ctr360_trace.txt")

XEX = os.path.join(ROOT, "build-360", "xex", "dist", "default.xex")
# ImageXex compresses the packaged .xex, so build identity is read from the
# linked PE (plain strings) that the .xex was produced from.
XEX_PE = os.path.join(ROOT, "build-360", "xex", "Release", "ctr360.exe")
COOKED = os.path.join(ROOT, "build-360", "ctr-u-360.bin")
STAGED = os.path.join(ROOT, "build-360", "xex", "dist", "assets", "ctr-u.bin")
RESULTS = os.path.join(ROOT, "build-360", "results")

# Probes whose presence in the built image identifies the build under test.
BUILD_PROBES = ["xs-pick f=%d", "xq f=%d", "trace mask="]
HEARTBEAT_RE = re.compile(r"\[probe\]\s+(?:hbm|hb)\s+f=(\d+)\b")
PACKET_FAILURES = (
    "invalid tag length",
    "invalid packet length",
    "invalid-prim",
    "did not output valid primitive",
    "Unhandled tagless primitive",
    "Unhandled tagless",
    "Unhandled zero length",
    "[CTR GPU] packet reports kind=",
    "-guard",
)
CPU_ACTIVE_SECONDS = 0.05


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pixelsum(path):
    """Checksum of the DECODED pixels, matching tools/ctr360/tga_to_png.py
    (16bpp BGR555, big-endian host-order bytes on Xenon, expanded to RGB and
    md5'd). This is the value the session-8 captures were compared with, so
    pixelsums stay comparable across sessions."""
    import struct
    with open(path, "rb") as f:
        data = f.read()
    width, height = struct.unpack_from("<HH", data, 12)
    offset = 18 + data[0]
    rgb = bytearray()
    for i in range(width * height):
        v = struct.unpack_from(">H", data, offset + i * 2)[0]
        b5, g5, r5 = v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F
        rgb.append((r5 << 3) | (r5 >> 2))
        rgb.append((g5 << 3) | (g5 >> 2))
        rgb.append((b5 << 3) | (b5 >> 2))
    return hashlib.md5(bytes(rgb)).hexdigest()[:16]


def read_log(path):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def grep_lines(text, needles):
    out = []
    for line in text.splitlines():
        for n in needles:
            if n in line:
                out.append(line)
                break
    return out


def max_frame(text):
    """Highest guest frame seen. Both heartbeats count: `hbm` (menu) and `hb`
    (every 30 frames outside the menu)."""
    frames = heartbeat_frames(text)
    return max(frames) if frames else -1


def heartbeat_frames(text):
    """Return only frame values from actual heartbeat records.

    Trace lines can contain other ``f=`` fields.  Matching the complete probe
    prefix prevents those fields from being mistaken for a frame heartbeat.
    """
    return [int(match.group(1)) for match in HEARTBEAT_RE.finditer(text)]


def heartbeat_evidence(text):
    frames = heartbeat_frames(text)
    first = frames[0] if frames else -1
    last = frames[-1] if frames else -1
    return {
        "heartbeat_count": len(frames),
        "heartbeat_first_frame": first,
        "heartbeat_last_frame": last,
        "heartbeat_max_frame": max(frames) if frames else -1,
        "heartbeat_progressed": any(b > a for a, b in zip(frames, frames[1:])),
    }


def launch_minimized(exe, cwd):
    """Start the emulator without stealing focus (SW_MINIMIZE)."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 6  # SW_MINIMIZE
    return subprocess.Popen([exe, XEX], cwd=cwd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, startupinfo=si)


def wait_for_frame(log_path, target, deadline):
    """Poll the guest log until the frame heartbeat reaches `target` (or the
    deadline passes). Returns the frame seen, or -1."""
    while time.time() < deadline:
        seen = max_frame(read_log(log_path))
        if seen >= target:
            return seen
        time.sleep(2.0)
    return max_frame(read_log(log_path))


def cpu_active(cpu):
    try:
        return float(cpu) >= CPU_ACTIVE_SECONDS
    except (TypeError, ValueError):
        return False


def capture_requirements(captures, expected, require_change):
    names = [capture["file"] for capture in captures]
    missing = [pattern for pattern in expected
               if not any(fnmatch.fnmatch(name, pattern) for name in names)]
    distinct = len({capture["pixelsum"] for capture in captures})
    return missing, distinct >= 2 if require_change else True, distinct


def classify(result, args):
    """Classify from recorded evidence so result.json and summary agree."""
    missing, pixels_changed, distinct = capture_requirements(
        result["captures"], args.expect_capture, args.expect_pixel_change)
    result["missing_expected_captures"] = missing
    result["pixels_changed"] = pixels_changed
    result["distinct_pixelsums"] = distinct

    if result["faults"] > 0:
        return "FAULT", "guest fault record"
    if result["packet_reports"] > 0:
        return "PACKET_INVALID", "packet validation record"
    if result["frames"] < 0:
        return "TIMEOUT", "no main-frame heartbeat"
    if result["frames"] < args.expect_frame:
        # A stalled guest is specifically one whose heartbeat stopped while
        # Xenia was still consuming CPU.  A run that kept advancing but missed
        # its deadline is a timeout, and analysis-only mode has no live CPU
        # sample with which to make a stall claim.
        if (not result["analysis_only"] and not result["heartbeat_progressed"]
                and result["cpu_active"]):
            return "STALLED", "heartbeat did not advance while CPU remained active"
        return "TIMEOUT", "expected frame was not reached before the deadline"
    if missing:
        return "CAPTURE_MISSING", "expected capture was not saved"
    if args.expect_pixel_change and not pixels_changed:
        return "PIXELS_UNCHANGED", "requested captures have no pixel change"
    return "PASS", "all requested gates passed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=int, default=90)
    ap.add_argument("--until-frame", type=int, default=0,
                    help="stop as soon as the guest reaches this frame (0 = run --secs)")
    ap.add_argument("--trace", default="")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--expect-frame", type=int, default=700)
    ap.add_argument("--expect-capture", action="append", default=[], metavar="GLOB",
                    help="require a saved VRAM capture matching GLOB (repeatable)")
    ap.add_argument("--expect-pixel-change", action="store_true",
                    help="require at least two saved captures with different decoded pixels")
    ap.add_argument("--no-launch", action="store_true", help="analyse the existing log only")
    ap.add_argument("--keep-log", action="store_true")
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    outdir = os.path.join(RESULTS, "%s_%s" % (stamp, args.tag))
    os.makedirs(outdir, exist_ok=True)

    result = {
        "stamp": stamp,
        "secs": args.secs,
        "trace": args.trace or "(default)",
        "xex": XEX,
        "outcome": "TIMEOUT",
        "frames": -1,
        "captures": [],
        "packet_reports": 0,
        "faults": 0,
        "guards": 0,
        "analysis_only": args.no_launch,
        "expected_frame": args.expect_frame,
        "expected_captures": args.expect_capture,
        "expect_pixel_change": args.expect_pixel_change,
        "heartbeat_count": 0,
        "heartbeat_first_frame": -1,
        "heartbeat_last_frame": -1,
        "heartbeat_max_frame": -1,
        "heartbeat_progressed": False,
        "cpu_over_3s": "n/a",
        "cpu_active": False,
    }

    # --- artifact identity -------------------------------------------------
    if not os.path.isfile(XEX):
        result["outcome"] = "ASSET_MISMATCH"
        result["classification_reason"] = "packaged XEX is missing"
        write_results(outdir, result)
        print("ASSET_MISMATCH: missing %s" % XEX)
        return 2
    result["xex_md5"] = md5(XEX)
    result["xex_mtime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(XEX)))
    result["xex_size"] = os.path.getsize(XEX)

    with open(XEX_PE if os.path.isfile(XEX_PE) else XEX, "rb") as f:
        image = f.read()
    missing = [p for p in BUILD_PROBES if p.encode("ascii") not in image]
    result["build_probes_missing"] = missing

    cooked_md5 = md5(COOKED) if os.path.isfile(COOKED) else "(missing)"
    staged_md5 = md5(STAGED) if os.path.isfile(STAGED) else "(missing)"
    result["cooked_md5"] = cooked_md5
    result["staged_md5"] = staged_md5
    if cooked_md5 != staged_md5:
        result["outcome"] = "ASSET_MISMATCH"
        print("ASSET_MISMATCH: cooked %s != staged %s (run prep_test.sh --cooked)" % (cooked_md5, staged_md5))
        write_results(outdir, result)
        return 2

    # --no-launch is a read-only analysis.  In particular it must not change
    # the trace mask, remove old captures, or terminate an existing emulator.
    if not args.no_launch:
        # --- trace categories ----------------------------------------------
        if args.trace:
            with open(TRACE_FILE, "w") as f:
                f.write(args.trace + "\n")
            result["trace"] = args.trace
        elif os.path.exists(TRACE_FILE):
            os.remove(TRACE_FILE)

    # --- run ---------------------------------------------------------------
    if not args.no_launch:
        if os.path.exists(GUEST_LOG) and not args.keep_log:
            os.remove(GUEST_LOG)
        for name in os.listdir(CACHE):
            if name.startswith("ctr360_") and name.endswith("_vram.tga"):
                os.remove(os.path.join(CACHE, name))

        proc = launch_minimized(os.path.join(XENIA_DIR, "xenia_canary.exe"), XENIA_DIR)
        if args.until_frame > 0:
            # Stop as soon as the frame of interest is reached: the state that
            # matters (the boot freeze) is in the first frames, so waiting for a
            # fixed wall time only burns minutes.
            seen = wait_for_frame(GUEST_LOG, args.until_frame, time.time() + args.secs)
            result["stopped_at_frame"] = seen
        else:
            time.sleep(args.secs)

        cpu = "n/a"
        try:
            ps = ("$p=Get-Process xenia_canary -ErrorAction SilentlyContinue;"
                  "if($p){$c1=$p.TotalProcessorTime.TotalSeconds;Start-Sleep -Seconds 3;"
                  "$c2=(Get-Process xenia_canary).TotalProcessorTime.TotalSeconds;"
                  "Write-Output ([math]::Round($c2-$c1,2))}")
            cpu = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True).stdout.strip() or "n/a"
        except OSError:
            pass
        result["cpu_over_3s"] = cpu
        result["cpu_active"] = cpu_active(cpu)

        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Stop-Process -Name xenia_canary -Force -ErrorAction SilentlyContinue"],
                       capture_output=True)
        time.sleep(1)

    # --- collect -----------------------------------------------------------
    text = read_log(GUEST_LOG)
    shutil.copy(GUEST_LOG, os.path.join(outdir, "guest.log")) if os.path.isfile(GUEST_LOG) else None
    if os.path.isfile(XENIA_LOG):
        xtext = read_log(XENIA_LOG)
        keep = grep_lines(xtext, ["ctr360", "default.xex", "Vulkan", "assert", "Fatal"])
        with open(os.path.join(outdir, "xenia_excerpt.log"), "w", errors="replace") as f:
            f.write("\n".join(keep[-200:]))

    result.update(heartbeat_evidence(text))
    result["frames"] = result["heartbeat_max_frame"]
    result["faults"] = len(grep_lines(text, ["[fault]"]))
    result["guards"] = len(grep_lines(text, ["-guard"]))
    result["packet_reports"] = len(grep_lines(text, PACKET_FAILURES))
    result["audio_pump_lines"] = len(grep_lines(text, ["pump callbacks"]))
    result["title_lines"] = grep_lines(text, ["title-init", "title-menu", "trial"])[:4]

    for name in sorted(os.listdir(CACHE)):
        if name.startswith("ctr360_") and name.endswith("_vram.tga"):
            src = os.path.join(CACHE, name)
            dst = os.path.join(outdir, name)
            shutil.copy(src, dst)
            result["captures"].append({
                "file": name,
                "pixelsum": pixelsum(src),
                "mtime": time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(src))),
            })

    # --- classify ----------------------------------------------------------
    result["outcome"], result["classification_reason"] = classify(result, args)

    write_results(outdir, result)

    sums = {c["file"]: c["pixelsum"] for c in result["captures"]}
    uniq = len(set(sums.values()))
    print("%s  frames=%d  heartbeats=%d progressed=%s captures=%d (distinct pixelsums=%d)  faults=%d guards=%d packets=%d  cpu3s=%s"
          % (result["outcome"], result["frames"], result["heartbeat_count"], result["heartbeat_progressed"], len(sums), uniq, result["faults"], result["guards"],
             result["packet_reports"], result.get("cpu_over_3s", "n/a")))
    print("results: %s" % outdir)
    if missing:
        print("WARNING: built image is missing probe marker(s): %s" % missing)
    return 0 if result["outcome"] == "PASS" else 1


def write_results(outdir, result):
    with open(os.path.join(outdir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    with open(os.path.join(outdir, "summary.txt"), "w") as f:
        f.write("outcome: %s\n" % result["outcome"])
        for key in ("stamp", "secs", "trace", "analysis_only", "xex_md5", "xex_mtime",
                    "cooked_md5", "staged_md5", "expected_frame", "frames",
                    "heartbeat_count", "heartbeat_first_frame", "heartbeat_last_frame",
                    "heartbeat_max_frame",
                    "heartbeat_progressed", "faults", "guards", "packet_reports",
                    "audio_pump_lines", "cpu_over_3s", "cpu_active",
                    "expect_pixel_change", "pixels_changed", "distinct_pixelsums",
                    "classification_reason"):
            if key in result:
                f.write("%-18s %s\n" % (key + ":", result[key]))
        if result.get("expected_captures"):
            f.write("expected captures: %s\n" % ", ".join(result["expected_captures"]))
        if result.get("missing_expected_captures"):
            f.write("missing captures: %s\n" % ", ".join(result["missing_expected_captures"]))
        for c in result.get("captures", []):
            f.write("capture           %s  %s  %s\n" % (c["mtime"], c["pixelsum"], c["file"]))
        if result.get("title_lines"):
            f.write("title lines:\n")
            for line in result["title_lines"]:
                f.write("  %s\n" % line)


if __name__ == "__main__":
    sys.exit(main())
