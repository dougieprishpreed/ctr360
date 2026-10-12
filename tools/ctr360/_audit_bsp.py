"""Read-only audit helper (scratch, deletable): precise BSP/leaf decode + ptrFrameData census
+ VisMem body coverage, for the draw-path matrix."""
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


def hx(x):
    return x.hex()


# ---------- (a) BSP decode, entry 41
e = 41
ra = rd(a, alba, ae, e)
rb = rd(b, blba, be, e)
mo, = struct.unpack_from('<i', ra, 0)
nb, = struct.unpack_from('<i', ra, 4 + mo)
mp = set(struct.unpack_from('<%di' % (nb // 4), ra, 4 + mo + 4))
mesh = u32f(ra, 0)
bsp = u32f(ra, mesh + 0x18)
num_bsp = struct.unpack_from('<i', ra, 4 + mesh + 0x1C)[0]
print('=== entry 41: bspRoot frame 0x%x numBspNodes=%d covered=%s' % (bsp, num_bsp, (mesh + 0x18) in mp))
for k in (0, 1, 2):
    off = bsp + k * 0x20
    fo = 4 + off
    flag = struct.unpack_from('<H', ra, fo)[0]
    bid = struct.unpack_from('<h', ra, fo + 2)[0]
    box = struct.unpack_from('<6h', ra, fo + 4)
    print(' BSP[%d] frame 0x%x flag=0x%x id=%d box=%s' % (k, off, flag, bid, box))
    print('   raw file bytes  = %s' % hx(ra[fo:fo + 0x20]))
    print('   cooked file bytes= %s' % hx(rb[fo:fo + 0x20]))
    if flag & 1:
        unk1 = struct.unpack_from('<i', ra, fo + 0x10)[0]
        hit = struct.unpack_from('<I', ra, fo + 0x14)[0]
        nq = struct.unpack_from('<i', ra, fo + 0x18)[0]
        pqb = struct.unpack_from('<I', ra, fo + 0x1c)[0]
        print('   LEAF: unk1=%d hitboxArr=0x%x numQuads=%d ptrQuadBlockArray=0x%x' % (unk1, hit, nq, pqb))
        print('         cov: unk1=%s hitbox=%s numQuads=%s ptrQB=%s' % (
            (off + 0x10) in mp, (off + 0x14) in mp, (off + 0x18) in mp, (off + 0x1c) in mp))
        print('         numQuads retail bytes=%s cooked bytes=%s ; BE-read=%d' % (
            hx(ra[fo + 0x18:fo + 0x1c]), hx(rb[fo + 0x18:fo + 0x1c]), struct.unpack_from('>i', ra, fo + 0x18)[0]))
        print('         ptrQB retail=%s cooked=%s' % (hx(ra[fo + 0x1c:fo + 0x20]), hx(rb[fo + 0x1c:fo + 0x20])))
    else:
        axis = struct.unpack_from('<4h', ra, fo + 0x10)
        child = struct.unpack_from('<4H', ra, fo + 0x18)
        print('   BRANCH: axis=%s childID=%s' % (axis, child))
        print('         cov: axis words=%s childID words=%s' % (
            [(off + 0x10 + i * 2) in mp for i in range(4)], [(off + 0x18 + i * 2) in mp for i in range(4)]))
        print('         axis retail=%s cooked=%s' % (hx(ra[fo + 0x10:fo + 0x18]), hx(rb[fo + 0x10:fo + 0x18])))
        print('         childID retail=%s cooked=%s' % (hx(ra[fo + 0x18:fo + 0x20]), hx(rb[fo + 0x18:fo + 0x20])))
# find first leaf
for k in range(num_bsp):
    off = bsp + k * 0x20
    fo = 4 + off
    if struct.unpack_from('<H', ra, fo)[0] & 1:
        print(' first LEAF is BSP[%d]' % k)
        break

# ---------- (b) VisMem body coverage (Level + 0x190)
vis = u32f(ra, 0x190)
print('=== entry 41: Level.visMem frame 0x%x covered=%s' % (vis, 0x190 in mp))
if vis:
    vf = 4 + vis
    names = ['visLeafList[0..3]', 'visFaceList[0..3]', 'visOVertList[0..3]', 'visSCVertList[0..3]',
             'visLeafSrc[0..3]', 'visFaceSrc[0..3]', 'visOVertSrc[0..3]', 'visSCVertSrc[0..3]', 'bspList[0..3]']
    for i, nm in enumerate(names):
        base = i * 0x10
        cov = [(vis + base + j * 4) in mp for j in range(4)]
        vals = ['%08x' % struct.unpack_from('<I', ra, vf + base + j * 4)[0] for j in range(4)]
        cookd = ['%08x' % struct.unpack_from('<I', rb, vf + base + j * 4)[0] for j in range(4)]
        print('  %-16s cov=%s retail=%s cooked=%s' % (nm, cov, vals, cookd))

# ---------- (c) ptrFrameData census across all entries
print('=== ptrFrameData census (models with non-null ptrFrameData)')
tot = nonnull = 0
examples = []
for e2 in range(len(ae)):
    off_s, size = ae[e2]
    if size < 0x800:
        continue
    ra2 = rd(a, alba, ae, e2)
    mo2, = struct.unpack_from('<i', ra2, 0)
    if mo2 < 0 or (4 + mo2 + 8) > size:
        continue
    nb2, = struct.unpack_from('<i', ra2, 4 + mo2)
    if nb2 <= 0 or (nb2 & 3) or (4 + mo2 + 4 + nb2) > size:
        continue
    mp2 = set(struct.unpack_from('<%di' % (nb2 // 4), ra2, 4 + mo2 + 4))
    if all(f in mp2 for f in (0, 4, 8, 16, 24)):
        arr = u32f(ra2, 24)
        nmm = u32f(ra2, 20)
        roots = [u32f(ra2, arr + kk * 4) for kk in range(nmm)]
    elif 4 in mp2:
        roots = []
        off = 4
        while off in mp2:
            t = u32f(ra2, off)
            if t == 0 or (t % 4) or (4 + t + 0x40) > size:
                break
            roots.append(t)
            off += 4
    else:
        continue
    for r in roots:
        if (4 + r + 0x40) > size:
            continue
        nh = struct.unpack_from('<h', ra2, 4 + r + 0x12)[0]
        hrel = u32f(ra2, r + 0x14)
        if not (1 <= nh <= 8) or hrel == 0:
            continue
        for hh in range(nh):
            hf = 4 + hrel + hh * 0x40
            if (hf + 0x40) > size:
                continue
            tot += 1
            fd = struct.unpack_from('<I', ra2, hf + 0x24)[0]
            if fd:
                nonnull += 1
                if len(examples) < 6:
                    nm = ra2[hf:hf + 16].split(b'\0')[0].decode('latin1')
                    examples.append((e2, nm, fd, hx(ra2[4 + fd:4 + fd + 0x1c])))
print('  headers scanned=%d with ptrFrameData=%d' % (tot, nonnull))
for x in examples:
    print('   entry %d %-16s ptrFrameData frame 0x%x bytes=%s' % x)
a.close(); b.close()
