"""Read-only audit helper (scratch, deletable): the raw-read vs byte-wise-read
convention per draw-path field, plus map coverage of the uncooked scalars."""
import struct, sys
sys.path.insert(0, '.')
from iso_bigfile import IsoImage

RETAIL = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
COOKED = r'F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\ctr-u-360.bin'


def open_big(path, little):
    iso = IsoImage(path)
    e = iso.find('BIGFILE.BIG')
    hdr = iso.read(e.lba, 8)
    cdpos, num = struct.unpack('<ii' if little else '>ii', hdr)
    raw = iso.read(e.lba, 8 + num * 8)
    return iso, e.lba, [struct.unpack_from('<ii' if little else '>ii', raw, 8 + i * 8) for i in range(num)]


a, alba, ae = open_big(RETAIL, True)
b, blba, be = open_big(COOKED, False)


def rd(iso, lba, ents, e):
    off_s, size = ents[e]
    return iso.read(lba + off_s, size)


def u32f(raw, f):
    return struct.unpack_from('<I', raw, 4 + f)[0]


def hexs(x):
    return x.hex()


for e in (514, 259, 41):
    ra = rd(a, alba, ae, e)
    rb = rd(b, blba, be, e)
    mo, = struct.unpack_from('<i', ra, 0)
    nb, = struct.unpack_from('<i', ra, 4 + mo)
    mp = set(struct.unpack_from('<%di' % (nb // 4), ra, 4 + mo + 4))
    print('==== entry %d  map words=%d' % (e, len(mp)))
    # find a model root
    if all(f in mp for f in (0, 4, 8, 16, 24)):
        arr = u32f(ra, 24)
        nm = u32f(ra, 20)
        roots = [u32f(ra, arr + k * 4) for k in range(nm)]
    else:
        roots = []
        off = 4
        while off in mp:
            t = u32f(ra, off)
            if t == 0 or (t % 4):
                break
            roots.append(t)
            off += 4
    for r in roots[:2]:
        hrel = u32f(ra, r + 0x14)
        hf = 4 + hrel
        cl = u32f(ra, hrel + 0x20)
        pa = u32f(ra, hrel + 0x38)
        name = ra[4 + r:4 + r + 16].split(b'\0')[0].decode('latin1')
        print('  model %r hdr@frame 0x%x' % (name, hrel))
        print('    cmdlist frame 0x%x  covered=%s' % (cl, cl in mp))
        if pa:
            print('    ptrAnimations frame 0x%x covered=%s' % (pa, pa in mp))
            a0 = u32f(ra, pa)
            print('    ModelAnim[0] frame 0x%x : numFrames slot 0x%x covered=%s ; frameSize slot 0x%x covered=%s ; ptrDeltaArray 0x%x covered=%s'
                  % (a0, a0 + 0x10, (a0 + 0x10) in mp, a0 + 0x12, (a0 + 0x12) in mp, a0 + 0x14, (a0 + 0x14) in mp))
            for nm2, f, sz in (('numFrames', 0x10, 2), ('frameSize', 0x12, 2)):
                print('       %-10s retail=%s cooked=%s  BE-read=%s' % (
                    nm2, hexs(ra[4 + a0 + f:4 + a0 + f + sz]), hexs(rb[4 + a0 + f:4 + a0 + f + sz]),
                    hexs(ra[4 + a0 + f:4 + a0 + f + sz][::-1])))
            fr = a0 + 0x18
            print('    first ModelFrame frame 0x%x : vertexOffset slot 0x%x covered=%s' % (fr, fr + 0x18, (fr + 0x18) in mp))
            print('       vertexOffset retail=%s cooked=%s' % (hexs(ra[4 + fr + 0x18:4 + fr + 0x1c]), hexs(rb[4 + fr + 0x18:4 + fr + 0x1c])))
            print('       pos.x/y/z retail=%s cooked=%s' % (hexs(ra[4 + fr:4 + fr + 6]), hexs(rb[4 + fr:4 + fr + 6])))
        fd = u32f(ra, hrel + 0x24)
        if fd:
            print('    ptrFrameData frame 0x%x covered=%s ; vertexOffset slot covered=%s retail=%s' % (
                fd, fd in mp, (fd + 0x18) in mp, hexs(ra[4 + fd + 0x18:4 + fd + 0x1c])))
        # AnimTex chain: are its numFrames cooked?
        atx = u32f(ra, hrel + 0x3C)
        if atx:
            print('    animtex frame 0x%x covered=%s nf retail=%s cooked=%s' % (
                atx, atx in mp, hexs(ra[4 + atx + 4:4 + atx + 6]), hexs(rb[4 + atx + 4:4 + atx + 6])))
a.close(); b.close()
