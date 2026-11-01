"""Record the disc cooker's byte swaps as a recipe the console replays.

Cooking (tools/ctr360/cook_disc.py) leaves the image's length and every byte in
place but the numeric fields it reverses, and each reversal is its own inverse.
Every good dump of the USA disc (SCUS-94426) holds the same bytes, so the
fields sit at the same places on every one: this records them once, in the
disc's 2048-byte data coordinates, and checks that replaying them on the dump
gives exactly the image the PC converter makes (--expect, its SHA-256). The
recipe holds positions and sizes only, nothing of the game.

The console (platform/xsdk/native_xsdk_disc_cook.c) copies the player's .bin
through the recipe and accepts the copy only when its CRC-32, which the recipe
carries, matches; any other dump fails that check and is left alone.

Recipe format, little-endian:
    char magic[4] = "CTRC"; u32 version = 1;
    u32 image_bytes; u32 output_crc32; u32 runs; then instructions to the end:
    varint gap; u8 kind;
        kind 2 or 4: varint count - a run
        kind 0:      varint k; varint times; k x { varint gap; u8 kind; varint count }
                     - those k runs, times over
A run reverses count consecutive elements of kind bytes, starting gap bytes
after the previous run's end (data coordinates, the disc's 2048-byte sectors
end to end; the first from 0). A repeat's first run starts the instruction's
gap after the previous end, and every later one its own gap: level meshes
repeat one field layout per quad, vertex and node, so 2.6 million runs of
about 8 MB take a few hundred KB.
"""
import argparse
import hashlib
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'ctr360'))
import cook_disc  # noqa: E402
from iso_bigfile import SECTOR, DATA_OFF, DATA_LEN  # noqa: E402

MAGIC = b'CTRC'
VERSION = 1


def record(disc):
    """The cooker's regions as (data offset, sites), from a run that writes nothing."""
    regions = []
    last = []

    def apply_swaps(raw, sites):
        last[:] = [sites]
        return original_apply(raw, sites)

    def convert_language_file(data):
        num_strings, table = struct.unpack_from('<ii', data, 0)
        last[:] = [[(0, 4), (4, 4)] + [(table + i * 4, 4) for i in range(num_strings)]]
        return original_language(data)

    def convert_bigfile_directory(data):
        last[:] = [[(i * 4, 4) for i in range(len(data) // 4)]]
        return original_directory(data)

    class Recorder:
        def __init__(self, path, readonly=True):
            pass

        def write_at(self, lba, offset, data):
            assert last, 'a region was written without its sites'
            regions.append((lba * DATA_LEN + offset, len(data), last[0]))
            last.clear()

        def close(self):
            pass

    original_apply = cook_disc.apply_swaps
    original_language = cook_disc.convert_language_file
    original_directory = cook_disc.convert_bigfile_directory
    cook_disc.apply_swaps = apply_swaps
    cook_disc.convert_language_file = convert_language_file
    cook_disc.convert_bigfile_directory = convert_bigfile_directory
    cook_disc.ImageWriter = Recorder
    cook_disc.cook(str(disc), 'unused', check_only=False)
    return regions


def runs_of(regions):
    """Sorted, merged (data offset, element bytes, count) runs; no two may overlap."""
    runs = []
    for base, length, sites in regions:
        for site in sites:
            off, size = site[0], site[1]
            elem = size if len(site) == 2 else site[2]
            count = size // elem
            assert 0 <= off and off + elem * count <= length and count > 0
            if elem > 1:
                runs.append((base + off, elem, count))
    runs.sort()
    merged = []
    for start, elem, count in runs:
        if merged:
            p_start, p_elem, p_count = merged[-1]
            p_end = p_start + p_elem * p_count
            assert start >= p_end, 'overlapping swaps at data byte %d' % start
            if start == p_end and elem == p_elem:
                merged[-1] = (p_start, elem, p_count + count)
                continue
        merged.append((start, elem, count))
    return merged


def image_index(data):
    return (data // DATA_LEN) * SECTOR + DATA_OFF + data % DATA_LEN


def apply(image, runs):
    """Reverse every element in place; an element across a sector's end takes its bytes from both."""
    straddling = 0
    for start, elem, count in runs:
        at = start
        end = start + elem * count
        while at < end:
            sector_end = (at // DATA_LEN + 1) * DATA_LEN
            whole = min(end, at + (sector_end - at) // elem * elem)
            if whole > at:
                i, j = image_index(at), image_index(whole - 1) + 1
                if elem == 2:
                    chunk = image[i:j]
                    chunk[0::2], chunk[1::2] = chunk[1::2], chunk[0::2]
                    image[i:j] = chunk
                else:
                    for k in range(i, j, elem):
                        image[k:k + elem] = image[k:k + elem][::-1]
                at = whole
            if at < end and at + elem > sector_end:
                where = [image_index(at + k) for k in range(elem)]
                values = [image[w] for w in where]
                for w, v in zip(where, reversed(values)):
                    image[w] = v
                straddling += 1
                at += elem
    return straddling


def varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7f
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


MAX_PATTERN = 16


def encode(runs, image_bytes, crc):
    """Runs as (gap, kind, count), with each longest repeating stretch of up to MAX_PATTERN runs folded."""
    rel = []
    end = 0
    for start, elem, count in runs:
        assert elem in (2, 4)
        rel.append((start - end, elem, count))
        end = start + elem * count
    n = len(rel)
    body = bytearray()
    i = 0
    while i < n:
        best = None
        for k in range(1, MAX_PATTERN + 1):
            if i + 3 * k > n:
                break
            pattern = rel[i + k:i + 2 * k]
            if rel[i][1:] != pattern[0][1:] or rel[i + 1:i + k] != pattern[1:]:
                continue
            times = 2
            while i + (times + 1) * k <= n and rel[i + times * k:i + (times + 1) * k] == pattern:
                times += 1
            if times >= 3 and (best is None or times * k > best[0] * best[1]):
                best = (times, k)
        if best:
            times, k = best
            body += varint(rel[i][0]) + b'\0' + varint(k) + varint(times)
            for gap, elem, count in rel[i + k:i + 2 * k]:
                body += varint(gap) + bytes([elem]) + varint(count)
            i += times * k
        else:
            gap, elem, count = rel[i]
            body += varint(gap) + bytes([elem]) + varint(count)
            i += 1
    return MAGIC + struct.pack('<4I', VERSION, image_bytes, crc, n) + bytes(body)


def decode(recipe):
    """The runs a recipe holds, as the console expands them."""
    assert recipe[:4] == MAGIC
    version, image_bytes, crc, total = struct.unpack_from('<4I', recipe, 4)
    assert version == VERSION
    at = 20

    def number():
        nonlocal at
        value = shift = 0
        while True:
            byte = recipe[at]
            at += 1
            value |= (byte & 0x7f) << shift
            shift += 7
            if not byte & 0x80:
                return value

    runs = []
    end = 0
    while at < len(recipe):
        gap = number()
        kind = recipe[at]
        at += 1
        if kind:
            count = number()
            runs.append((end + gap, kind, count))
            end += gap + kind * count
            continue
        k, times = number(), number()
        pattern = []
        for _ in range(k):
            g = number()
            e = recipe[at]
            at += 1
            pattern.append((g, e, number()))
        for t in range(times):
            for j, (g, e, count) in enumerate(pattern):
                start = end + (gap if t == 0 and j == 0 else g)
                runs.append((start, e, count))
                end = start + e * count
    assert len(runs) == total
    return image_bytes, crc, runs


PATCH_MAGIC = b'CTRP'


def entry_patches(disc, runs, groups):
    """Patches for BIGFILE entries that images converted before 1.0.4.0 left as on the disc.

    Format, little-endian: char magic[4] = "CTRP"; u32 version = 1; u32 records; then per record
    u32 entry count, u32 entries[count], u32 entry bytes, u32 CRC-32 before, u32 CRC-32 after,
    u32 runs, u32 instruction bytes, then the recipe's instructions with offsets from the entry's
    first byte. The entries of a record hold the same bytes. The game applies a record to an
    entry it has read only when the entry's CRC-32 is the one before (platform/native_disc_cook.c).
    """
    image = disc.read_bytes()
    big = cook_disc.BigFile(cook_disc.IsoImage(str(disc)))
    lba, entries = big.lba, big.entries
    out = bytearray(PATCH_MAGIC + struct.pack('<2I', VERSION, len(groups)))
    for group in groups:
        records = []
        for entry in group:
            sector, size = entries[entry]
            start = (lba + sector) * DATA_LEN
            mine = [(s - start, e, c) for s, e, c in runs if start <= s < start + size]
            assert all(s + e * c <= size for s, e, c in mine), 'entry %d: a run past its end' % entry
            data = bytearray(b''.join(image[image_index(start + k * DATA_LEN):image_index(start + k * DATA_LEN) + DATA_LEN]
                                      for k in range((size + DATA_LEN - 1) // DATA_LEN))[:size])
            before = zlib.crc32(data) & 0xffffffff
            for s, e, c in mine:
                for k in range(c):
                    data[s + k * e:s + (k + 1) * e] = data[s + k * e:s + (k + 1) * e][::-1]
            records.append((size, before, zlib.crc32(data) & 0xffffffff, mine))
        assert all(r == records[0] for r in records), 'entries %s differ' % (group,)
        size, before, after, mine = records[0]
        assert mine and before != after
        body = encode(mine, size, after)[20:]
        out += struct.pack('<I', len(group)) + struct.pack('<%dI' % len(group), *group)
        out += struct.pack('<5I', size, before, after, len(mine), len(body)) + body
        print('entries %s: %d bytes, %d runs, CRC-32 %08x before, %08x after, %d bytes of patch' %
              (group, size, len(mine), before, after, len(body)))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--disc', type=Path, required=True, help='the USA dump (.bin, 2352-byte sectors)')
    ap.add_argument('--expect', required=True, help="SHA-256 of the PC converter's image of that dump")
    ap.add_argument('--out', type=Path, required=True, help='the recipe to write')
    ap.add_argument('--entry-patches', type=Path, help='also write patches for these entries of older images')
    ap.add_argument('--entries', default='454,455,464,465',
                    help='entry groups for --entry-patches: a comma-separated list of +-joined entries')
    a = ap.parse_args()
    regions = record(a.disc)
    runs = runs_of(regions)
    image = bytearray(a.disc.read_bytes())
    image_bytes = len(image)
    straddling = apply(image, runs)
    digest = hashlib.sha256(image).hexdigest()
    if digest != a.expect.lower():
        raise SystemExit('replaying %d runs gives %s, not %s' % (len(runs), digest, a.expect))
    crc = zlib.crc32(image) & 0xffffffff
    recipe = encode(runs, image_bytes, crc)
    if decode(recipe) != (image_bytes, crc, runs):
        raise SystemExit('the recipe does not decode to the runs it was made from')
    a.out.write_bytes(recipe)
    elements = sum(count for _, _, count in runs)
    print('%d regions, %d runs, %d elements (%d across a sector end), image %d bytes, CRC-32 %08x' %
          (len(regions), len(runs), elements, straddling, image_bytes, crc))
    print('replayed image matches %s; recipe %d bytes (%d zipped) -> %s' %
          (digest, len(recipe), len(zlib.compress(recipe, 9)), a.out))
    if a.entry_patches:
        groups = [[int(e) for e in group.split('+')] for group in a.entries.split(',')]
        a.entry_patches.write_bytes(entry_patches(a.disc, runs, groups))
        print('entry patches -> %s' % a.entry_patches)


if __name__ == '__main__':
    main()
