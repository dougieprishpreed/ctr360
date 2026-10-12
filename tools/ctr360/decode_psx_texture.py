"""Decode a 4-bit PSX texture from the legacy PPC SaveVRAM dump.

The old Xbox dump has a TGA header but writes native big-endian PSX words.
It is not a normal TGA image. Decode indices and the selected CLUT explicitly.
"""
import argparse
from pathlib import Path
import struct
import zlib


def write_png(path, width, height, rgb):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--clut", type=int, required=True)
    parser.add_argument("--rect", type=int, nargs=4, required=True, metavar=("U", "V", "W", "H"))
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()
    data = args.dump.read_bytes()
    width, height = struct.unpack_from("<HH", data, 12)
    if (width, height, data[16]) != (1024, 512, 16):
        parser.error("requires a full legacy Xbox VRAM dump (1024x512, 16 bits)")
    def word(x, y):
        return struct.unpack_from(">H", data, 18 + 2 * ((height - 1 - y) * width + x))[0]
    px, py = (args.page & 15) * 64, (args.page >> 4) * 256
    cx, cy = (args.clut & 63) * 16, args.clut >> 6
    palette = [word(cx + i, cy) for i in range(16)]
    u, v, w, h = args.rect
    rgb = bytearray()
    for y in range(v, v + h):
        row = bytearray()
        for x in range(u, u + w):
            packed = word(px + (x >> 2), py + y)
            color = palette[(packed >> ((x & 3) * 4)) & 15]
            pixel = bytes(((color & 31) << 3, ((color >> 5) & 31) << 3, ((color >> 10) & 31) << 3))
            row.extend(pixel * args.scale)
        rgb.extend(row * args.scale)
    write_png(args.output, w * args.scale, h * args.scale, rgb)
    print("palette:", " ".join(f"{c:04x}" for c in palette))
    print(args.output)


if __name__ == "__main__":
    main()
