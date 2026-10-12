"""Read-only audit helper (scratch, deletable): enumerate level-shaped entries and
report mesh_info contents, plus model/anim/frame scalar cook status."""
import struct, sys
sys.path.insert(0, '.')
from iso_bigfile import IsoImage, BigFile

IMG = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
iso = IsoImage(IMG)
big = BigFile(iso)


def u32(raw, f):
    return struct.unpack_from('<I', raw, 4 + f)[0]


print('entry  size      numInst numModels  mesh:numQB numVert bspRoot numBsp   instDefs')
for e in range(big.num_entry):
    off_s, size = big.entries[e]
    if size < 0x400:
        continue
    raw = iso.read(big.lba + off_s, size)
    mo, = struct.unpack_from('<i', raw, 0)
    if mo < 0 or (4 + mo + 8) > size:
        continue
    nb, = struct.unpack_from('<i', raw, 4 + mo)
    if nb <= 0 or (nb & 3) or (4 + mo + 4 + nb) > size:
        continue
    count = nb // 4
    offs = set(struct.unpack_from('<%di' % count, raw, 4 + mo + 4))
    if not all(f in offs for f in (0, 4, 8, 16, 24)):
        continue
    vals = [u32(raw, f) for f in (0, 4, 8, 16, 24)]
    if any((v % 4) or v == 0 or (4 + v + 0x10) > size for v in vals):
        continue
    num_inst = u32(raw, 12)
    num_models = u32(raw, 20)
    if not (1 <= num_inst <= 4096 and 1 <= num_models <= 4096):
        continue
    mesh_rel = u32(raw, 0)
    mf = 4 + mesh_rel
    if mf + 0x20 > size:
        continue
    numQB, numV, unk1, ptrQB, ptrV, unk2, bspRoot, numBsp = struct.unpack_from('<8i', raw, mf)
    arr = u32(raw, 24)
    roots = [u32(raw, arr + k * 4) for k in range(num_models)]
    names = [raw[4 + r:4 + r + 10].split(b'\0')[0].decode('latin1') for r in roots[:3]]
    print('%-5d %-9d %-7d %-9d      %-8d %-7d %-8d %-7d %s' % (e, size, num_inst, num_models, numQB, numV, bspRoot, numBsp, ','.join(names)))
iso.close()
