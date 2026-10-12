"""Scratch: inspect KART.HWL's raw header on the user's pristine dump.

Prints the HowlHeader fields as little-endian (disc) values and as they would be
read on the big-endian console, plus the pointer tables the game walks.
"""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage

IMG = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'

MASK32 = 0xFFFFFFFF

iso = IsoImage(IMG)
e = iso.find(r'SOUNDS\KART.HWL')
print("KART.HWL: name=%r lba=%d size=%d bytes (%d sectors)" % (e.name, e.lba, e.size, (e.size + 2047) // 2048))

raw = iso.read(e.lba, min(e.size, 8192))
print("first 16 bytes:", raw[:16].hex(' '))
print("magic bytes [0:4] =", raw[0:4])

names = ['magic', 'version', 'unk1', 'unk2', 'numSpuAddrs', 'numOtherFX', 'numEngineFX', 'numBanks', 'numSequences', 'headerSize']
for i, nm in enumerate(names):
    le = struct.unpack_from('<i', raw, i * 4)[0]
    beread = struct.unpack_from('>i', raw, i * 4)[0]
    print("  off %02x %-12s LE=%-14d (0x%08x)   BE-read=0x%08x = %d" % (i * 4, nm, le, le & MASK32, beread & MASK32, beread))

numSpuAddrs, numOtherFX, numEngineFX, numBanks, numSequences, headerSize = struct.unpack_from('<6i', raw, 16)
print("headerSize=%d  numSpuAddrs=%d numOtherFX=%d numEngineFX=%d numBanks=%d numSequences=%d"
      % (headerSize, numSpuAddrs, numOtherFX, numEngineFX, numBanks, numSequences))

# Walk the tables with LE offsets, exactly like howl_ParseHeader does.
off = 40  # sizeof(HowlHeader)
spu = struct.unpack_from('<%dH' % (2 * numSpuAddrs), raw, off)
off += 4 * numSpuAddrs
print("first SpuAddrEntry pairs (spuAddr, spuSize) LE:", list(zip(spu[0:12:2], spu[1:12:2])))

# OtherFX / EngineFX sizes unknown here; just show raw words at the post-spu-addr offset
print("bytes after spuAddrs table [0:32]:", raw[off:off + 32].hex(' '))

iso.close()
