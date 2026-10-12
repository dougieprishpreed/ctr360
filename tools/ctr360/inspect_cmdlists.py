"""Validate command-list + color-layout layout on the ndi_box pack (entry 514)."""
import struct
import importlib.util
import os

spec = importlib.util.spec_from_file_location("cook", os.path.join(os.getcwd(), "tools", "ctr360", "cook_disc.py"))
cook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cook)

RAW = r"F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin"
iso = cook.IsoImage(RAW)
f = iso.find("BIGFILE.BIG")
raw_dir = iso.read(f.lba, 8 + 4096 * 8)
num_entry, = struct.unpack_from("<i", raw_dir, 4)
entries = [struct.unpack_from("<ii", raw_dir, 8 + i * 8) for i in range(num_entry)]
ENTRY = 514
off_s, size = entries[ENTRY]
data = iso.read(f.lba + off_s, size)
iso.close()

map_off, = struct.unpack_from("<i", data, 0)
numb, = struct.unpack_from("<i", data, 4 + map_off)
moffs = struct.unpack_from("<%di" % (numb >> 2), data, 4 + map_off + 4)
covered = set(moffs)


def u32(off):
    return struct.unpack_from("<I", data, off)[0]


# re-find models via names, like the earlier inspector
seen = []
for o in range(0, min(len(data) - 0x18, 0x40000)):
    name = data[o:o + 0x10]
    if sum(1 for b in name if 32 <= b < 127) < 4 or b"\0" not in name or (o - 4) % 4:
        continue
    ident, numh, hdr = struct.unpack_from("<hhI", data, o + 0x10)
    if 0 <= ident < 0x1000 and 1 <= numh <= 4:
        seen.append(o)

print("models found: %d" % len(seen))
for o in seen[:4]:
    ident, numh, hdr = struct.unpack_from("<hhI", data, o + 0x10)
    h = 4 + hdr
    cmd_rel, frd, tex, col_rel = struct.unpack_from("<IIII", data, h + 0x20)
    print("model@%#x id=%#x hdr@%#x cmd_rel=%#x (%s) colors_rel=%#x (%s)"
          % (o, ident, h, cmd_rel, "MAP" if (cmd_rel) in covered else "scalar?", col_rel, "MAP" if (col_rel) in covered else "scalar?"))
    cfile = 4 + cmd_rel
    count = u32(cfile)
    words = []
    p = cfile + 4
    term = None
    for i in range(0x4000):
        w = u32(p + i * 4)
        if w == 0xFFFFFFFF:
            term = i
            break
        words.append(w)
    print("   count(word0)=%d; %d command words; terminator at word %s" % (count, len(words), term))
    print("   first commands: %s" % " ".join("%08x" % w for w in words[:6]))
    if col_rel:
        cfol = 4 + col_rel
        cw = [u32(cfol + i * 4) for i in range(min(count, 8))]
        print("   color[0..%d] = %s" % (min(count, 8), " ".join("%08x" % w for w in cw)))
