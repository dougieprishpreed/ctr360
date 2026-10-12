#!/usr/bin/env python3
"""ctr360 asset pipeline: ISO9660 (raw 2352, Mode2/Form1) + CTR BIGFILE.BIG reader.

Reads the user's own retail disc dump only. Never ships retail data.

Layout contract (matches platform/native_disc_image.c and namespace_Load.h):
  - 2352-byte raw sectors, Mode 2 Form 1, user data at offset 24 (2048 bytes)
  - PVD at LBA 16; root directory record at PVD offset 156 (extent LE32 @+2, size LE32 @+10)
  - BIGFILE.BIG: struct BigHeader { int cdpos; int numEntry; } (LE)
    followed by numEntry * struct BigEntry { int offset; int size; } (LE)
    (offset appears to be in 2048-byte data sectors, relative to BIGFILE start)
"""
import argparse
import struct
import sys
from dataclasses import dataclass
from typing import Iterator, Optional

SECTOR = 2352
DATA_OFF = 24
DATA_LEN = 2048


@dataclass
class IsoFile:
    name: str
    lba: int
    size: int
    is_dir: bool


class IsoImage:
    def __init__(self, path: str):
        self.path = path
        self.f = open(path, 'rb')
        pvd = self.data_sector(16)
        if pvd[1:6] != b'CD001':
            raise ValueError("not an ISO9660 PVD (532-byte raw BIN expected)")
        self.root_lba = struct.unpack_from('<I', pvd, 158)[0]
        self.root_size = struct.unpack_from('<I', pvd, 166)[0]
        self.volume_id = pvd[40:72].decode('ascii', 'replace').strip()

    def close(self):
        self.f.close()

    def data_sector(self, lba: int) -> bytes:
        self.f.seek(lba * SECTOR + DATA_OFF)
        return self.f.read(DATA_LEN)

    def read(self, lba: int, size: int) -> bytes:
        out = bytearray()
        for i in range((size + DATA_LEN - 1) // DATA_LEN):
            out += self.data_sector(lba + i)
        return bytes(out[:size])

    def iter_dir(self, lba: int, size: int) -> Iterator[IsoFile]:
        data = self.read(lba, size)
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = ((pos // DATA_LEN) + 1) * DATA_LEN
                continue
            rec = data[pos:pos + ln]
            ext = struct.unpack_from('<I', rec, 2)[0]
            sz = struct.unpack_from('<I', rec, 10)[0]
            flags = rec[25]
            namelen = rec[32]
            name = rec[33:33 + namelen].decode('ascii', 'replace')
            if name not in ('.', '..'):
                yield IsoFile(name, ext, sz, bool(flags & 2))
            pos += ln

    def find(self, path: str) -> Optional[IsoFile]:
        """Case-insensitive lookup; tolerates ';1' version suffix and backslashes."""
        parts = [p for p in path.replace('\\', '/').split('/') if p]
        lba, size = self.root_lba, self.root_size
        entry = None
        for part in parts:
            want = part.rsplit(';', 1)[0].upper()
            entry = next((e for e in self.iter_dir(lba, size)
                          if e.name.rsplit(';', 1)[0].upper() == want), None)
            if entry is None:
                return None
            lba, size = entry.lba, entry.size
        return entry


class BigFile:
    """View of BIGFILE.BIG's directory (retail-shaped, little-endian)."""

    def __init__(self, iso: IsoImage, name: str = 'BIGFILE.BIG'):
        e = iso.find(name)
        if e is None:
            raise FileNotFoundError(f"{name} not found in {iso.path}")
        self.iso = iso
        self.name = e.name
        self.lba = e.lba
        self.size = e.size
        hdr = iso.read(self.lba, 8)
        self.cdpos, self.num_entry = struct.unpack('<ii', hdr)
        raw = iso.read(self.lba, 8 + self.num_entry * 8)
        self.entries = [struct.unpack_from('<ii', raw, 8 + i * 8)
                        for i in range(self.num_entry)]

    def read_entry(self, index: int) -> bytes:
        off, size = self.entries[index]
        return self.iso.read(self.lba + off, size)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image', help="path to the user's CTR NTSC-U .bin dump")
    ap.add_argument('--find', metavar='PATH', action='append', default=[],
                    help="ISO path to locate (repeatable), e.g. --find SOUNDS/KART.HWL")
    ap.add_argument('--list-root', action='store_true')
    ap.add_argument('--dump-entries', type=int, metavar='N', default=0,
                    help="print first N BIGFILE entries")
    ap.add_argument('--entries-range', metavar='A:B', default=None,
                    help="print BIGFILE entries [A,B) (decimal or 0x hex)")
    args = ap.parse_args()

    iso = IsoImage(args.image)
    print(f"Volume ID: {iso.volume_id}")
    print(f"Root dir:  LBA {iso.root_lba}, {iso.root_size} bytes")

    if args.list_root:
        for e in iso.iter_dir(iso.root_lba, iso.root_size):
            kind = 'DIR' if e.is_dir else '   '
            print(f"  {kind} {e.name:14s} lba={e.lba:7d} size={e.size}")

    for p in args.find:
        e = iso.find(p)
        print(f"  find {p!r}: " + (f"lba={e.lba} size={e.size} dir={e.is_dir}" if e else "NOT FOUND"))

    big = None
    try:
        big = BigFile(iso)
    except FileNotFoundError as ex:
        print(ex)
        return 1

    print(f"\nBIGFILE.BIG: {big.name} lba={big.lba} size={big.size} "
          f"cdpos={big.cdpos} numEntry={big.num_entry}")

    def show(a: int, b: int):
        end = min(b, big.num_entry)
        for i in range(a, end):
            off, size = big.entries[i]
            print(f"  [{i:5d}] offset={off:8d} size={size:9d} "
                  f"(byte offset {off * DATA_LEN:10d})")

    if args.dump_entries:
        show(0, args.dump_entries)
    if args.entries_range:
        a, _, b = args.entries_range.partition(':')
        show(int(a, 0), int(b, 0) if b else big.num_entry)

    # sanity: last entry end within BIGFILE size
    last_off, last_size = max(big.entries, key=lambda t: t[0] * DATA_LEN + t[1])
    end_bytes = last_off * DATA_LEN + last_size
    print(f"last entry end: {end_bytes} bytes vs BIGFILE size {big.size} "
          f"({'OK' if end_bytes <= big.size else 'OVERRUN!'})")
    iso.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
