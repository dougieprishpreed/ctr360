#!/usr/bin/env python3
"""Convert a PSX VRAM TGA dump (16bpp BGR555) to PNG.

The 360 build writes `NativeRenderer_SaveVRAM` TGAs with host-order u16 pixels
(big-endian bytes on Xenon), rows bottom-up (TGA default). This converts without
modifying the source and prints the output path plus a checksum of the decoded
pixels, so the run harness can compare captures.

Usage:
    python tools/ctr360/tga_to_png.py <in.tga> [out.png] [--le] [--rgb555]
"""

import hashlib
import os
import struct
import sys

from PIL import Image


def read_tga(path, little_endian):
    with open(path, 'rb') as f:
        data = f.read()

    if len(data) < 18:
        raise SystemExit('tga: too short: %s' % path)

    id_len, cmap_type, image_type = data[0], data[1], data[2]
    width, height = struct.unpack_from('<HH', data, 12)
    bpp = data[16]
    descriptor = data[17]

    if image_type != 2:
        raise SystemExit('tga: unsupported image type %d (need uncompressed true-color)' % image_type)
    if bpp != 16:
        raise SystemExit('tga: unsupported bpp %d (need 16)' % bpp)

    offset = 18 + id_len
    need = width * height * 2
    if len(data) < offset + need:
        raise SystemExit('tga: pixel data truncated (%d < %d)' % (len(data) - offset, need))

    pixels = []
    order = 'little' if little_endian else 'big'
    for i in range(width * height):
        v = struct.unpack_from('<' + 'H' if little_endian else '>H', data, offset + i * 2)[0]
        pixels.append(v)
    return width, height, pixels, descriptor


def vram555_to_rgb(v, rgb555=False):
    if rgb555:
        r5, g5, b5 = v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F
    else:  # BGR555 (PSX VRAM layout)
        b5, g5, r5 = v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F
    return ((r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    if not args:
        raise SystemExit(__doc__)

    src = args[0]
    dst = args[1] if len(args) > 1 else os.path.splitext(src)[0] + '.png'
    little_endian = '--le' in flags
    rgb555 = '--rgb555' in flags

    width, height, pixels, descriptor = read_tga(src, little_endian)
    rgb = [vram555_to_rgb(v, rgb555) for v in pixels]
    img = Image.new('RGB', (width, height))
    img.putdata(rgb)
    if not (descriptor & 0x20):  # bottom-up source -> flip to top-down
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    img.save(dst)

    checksum = hashlib.md5(bytes(bytearray([c for px in rgb for c in px]))).hexdigest()[:16]
    print('%s -> %s  %dx%d  pixelsum=%s' % (src, dst, width, height, checksum))
    return 0


if __name__ == '__main__':
    sys.exit(main())
