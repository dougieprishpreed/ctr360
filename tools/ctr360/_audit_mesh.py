"""Read-only audit helper (scratch, deletable): map-coverage of mesh/BSP/quadblock/
PVS/vertex pointer words + value-domain checks for a real track (41) and the ND crate (514)."""
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


for e in (41, 514):
    raw, mp = load(e)
    n = len(raw)
    print('==== entry %d size=%d mapwords=%d' % (e, n, len(mp)))
    mesh_rel = u32(raw, 0)
    m = mesh_rel
    print('  mesh_info frame 0x%x; pointer words map-covered:' % m)
    for name, f in (('ptrQuadBlockArray', 0xC), ('ptrVertexArray', 0x10), ('bspRoot', 0x18)):
        print('     %-20s frame 0x%x covered=%s value=0x%x' % (name, m + f, (m + f) in mp, u32(raw, m + f)))
    print('  Level ptr fields covered: ptrInstDefs(0x10)=%s ptrModelsPtrArray(0x18)=%s visOVertSrc(0x28)=%s '
          'ptr_water(0x38)=%s levTexLookup(0x3c)=%s ptr_tex_waterEnvMap(0x44)=%s visMem(0x190)=%s ptrSCVert(0x178)=%s' % (
              (0x10 in mp), (0x18 in mp), (0x28 in mp), (0x38 in mp), (0x3c in mp), (0x44 in mp), (0x190 in mp), (0x178 in mp)))
    print('  Level scalar words covered: numInstances(0xc)=%s numModels(0x14)=%s numWaterVertices(0x34)=%s numSCVert(0x174)=%s '
          'clearColorRGBA(0xd8)=%s configFlags(0xdc)=%s numSpawnType2(0x138)=%s cnt_restart_points(0x148)=%s' % (
              (0xc in mp), (0x14 in mp), (0x34 in mp), (0x174 in mp), (0xd8 in mp), (0xdc in mp), (0x138 in mp), (0x148 in mp)))
    bsp = u32(raw, m + 0x18)
    if bsp:
        print('  BSP[0] at frame 0x%x: words %s' % (bsp, ' '.join('%08x' % struct.unpack_from('<I', raw, 4 + bsp + i * 4)[0] for i in range(8))))
        flag = struct.unpack_from('<H', raw, 4 + bsp)[0]
        print('     flag=0x%x leaf=%d ; childID words covered: %s' % (
            flag, flag & 1, [(0x18 + i * 2 + bsp) in mp for i in range(4)]))
    qb = u32(raw, m + 0xC)
    if qb:
        qf = 4 + qb
        print('  QuadBlock[0] at file 0x%x index[9]=%s' % (qf, struct.unpack_from('<9H', raw, qf)))
        print('     draw_order_low=%08x draw_order_high=%08x quadFlags=%04x blockID=%d' % (
            struct.unpack_from('<I', raw, qf + 0x14)[0], struct.unpack_from('<I', raw, qf + 0x18)[0],
            struct.unpack_from('<H', raw, qf + 0x12)[0], struct.unpack_from('<h', raw, qf + 0x3c)[0]))
        print('     ptr_texture_mid covered=%s values=%s ; ptr_texture_low covered=%s ; pvs covered=%s value=0x%x' % (
            [(qb + 0x1c + i * 4) in mp for i in range(4)],
            ['%08x' % struct.unpack_from('<I', raw, qf + 0x1c + i * 4)[0] for i in range(4)],
            (qb + 0x40) in mp, (qb + 0x44) in mp, struct.unpack_from('<I', raw, qf + 0x44)[0]))
    va = u32(raw, m + 0x10)
    if va:
        vf = 4 + va
        pos = struct.unpack_from('<3h', raw, vf)
        print('  LevVertex[0] at file 0x%x: %s  pos=(%d,%d,%d) flags=0x%x color_hi=%s' % (
            vf, raw[vf:vf + 16].hex(), pos[0], pos[1], pos[2], struct.unpack_from('<H', raw, vf + 6)[0], raw[vf + 8:vf + 12].hex()))
        print('     raw u32 at pos = %08x ; LE-byte-wise = %08x ; map covered(+0)=%s' % (
            struct.unpack_from('>I', raw, vf)[0], struct.unpack_from('<I', raw, vf)[0], (va) in mp))
    # delta array of the first model (entry 514)
    if e == 514:
        arr = u32(raw, 24)
        r0 = u32(raw, arr)
        hf = 4 + u32(raw, r0 + 0x14)
        pa = struct.unpack_from('<I', raw, hf + 0x38)[0]
        a0 = u32(raw, pa)
        da = u32(raw, a0 + 0x14)
        print('  model0 anim0 ptrDeltaArray=0x%x covered=%s first words: %s' % (
            da, (a0 + 0x14) in mp, ' '.join('%08x' % struct.unpack_from('<I', raw, 4 + da + i * 4)[0] for i in range(6))))
        print('     as LE bitfields: xBits/zBits/yBits of first 3: %s' % [
            ((w >> 6) & 7, (w >> 3) & 7, w & 7) for w in struct.unpack_from('<3I', raw, 4 + da)])
        nf = struct.unpack_from('<H', raw, 4 + a0 + 0x10)[0]
        fs = struct.unpack_from('<h', raw, 4 + a0 + 0x12)[0]
        print('     ModelAnim numFrames(LE)=%d frameSize(LE)=%d -> raw BE numFrames=%d frameSize=%d' % (
            nf, fs, struct.unpack_from('>H', raw, 4 + a0 + 0x10)[0], struct.unpack_from('>h', raw, 4 + a0 + 0x12)[0]))
        # first ModelFrame of the anim
        fr = 4 + a0 + 0x18
        print('     first ModelFrame at file 0x%x: %s pos=(%d,%d,%d) vertexOffset(LE)=%d' % (
            fr, raw[fr:fr + 0x1c].hex(), struct.unpack_from('<3h', raw, fr),
            struct.unpack_from('<i', raw, fr + 0x18)[0]))
iso.close()
