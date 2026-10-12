"""Scratch: validate the HWL block layout (Region A tables + bank/song blocks).

Uses the same parsing rules as howl_ParseHeader / Bank_AssignSpuAddrs / howl_LoadSong
but reads everything as little-endian (the disc's on-disk order).
"""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage

IMG = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
HL = struct.calcsize('<i')
SECTOR = 2048

iso = IsoImage(IMG)
e = iso.find(r'SOUNDS\KART.HWL')
hwl_lba = e.lba
size = e.size
raw = iso.read(hwl_lba, 8192)

magic, version, unk1, unk2, numSpuAddrs, numOtherFX, numEngineFX, numBanks, numSequences, headerSize = struct.unpack_from('<10i', raw, 0)
print("numSpuAddrs=%d numOtherFX=%d numEngineFX=%d numBanks=%d numSequences=%d headerSize=%d" %
      (numSpuAddrs, numOtherFX, numEngineFX, numBanks, numSequences, headerSize))

off = 40
spu_off = off
off += 4 * numSpuAddrs
other_off = off
off += 8 * numOtherFX
engine_off = off
off += 8 * numEngineFX
banks_off = off
off += 2 * numBanks
songs_off = off
off += 2 * numSequences
print("computed tables end = %d (headerSize+40 = %d)" % (off, headerSize + 40))

# Need the tail of the tables: read the whole header region.
hdr = iso.read(hwl_lba, headerSize + 40)
bank_offsets = struct.unpack_from('<%dH' % numBanks, hdr, banks_off)
song_offsets = struct.unpack_from('<%dH' % numSequences, hdr, songs_off)
print("bankOffsets[0:8] =", bank_offsets[:8])
print("songOffsets[0:8] =", song_offsets[:8])
print("bankOffsets[33] = %d  songOffsets[28] = %d" % (bank_offsets[33], song_offsets[28]))

# --- bank block (Region B) ---
bsec = bank_offsets[33]
blk = iso.read(hwl_lba + bsec, 0x800)
numSamples = struct.unpack_from('<h', blk, 0)[0]
print("\nbank 33 @ sector %d: numSamples=%d" % (bsec, numSamples))
if 0 < numSamples < 4096:
    idx = struct.unpack_from('<%dh' % min(numSamples, 16), blk, 2)
    print("  first indices:", idx)
    maxidx = max(struct.unpack_from('<%dh' % numSamples, blk, 2))
    print("  max index (must be < numSpuAddrs=%d): %d" % (numSpuAddrs, maxidx))

# --- song block (Region C) ---
ssec = song_offsets[28]
sblk = iso.read(hwl_lba + ssec, 0x800)
songSize, = struct.unpack_from('<i', sblk, 0)
nlong = sblk[4]
nshort = sblk[5]
nsongs, = struct.unpack_from('<H', sblk, 6)
print("\nsong 28 @ sector %d: songSize=%d numLongSamples=%d numShortSamples=%d numSongs=%d" %
      (ssec, songSize, nlong, nshort, nsongs))
print("  sectors needed for song data: %d (file has %d sectors)" % ((songSize + 2047) // 2048, size // 2048))
print("  first SampleInstrument words:", sblk[8:32].hex(' '))
iso.close()
