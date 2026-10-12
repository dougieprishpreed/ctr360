"""Read-only audit helper (scratch, deletable): decode ModelHeader.ptrCommandList
words under LE and BE interpretations to decide whether they are numeric."""
import struct, sys
sys.path.insert(0, '.')
from iso_bigfile import IsoImage, BigFile

IMG = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
iso = IsoImage(IMG)
big = BigFile(iso)


def load(e):
    off_s, size = big.entries[e]
    raw = iso.read(big.lba + off_s, size)
    mo, = struct.unpack_from('<i', raw, 0)
    nb, = struct.unpack_from('<i', raw, 4 + mo)
    offs = set(struct.unpack_from('<%di' % (nb // 4), raw, 4 + mo + 4))
    return raw, offs


def u32(raw, f):
    return struct.unpack_from('<I', raw, 4 + f)[0]


def sw(w):
    return struct.unpack('<I', struct.pack('>I', w))[0]


def analyze(raw, mapset, roots, label):
    print('==== %s' % label)
    for r in roots[:10]:
        mf = 4 + r
        name = raw[mf:mf + 16].split(b'\0')[0].decode('latin1')
        hrel = u32(raw, r + 0x14)
        hf = 4 + hrel
        cl = struct.unpack_from('<I', raw, hf + 0x20)[0]
        px = struct.unpack_from('<I', raw, hf + 0x28)[0]
        pc = struct.unpack_from('<I', raw, hf + 0x2c)[0]
        if not cl:
            continue
        words = []
        k = 0
        while k < 16384:
            w = u32(raw, cl + k * 4)
            if w == 0xffffffff:
                break
            words.append(w)
            k += 1
        count = words[0]
        colbytes = count * 4
        okLE = okBE = tot = 0
        for w in words[1:]:
            for tag in ('LE', 'BE'):
                v = w if tag == 'LE' else sw(w)
                texIdx = v & 0x1ff
                colOff = (v >> 7) & 0x1fc
                good = (texIdx <= 512) and (colOff < colbytes)
                if tag == 'LE':
                    okLE += 1 if good else 0
                else:
                    okBE += 1 if good else 0
            tot += 1
        tl0 = u32(raw, px) if px else 0
        print('%-18s count=%-4d cmds=%-4d  plausibleLE=%d/%d plausibleBE=%d/%d  texLayout@0x%x colors@0x%x' % (
            name, count, tot, okLE, tot, okBE, tot, tl0, pc))
        for w in words[1:4]:
            for tag in ('LE', 'BE'):
                v = w if tag == 'LE' else sw(w)
                print('      %s %08x flags=%02x stk=%02x texIdx=%3d colOff=%3d bit27of(cmd<<4)=%d' % (
                    tag, v, (v >> 24) & 0xff, (v >> 16) & 0xff, v & 0x1ff, (v >> 7) & 0x1fc, ((v << 4) >> 31) & 1))
        # Also: does the word look like an OT/PSX pointer? (low 3 bytes small & ascending)
        lo = [w & 0xffffff for w in words[1:6]]
        print('      low24 of first cmds: %s' % ['%06x' % x for x in lo])
        # frame-data sanity: does ptrFrameData exist?
        fd = struct.unpack_from('<I', raw, hf + 0x24)[0]
        print('      ptrFrameData=0x%x anims=0x%x' % (fd, struct.unpack_from('<I', raw, hf + 0x38)[0]))


raw, mapset = load(514)
n = len(raw)
arr = u32(raw, 24)
nm = u32(raw, 20)
roots = [u32(raw, arr + k * 4) for k in range(nm)]
analyze(raw, mapset, roots, 'entry 514 (level-embedded ND-crate models)')

# pack entries: find one with a lookup head (entry 259 area)
for e in (259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276):
    off_s, size = big.entries[e]
    if size < 64:
        continue
    raw2 = iso.read(big.lba + off_s, size)
    mo, = struct.unpack_from('<i', raw2, 0)
    if mo < 0:
        continue
    nb, = struct.unpack_from('<i', raw2, 4 + mo)
    if nb <= 0 or (nb & 3) or (4 + mo + 4 + nb) > size:
        continue
    offs = set(struct.unpack_from('<%di' % (nb // 4), raw2, 4 + mo + 4))
    if 4 not in offs:
        continue
    # pack leading run
    roots2 = []
    off = 4
    while off in offs:
        t = u32(raw2, off)
        if t == 0 or (t % 4):
            break
        roots2.append(t)
        off += 4
    if len(roots2) >= 3:
        analyze(raw2, offs, roots2, 'entry %d pack (%d models)' % (e, len(roots2)))
        break
iso.close()
