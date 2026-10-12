"""Scan raw + cooked bigfiles for `struct Model` records and report the
`headers` (offset 0x14) field's raw value in each.

struct Model: name[0x10], s16 id @0x10, s16 numHeaders @0x12, u32 headers @0x14
Model files begin with a 4-byte header; the Model struct starts at +4.
"""
import io
import os
import struct
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "ctr360"))
spec = importlib.util.spec_from_file_location("cook", os.path.join(ROOT, "tools", "ctr360", "cook_disc.py"))
cook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cook)

RAW = r"F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin"
COOKED = os.path.join(ROOT, "build-360", "ctr-u-360.bin")


def scan(path, label):
    data = io.open(path, "rb").read()
    cdpos, num_entry = struct.unpack_from("<ii", data, 0)
    entries = []
    for i in range(num_entry):
        at = 8 + i * 8
        off, size = struct.unpack_from("<ii", data, at)
        entries.append((off, size))
    print("== %s: %d entries" % (label, len(entries)))
    hits = 0
    zero = 0
    nonzero_samples = []
    zero_samples = []
    for e in entries:
        off = e[0] if isinstance(e, (tuple, list)) else e.offset
        size = e[1] if isinstance(e, (tuple, list)) else e.size
        blob = data[off:off + size]
        if len(blob) < 0x40:
            continue
        # scan aligned-ish positions for a Model struct with a printable name
        for o in range(0, min(len(blob) - 0x18, 0x40000), 4):
            name = blob[o:o + 0x10]
            if not name[:3].isalpha() or not all(32 <= c < 127 or c == 0 for c in name):
                continue
            ident, numh, hdr = struct.unpack_from(">hhI", blob, o + 0x10) if label == "cooked" else struct.unpack_from("<hhI", blob, o + 0x10)
            if not (0 <= ident < 0x1000 and 1 <= numh <= 16):
                continue
            hits += 1
            if hdr == 0:
                zero += 1
                if len(zero_samples) < 6:
                    zero_samples.append((o, name.split(b"\0")[0].decode(), ident, numh))
            else:
                if len(nonzero_samples) < 6:
                    nonzero_samples.append((o, name.split(b"\0")[0].decode(), ident, numh, hdr))
            break  # one model per position window is enough per offset
    print("  model-like records: %d, headers==0: %d" % (hits, zero))
    print("  nonzero samples:")
    for s in nonzero_samples:
        print("   ", s)
    print("  zero samples:")
    for s in zero_samples:
        print("   ", s)


scan(RAW, "raw")
scan(COOKED, "cooked")
