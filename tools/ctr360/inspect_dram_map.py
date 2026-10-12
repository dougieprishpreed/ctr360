"""Scratch: parse the DRAM pointer map of a bigfile entry and check it names the
pointer-shaped words (the map is what LOAD_RunPtrMap patches with +base).

Usage: python inspect_dram_map.py [entry_index ...]
"""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage, BigFile

ISO = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
iso = IsoImage(ISO)
big = BigFile(iso)


def parse(idx):
    off, size = big.entries[idx]
    if size < 16:
        return None
    raw = iso.read(big.lba + off, size)
    if len(raw) < size:
        return None
    map_off, = struct.unpack_from('<i', raw, 0)
    if map_off < 0 or (map_off + 8) > size:
        return None
    num_bytes, = struct.unpack_from('<i', raw, 4 + map_off)
    if num_bytes <= 0 or (num_bytes & 3) or (map_off + 8 + num_bytes) > size:
        return None
    n = num_bytes >> 2
    offs = struct.unpack_from('<%di' % n, raw, 4 + map_off + 4)
    return raw, size, map_off, num_bytes, offs


for idx in [int(a) for a in sys.argv[1:]] or [276, 277, 291]:
    r = parse(idx)
    if r is None:
        print('entry %d: no plausible pointer map' % idx)
        continue
    raw, size, map_off, num_bytes, offs = r
    print('entry %d size=%d map@%d numBytes=%d (%d ptr words)' % (idx, size, map_off, num_bytes, len(offs)))
    print('   first 12 ptr offsets: %s' % (list(offs[:12]),))
    bad = [o for o in offs if o < 4 or (o + 4) > size or (o & 3)]
    print('   out-of-range/unaligned offsets: %d %s' % (len(bad), bad[:6]))
    print('   values at those offsets (LE):')
    for o in list(offs[:10]):
        v, = struct.unpack_from('<I', raw, o)
        print('      +0x%04x = %08x  (relative? %s)  next-word=%08x' % (o, v, 'yes' if v < size else 'NO', struct.unpack_from('<I', raw, o + 4)[0] if o + 8 <= size else 0))
    # word 1 (mpkIcons) should be listed too
    print('   is offset 4 (word1) listed: %s ; map_off listed: %s' % (4 in offs, (4 + map_off) in offs))
iso.close()
