"""Scratch: decode .vrm pixel data (u16) from pristine vs cooked image.

Confirms/denies the hypothesis that 16-bit pixel VALUES in these files are
little-endian and must be byte-swapped like every other u16 the game reads.
Prints a histogram (top values) and a coarse brightness map, decoding the
pristine pixels as LE (the PSX's own order) and the cooked pixels as BE (what
the Xenon sees today).
"""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage, BigFile

PRISTINE = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
COOKED = r'F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\ctr-u-360.bin'
HDR = 0x14
RECT = 0xC


def rect_of(buf, off):
    return struct.unpack_from('<4h', buf, off + RECT)


def chunks_of(buf):
    """Yield (vh_off, x, y, w, h, pix_off, pix_bytes) as the game's loader sees
    them, decoding with the given byte order (pristine: '<')."""
    first, = struct.unpack_from('<I', buf, 0)
    if first != 0x20:
        x, y, w, h = rect_of(buf, 0)
        yield (0, x, y, w, h, HDR, w * h * 2)
        return
    off = 4
    while True:
        size, = struct.unpack_from('<I', buf, off)
        off += 4
        if size == 0:
            return
        x, y, w, h = rect_of(buf, off)
        yield (off, x, y, w, h, off + HDR, w * h * 2)
        off += size


def report(tag, buf, order):
    print('--- %s (pixels decoded %s) ---' % (tag, order))
    for (vh, x, y, w, h, poff, nbytes) in chunks_of(buf):
        vals = struct.unpack_from('<%dH' % (w * h), buf, poff) if order == 'LE' else struct.unpack_from('>%dH' % (w * h), buf, poff)
        hist = {}
        for v in vals:
            hist[v] = hist.get(v, 0) + 1
        top = sorted(hist.items(), key=lambda kv: -kv[1])[:6]
        print('rect %d,%d %dx%d  top=%s' % (x, y, w, h, ['%04x:%d' % (v, c) for v, c in top]))
        # coarse brightness map: sample a grid, show 1 char per cell
        cols, rows = 48, 16
        for ry in range(rows):
            line = []
            for rx in range(cols):
                px = int((rx + 0.5) * w / cols)
                py = int((ry + 0.5) * h / rows)
                v = vals[py * w + px]
                r = v & 0x1F
                g = (v >> 5) & 0x1F
                b = (v >> 10) & 0x1F
                lum = (r * 3 + g * 6 + b) // 10
                line.append(' .:-=+*#%@'[min(9, lum * 10 // 32)])
            print('    |' + ''.join(line) + '|')
        break  # first chunk only, keep the output readable


iso_a = IsoImage(PRISTINE)
big = BigFile(iso_a)
iso_b = IsoImage(COOKED)

for idx in (509, 510):
    off, size = big.entries[idx]
    a = iso_a.read(big.lba + off, size)
    b = iso_b.read(big.lba + off, size)
    report('entry %d pristine' % idx, a, 'LE')
    report('entry %d cooked as-read-for-BE-console' % idx, b, 'BE')
    print('    pristine bytes[0x14:0x1C] = %s' % a[0x14:0x1C].hex())
    print('    cooked   bytes[0x14:0x1C] = %s' % b[0x14:0x1C].hex())
iso_a.close()
iso_b.close()
