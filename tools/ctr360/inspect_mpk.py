"""Scratch: find MPK-shaped bigfile entries and inspect their pointer fields.

An MPK ("model pack") entry as the loader sees it starts with
    [int mpkIconsOffset][struct Model *modelList...]  (NULL-terminated)
and the models themselves hold absolute PSX RAM pointers (0x80xxxxxx).

If those 32-bit values are little-endian on disc, a big-endian reader gets
byte-swapped garbage - exactly what a wild-pointer walk looks like at runtime.
"""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage, BigFile

PRISTINE = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
SECTOR = 2048


def looks_like_psx_ptr(v):
    return 0x80000000 <= v <= 0x80200000


iso = IsoImage(PRISTINE)
big = BigFile(iso)
print('entries=%d' % big.num_entry)

hits = []
for idx in range(big.num_entry):
    off, size = big.entries[idx]
    if size < 16 or size > 0x400000:
        continue
    head = iso.read(big.lba + off, 32)
    if len(head) < 32:
        continue
    w = struct.unpack_from('<8I', head, 0)
    # candidate: word0 = small offset, words 1..7 are PSX pointers or 0
    ptrs = sum(1 for v in w[1:8] if looks_like_psx_ptr(v))
    if ptrs >= 4 and w[0] < 0x100000:
        hits.append((idx, size, w))

print('MPK-shaped candidates: %d' % len(hits))
for idx, size, w in hits[:12]:
    print('entry %3d size=%7d head=%s' % (idx, size, ' '.join('%08x' % v for v in w)))
for idx, size, w in hits[-8:]:
    print('entry %3d size=%7d head=%s' % (idx, size, ' '.join('%08x' % v for v in w)))

if hits:
    idx, size, w = hits[0]
    off, _ = big.entries[idx]
    raw = iso.read(big.lba + off, min(size, 4096))
    print('--- entry %d first model list (LE) ---' % idx)
    for i in range(1, 12):
        v, = struct.unpack_from('<I', raw, i * 4)
        print('   [%2d] %08x  (as BE the console reads %08x)' % (i, v, struct.unpack_from('>I', raw, i * 4)[0]))
    # dereference the first model pointer (LE) and show its first words
    m = struct.unpack_from('<I', raw, 4)[0]
    print('first model ptr (LE) = %08x' % m)
    if looks_like_psx_ptr(m):
        # file-internal offset unknown; just show what a model header would be
        print('   note: model data lives inside this entry; pointer is a PSX RAM address')
iso.close()
