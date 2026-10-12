"""Read-only audit helper (scratch, deletable): compare retail vs cooked bytes for
the draw-path structures (level 514 + track 41). Proves cook coverage empirically."""
import struct, sys
sys.path.insert(0, '.')
from iso_bigfile import IsoImage, BigFile

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


a, alba, aents = open_big(RETAIL, True)
b, blba, bents = open_big(COOKED, False)
print('retail entries=%d cooked entries=%d  (cooked dir is big-endian)' % (len(aents), len(bents)))


def rd(iso, lba, ents, e):
    off_s, size = ents[e]
    return iso.read(lba + off_s, size)


def u32f(raw, f):
    return struct.unpack_from('<I', raw, 4 + f)[0]


def diff(raw_a, raw_b, file_off, size):
    return raw_a[file_off:file_off + size] != raw_b[file_off:file_off + size]


def hexs(b):
    return b.hex()


def report(e, fields, label):
    ra = rd(a, alba, aents, e); rb = rd(b, blba, bents, e)
    print('==== entry %d %s size retail=%d cooked=%d' % (e, label, len(ra), len(rb)))
    if len(ra) != len(rb):
        print('   SIZE MISMATCH')
        return
    for name, off, size in fields:
        da = diff(ra, rb, off, size)
        print('   %-42s file+0x%-7x %2dB  cooked=%-5s retail=%s cooked=%s' % (
            name, off, size, da, hexs(ra[off:off + size]), hexs(rb[off:off + size])))
    return ra, rb


# ---- entry 514: level-embedded models
ra, rb = report(514, [], 'ND crate level')
mesh = u32f(ra, 0)
print('   mesh_info: numQB=%d numV=%d ptrQB=0x%x ptrV=0x%x bspRoot=0x%x numBsp=%d' % (
    struct.unpack_from('<i', ra, 4 + mesh + 0)[0], struct.unpack_from('<i', ra, 4 + mesh + 4)[0],
    u32f(ra, mesh + 0xC), u32f(ra, mesh + 0x10), u32f(ra, mesh + 0x18), u32f(ra, mesh + 0x1C)))
for f, nm in ((0, 'mesh ptr_mesh_info'), (0xC, 'mesh numQuadBlock'), (0x10, 'mesh numVertex'),
              (0xC + 0xC, 'mesh ptrQuadBlockArray'), (0xC + 0x10, 'mesh ptrVertexArray'),
              (0xC + 0x18, 'mesh bspRoot'), (0xC + 0x1C, 'mesh numBspNodes')):
    print('   mesh frame 0x%02x %-24s retail=%s cooked=%s' % (f, nm, hexs(ra[4 + mesh + f:4 + mesh + f + 4]), hexs(rb[4 + mesh + f:4 + mesh + f + 4])))

arr = u32f(ra, 24)
r0 = u32f(ra, arr)
mf = 4 + r0
hrel = u32f(ra, r0 + 0x14)
hf = 4 + hrel
print('   model0 %r' % ra[mf:mf + 16].split(b'\0')[0])
for f, nm, sz in ((0x10, 'Model.id', 2), (0x12, 'Model.numHeaders', 2), (0x14, 'Model.headers ptr', 4),
                  (0x10, 'MH.unk1', 4), (0x14, 'MH.maxDistanceLOD', 2), (0x16, 'MH.flags', 2),
                  (0x18, 'MH.scale.x', 2), (0x1A, 'MH.scale.y', 2), (0x1C, 'MH.scale.z', 2),
                  (0x20, 'MH.ptrCommandList', 4), (0x24, 'MH.ptrFrameData', 4), (0x28, 'MH.ptrTexLayout', 4),
                  (0x2C, 'MH.ptrColors', 4), (0x30, 'MH.unk3', 4), (0x34, 'MH.numAnimations', 4),
                  (0x38, 'MH.ptrAnimations', 4), (0x3C, 'MH.animtex', 4)):
    base = mf if nm.startswith('Model.') else hf
    print('   %-24s file+0x%02x  retail=%s cooked=%s' % (nm, base + f, hexs(ra[base + f:base + f + sz]), hexs(rb[base + f:base + f + sz])))

# ModelAnim of model0
pa = u32f(ra, hrel + 0x38)
a0 = u32f(ra, pa)
print('   ModelAnim[0] @frame 0x%x' % a0)
for f, nm, sz in ((0x10, 'MA.numFrames(u16)', 2), (0x12, 'MA.frameSize(s16)', 2), (0x14, 'MA.ptrDeltaArray', 4)):
    print('   %-24s file+0x%02x  retail=%s cooked=%s' % (nm, 4 + a0 + f, hexs(ra[4 + a0 + f:4 + a0 + f + sz]), hexs(rb[4 + a0 + f:4 + a0 + f + sz])))
# first ModelFrame
fr = 4 + a0 + 0x18
for f, nm, sz in ((0x0, 'MF.pos.x', 2), (0x2, 'MF.pos.y', 2), (0x4, 'MF.pos.z', 2), (0x18, 'MF.vertexOffset', 4)):
    print('   %-24s file+0x%02x  retail=%s cooked=%s' % (nm, fr + f, hexs(ra[fr + f:fr + f + sz]), hexs(rb[fr + f:fr + f + sz])))
# command list of model0
cl = u32f(ra, hrel + 0x20)
print('   cmdlist frame 0x%x: retail %s' % (cl, hexs(ra[4 + cl:4 + cl + 40])))
print('                        cooked %s' % hexs(rb[4 + cl:4 + cl + 40]))
# texLayout + colors
px = u32f(ra, hrel + 0x28); tl0 = u32f(ra, px)
print('   texLayout[0] frame 0x%x retail=%s cooked=%s' % (tl0, hexs(ra[4 + tl0:4 + tl0 + 12]), hexs(rb[4 + tl0:4 + tl0 + 12])))
pc = u32f(ra, hrel + 0x2C)
print('   ptrColors frame 0x%x retail=%s cooked=%s' % (pc, hexs(ra[4 + pc:4 + pc + 16]), hexs(rb[4 + pc:4 + pc + 16])))
# delta array
da = u32f(ra, a0 + 0x14)
print('   deltaArray frame 0x%x retail=%s cooked=%s' % (da, hexs(ra[4 + da:4 + da + 16]), hexs(rb[4 + da:4 + da + 16])))

# ---- entry 41: real track
ra, rb = report(41, [], 'Tiger Temple-ish track')
mesh = u32f(ra, 0)
print('   mesh_info: numQB=%d numV=%d ptrQB=0x%x ptrV=0x%x bspRoot=0x%x numBsp=%d' % (
    struct.unpack_from('<i', ra, 4 + mesh + 0)[0], struct.unpack_from('<i', ra, 4 + mesh + 4)[0],
    u32f(ra, mesh + 0xC), u32f(ra, mesh + 0x10), u32f(ra, mesh + 0x18), u32f(ra, mesh + 0x1C)))
for f, nm, sz in ((0, 'mesh ptr_mesh_info', 4), (4, 'mesh numQuadBlock', 4), (8, 'mesh numVertex', 4),
                  (0x10, 'mesh ptrQuadBlockArray', 4), (0x14, 'mesh ptrVertexArray', 4),
                  (0x1C, 'mesh bspRoot', 4), (0x20, 'mesh numBspNodes', 4)):
    print('   %-26s file+0x%02x retail=%s cooked=%s' % (nm, 4 + mesh + f, hexs(ra[4 + mesh + f:4 + mesh + f + sz]), hexs(rb[4 + mesh + f:4 + mesh + f + sz])))
qb = u32f(ra, mesh + 0xC)
qf = 4 + qb
print('   QuadBlock[0] index[0..8] file+0x%x retail=%s cooked=%s' % (qf, hexs(ra[qf:qf + 18]), hexs(rb[qf:qf + 18])))
for f, nm, sz in ((0x12, 'QB.quadFlags', 2), (0x14, 'QB.draw_order_low', 4), (0x18, 'QB.draw_order_high', 4),
                  (0x1C, 'QB.ptr_texture_mid[0]', 4), (0x2C, 'QB.bbox.min.x', 2), (0x38, 'QB.terrain_type', 1),
                  (0x3C, 'QB.blockID', 2), (0x40, 'QB.ptr_texture_low', 4), (0x44, 'QB.pvs', 4),
                  (0x48, 'QB.triNormalVecDividend[0]', 2)):
    print('   %-26s file+0x%02x retail=%s cooked=%s' % (nm, qf + f, hexs(ra[qf + f:qf + f + sz]), hexs(rb[qf + f:qf + f + sz])))
va = u32f(ra, mesh + 0x10)
vf = 4 + va
print('   LevVertex[0] file+0x%x retail=%s cooked=%s' % (vf, hexs(ra[vf:vf + 16]), hexs(rb[vf:vf + 16])))
bsp = u32f(ra, mesh + 0x18)
bf = 4 + bsp
print('   BSP[0] file+0x%x retail=%s' % (bf, hexs(ra[bf:bf + 0x20])))
print('                cooked=%s' % hexs(rb[bf:bf + 0x20]))
print('   BSP[1] file+0x%x retail=%s' % (bf + 0x20, hexs(ra[bf + 0x20:bf + 0x40])))
print('                cooked=%s' % hexs(rb[bf + 0x20:bf + 0x40]))
# find a leaf node
for k in range(24):
    off = bf + k * 0x20
    flag = struct.unpack_from('<H', ra, off)[0]
    if flag & 1:
        print('   BSP leaf[%d] file+0x%x retail=%s' % (k, off, hexs(ra[off:off + 0x20])))
        print('                          cooked=%s' % hexs(rb[off:off + 0x20]))
        break
# PVS of a quadblock that has one
for k in range(200):
    off = qf + k * 0x5c
    pv = struct.unpack_from('<I', ra, off + 0x44)[0]
    if pv:
        pvf = 4 + pv
        print('   QB[%d].pvs frame 0x%x covered-retail: visLeafSrc=%s visFaceSrc=%s visInstSrc=%s visExtraSrc=%s' % (
            k, pv, hexs(ra[pvf:pvf + 4]), hexs(ra[pvf + 4:pvf + 8]), hexs(ra[pvf + 8:pvf + 12]), hexs(ra[pvf + 12:pvf + 16])))
        print('        cooked: %s' % hexs(rb[pvf:pvf + 16]))
        break
a.close(); b.close()
