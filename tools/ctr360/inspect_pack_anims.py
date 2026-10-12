"""Inspect the 'ndi_box' model pack (raw entry 514): models -> headers ->
anims -> numFrames/frameSize/first frame raw LE values."""
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
n = numb >> 2
moffs = struct.unpack_from("<%di" % n, data, 4 + map_off + 4)
print("entry %d: %d bytes, map_off=%d, %d map offsets; first 12: %s" % (ENTRY, size, map_off, n, moffs[:12]))

# find Model structs by scanning for plausible names + counts
hits = []
for o in range(0, min(len(data) - 0x18, 0x40000)):
    name = data[o:o + 0x10]
    if sum(1 for b in name if 32 <= b < 127) < 4 or b"\0" not in name:
        continue
    ident, numh, hdr = struct.unpack_from("<hhI", data, o + 0x10)
    if not (0 <= ident < 0x1000 and 1 <= numh <= 4):
        continue
    if (o - 4) % 4:
        continue
    hits.append((o, name.split(b"\0")[0].decode(), ident, numh, hdr))

print("model-like hits: %d" % len(hits))
for (o, name, ident, numh, hdr) in hits[:6]:
    fo = 4 + hdr  # headers array in file space
    print("Model @%#x name=%s id=%#x numHeaders=%d headers_rel=%#x -> file+%#x" % (o, name, ident, numh, hdr, fo))
    for k in range(min(numh, 2)):
        h = fo + k * 0x40
        hname = data[h:h + 0x10].split(b"\0")[0]
        unk1, = struct.unpack_from("<i", data, h + 0x10)
        maxd, flags = struct.unpack_from("<hH", data, h + 0x14)
        cmd, frd, tex, col = struct.unpack_from("<IIII", data, h + 0x20)
        unk3, nanim, panims = struct.unpack_from("<III", data, h + 0x30)
        print("  hdr[%d] @%#x %-16s unk1=%#x maxD=%d flags=%#x cmd=%#x frmdata=%#x nanim=%d ptrAnims_rel=%#x"
              % (k, h, hname.decode(errors="replace"), unk1, maxd, flags, cmd, frd, nanim, panims))
        if 1 <= nanim <= 64 and panims and (panims & 3) == 0:
            afo = 4 + panims
            for a in range(min(nanim, 3)):
                aptr, = struct.unpack_from("<I", data, afo + a * 4)
                ao = 4 + aptr
                if ao + 0x18 > len(data):
                    print("    anim[%d] ptr=%#x OUT OF RANGE" % (a, aptr))
                    continue
                aname = data[ao:ao + 0x10]
                nf, fs = struct.unpack_from("<Hh", data, ao + 0x10)
                delta, = struct.unpack_from("<I", data, ao + 0x14)
                f0 = ao + 0x18
                p = struct.unpack_from("<3h", data, f0)
                vo, = struct.unpack_from("<i", data, f0 + 0x18)
                print("    anim[%d] rel=%#x name=%s numFrames=%d frameSize=%d delta=%#x frame0.pos=%s vo=%#x"
                      % (a, aptr, aname.split(b'\0')[0].decode(errors="replace"), nf, fs, delta, p, vo))
