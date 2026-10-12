"""Read-only audit helper (scratch, deletable): driver/racer model packs -
are ModelAnim (numFrames/frameSize) and ModelFrame.vertexOffset cooked?"""
import struct, sys
sys.path.insert(0, '.')
from iso_bigfile import IsoImage

RETAIL = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
COOKED = r'F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\ctr-u-360.bin'


def open_big(path, little):
    iso = IsoImage(path)
    e = iso.find('BIGFILE.BIG')
    lba = e.lba
    hdr = iso.read(lba, 8)
    cdpos, num = struct.unpack('<ii' if little else '>ii', hdr)
    raw = iso.read(lba, 8 + num * 8)
    ents = [struct.unpack_from('<ii' if little else '>ii', raw, 8 + i * 8) for i in range(num)]
    return iso, lba, ents


a, alba, ae = open_big(RETAIL, True)
b, blba, be = open_big(COOKED, False)


def rd(iso, lba, ents, e):
    off_s, size = ents[e]
    return iso.read(lba + off_s, size)


def hexs(x):
    return x.hex()


# find packs containing a model named 'crash' or 'cortex'
for e in range(len(ae)):
    off_s, size = ae[e]
    if size < 0x1000:
        continue
    ra = rd(a, alba, ae, e)
    mo, = struct.unpack_from('<i', ra, 0)
    if mo < 0 or (4 + mo + 8) > size:
        continue
    nb, = struct.unpack_from('<i', ra, 4 + mo)
    if nb <= 0 or (nb & 3):
        continue
    cnt = nb // 4
    if (4 + mo + 4 + nb) > size or cnt < 16:
        continue
    offs = set(struct.unpack_from('<%di' % cnt, ra, 4 + mo + 4))
    if 4 not in offs:
        continue
    # collect leading-run model roots
    roots = []
    off = 4
    while off in offs:
        t = struct.unpack_from('<I', ra, 4 + off)[0]
        if t == 0 or (t % 4) or (4 + t + 0x40) > size:
            break
        roots.append(t)
        off += 4
    if len(roots) < 3:
        continue
    names = [ra[4 + r:4 + r + 12].split(b'\0')[0].decode('latin1') for r in roots]
    if not any(n in ('crash', 'cortex', 'tiny', 'polar', 'dingo') for n in names):
        continue
    print('==== entry %d size=%d models=%d names=%s' % (e, size, len(roots), names[:8]))
    rb = rd(b, blba, be, e)
    r = roots[0]
    mf = 4 + r
    hrel = struct.unpack_from('<I', ra, mf + 0x14)[0]
    hf = 4 + hrel
    for nm, base, f, sz in (('Model.id', mf, 0x10, 2), ('Model.numHeaders', mf, 0x12, 2),
                            ('MH.ptrFrameData', hf, 0x24, 4), ('MH.ptrAnimations', hf, 0x38, 4),
                            ('MH.animtex', hf, 0x3C, 4), ('MH.ptrCommandList', hf, 0x20, 4)):
        print('   %-20s retail=%s cooked=%s' % (nm, hexs(ra[base + f:base + f + sz]), hexs(rb[base + f:base + f + sz])))
    pa = struct.unpack_from('<I', ra, hf + 0x38)[0]
    if pa:
        a0 = struct.unpack_from('<I', ra, 4 + pa)[0]
        print('   ModelAnim[0] frame 0x%x' % a0)
        for nm, f, sz in (('MA.numFrames', 0x10, 2), ('MA.frameSize', 0x12, 2), ('MA.ptrDeltaArray', 0x14, 4)):
            print('      %-18s retail=%s cooked=%s' % (nm, hexs(ra[4 + a0 + f:4 + a0 + f + sz]), hexs(rb[4 + a0 + f:4 + a0 + f + sz])))
        fr = 4 + a0 + 0x18
        print('      first ModelFrame retail=%s cooked=%s' % (hexs(ra[fr:fr + 0x1c]), hexs(rb[fr:fr + 0x1c])))
    fd = struct.unpack_from('<I', ra, hf + 0x24)[0]
    if fd:
        print('   ptrFrameData frame 0x%x retail=%s cooked=%s' % (fd, hexs(ra[4 + fd:4 + fd + 0x1c]), hexs(rb[4 + fd:4 + fd + 0x1c])))
        vo = struct.unpack_from('<i', ra, 4 + fd + 0x18)[0]
        vob = struct.unpack_from('>i', ra, 4 + fd + 0x18)[0]
        print('      vertexOffset LE=%d  as-BE-read=%d' % (vo, vob))
    # 2nd model for extra confidence
    if len(roots) > 1:
        r2 = roots[1]
        h2 = 4 + struct.unpack_from('<I', ra, 4 + r2 + 0x14)[0]
        pa2 = struct.unpack_from('<I', ra, h2 + 0x38)[0]
        if pa2:
            a2 = struct.unpack_from('<I', ra, 4 + pa2)[0]
            print('   model1 %r MA.numFrames retail=%s cooked=%s frameSize retail=%s cooked=%s' % (
                ra[4 + r2:4 + r2 + 12].split(b'\0')[0],
                hexs(ra[4 + a2 + 0x10:4 + a2 + 0x12]), hexs(rb[4 + a2 + 0x10:4 + a2 + 0x12]),
                hexs(ra[4 + a2 + 0x12:4 + a2 + 0x14]), hexs(rb[4 + a2 + 0x12:4 + a2 + 0x14])))
    break
a.close(); b.close()
