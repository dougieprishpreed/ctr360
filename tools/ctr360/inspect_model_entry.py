"""Deep-dive one model file (entry from the scanner): full-file pointer map,
Model struct fields, in the raw and cooked images (cooked dir is BE)."""
import io
import os
import struct
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
spec = importlib.util.spec_from_file_location("cook", os.path.join(ROOT, "tools", "ctr360", "cook_disc.py"))
cook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cook)

RAW = r"F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin"
COOKED = os.path.join(ROOT, "build-360", "ctr-u-360.bin")

ENTRY = 366


def report(path, label, dir_order):
    iso = cook.IsoImage(path)
    lba = cook.BigFile.__new__(cook.BigFile)  # avoid __init__'s LE assumption
    hub = iso.read  # bind
    # find bigfile lba + entries manually: reuse IsoImage.find on BIGFILE.BIG
    big = None
    f = iso.find("BIGFILE.BIG") if hasattr(iso, "find") else None
    if f is None:
        raise SystemExit("no BIGFILE")
    dirsize = 8 + 4096 * 8
    raw_dir = iso.read(f.lba, dirsize)
    num_entry, = struct.unpack_from(dir_order + "i", raw_dir, 4)
    entries = []
    for i in range(num_entry):
        off, size = struct.unpack_from(dir_order + "ii", raw_dir, 8 + i * 8)
        entries.append((off, size))
    off_sectors, size = entries[ENTRY]
    data = iso.read(f.lba + off_sectors, size)
    print("== %s: entry %d, %d bytes" % (label, ENTRY, size))
    map_off, = struct.unpack_from(dir_order + "i", data, 0)
    print("   word0 (map offset) = %d, size=%d" % (map_off, size))
    if 0 <= map_off and 4 + map_off + 8 <= size:
        numb, = struct.unpack_from(dir_order + "i", data, 4 + map_off)
        n = numb >> 2
        offs = struct.unpack_from(dir_order + "%di" % n, data, 4 + map_off + 4)
        print("   map numBytes=%d (%d offsets); 0x14 in map: %s; first 16: %s"
              % (numb, n, 0x14 in offs, offs[:16]))
    name = data[4:20].split(b"\0")[0]
    ident, numh, hdr = struct.unpack_from(dir_order + "hhI", data, 0x14)
    print("   Model: name=%s id=%#x numHeaders=%d headers=%#010x (bytes %s)"
          % (name.decode(errors="replace"), ident, numh, hdr, data[0x18:0x1c].hex()))
    # what's AT the headers target
    if 0x14 + 4 <= size:
        tgt = 0x14 + 4  # realFileBuf offset of headers' target = 0x18 + 0? print raw bytes at file offset 0x18
    print("   bytes at file+0x18..0x30: %s" % data[0x18:0x30].hex())
    iso.close()


report(RAW, "raw", "<")
report(COOKED, "cooked", ">")
