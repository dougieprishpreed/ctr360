"""Inspect one Model file's pointer map in the raw and cooked bigfiles:
- word0 (map offset), numBytes of map, whether 0x14 (Model.headers) is listed,
- the Model struct at +4 (name/id/numHeaders/headers) in both images.
"""
import io
import os
import struct
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
spec = importlib.util.spec_from_file_location("cook", os.path.join(ROOT, "tools", "ctr360", "cook_disc.py"))
cook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cook)


def find_model_files(iso, big, byteorder, limit=6):
    found = []
    for idx in range(big.num_entry):
        off_sectors, size = big.entries[idx]
        if size < 0x40 or size > 4 << 20:
            continue
        head = iso.read(big.lba + off_sectors, min(size, 0x200))
        if len(head) < 0x40:
            continue
        try:
            name = head[4:20].split(b"\0")[0]
            ident, numh, hdr = struct.unpack_from(byteorder + "hhI", head, 0x14)
        except Exception:
            continue
        if not name or not all(32 <= c < 127 for c in name):
            continue
        if not (0 <= ident < 0x1000 and 1 <= numh <= 16):
            continue
        found.append((idx, name.decode(), ident, numh, hdr))
        if len(found) >= limit:
            break
    return found


def dump(iso, big, byteorder, label):
    print("== %s ==" % label)
    for idx, name, ident, numh, hdr in find_model_files(iso, big, byteorder):
        off_sectors, size = big.entries[idx]
        head = iso.read(big.lba + off_sectors, min(size, 0x1000))
        map_off, = struct.unpack_from(byteorder + "i", head, 0)
        info = "entry %3d size=%7d model=%s id=%#x numHeaders=%d headers=%#010x map_off=%d" % (
            idx, size, name, ident, numh, hdr, map_off)
        if map_off >= 0 and 4 + map_off + 4 <= len(head):
            numb, = struct.unpack_from(byteorder + "i", head, 4 + map_off)
            noff = numb >> 2
            offs = struct.unpack_from(byteorder + "%di" % min(noff, 60), head, 4 + map_off + 4)
            has = 0x14 in offs
            info += " numMapBytes=%d nOff=%d has_0x14=%s first_offs=%s" % (numb, noff, has, offs[:10])
        print(info)


RAW = r"F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin"
COOKED = os.path.join(ROOT, "build-360", "ctr-u-360.bin")

iso = cook.IsoImage(RAW)
big = cook.BigFile(iso)
dump(iso, big, "<", "raw")
iso.close()

iso = cook.IsoImage(COOKED)
big = cook.BigFile(iso)
dump(iso, big, ">", "cooked")
iso.close()
