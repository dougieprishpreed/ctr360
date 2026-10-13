"""ctr360 disc cooker (work in progress).

Converts the user's own retail PSX dump into a big-endian equivalent that the
Xbox 360 build can read directly: SAME file, same length, same ISO9660 layout,
same sector numbers, same BIGFILE offsets - only the byte order of fields the
game interprets as numbers is swapped, in place.

Reads the user's dump only. Never ships retail data.

Current coverage
----------------
Entry 234..241 (BI_LANGUAGEFILE + 0..7, the language files):

    struct LngFile
    {
        int  numStrings;       /* LE on disc  */
        int  offsetToPtrArr;   /* LE on disc  */
        char strings[1];
    };

    LOAD_LangFile() then walks `offsetToPtrArr` as an array of numStrings
    32-bit self-relative string offsets and rewrites each in place, so both the
    header ints and every pointer-table entry are numeric and must be swapped.

KART.HWL (the HOWL sound file, located through the ISO9660 tree):

    HowlHeader (version + the six count/size ints), SpuAddrEntry[528],
    OtherFX[]/EngineFX[] u16 fields, u16 bankOffsets[]/songOffsets[], and per
    block: s16 numSamples + s16 sample indices (banks), CseqHeader.songSize +
    numSongs + SampleInstrument/SampleDrums s16 fields + s16 song offsets,
    plus per song: CseqSongHeader.bpm/tpqn and the u16 sequence-offset array
    (songs). See hwl_swap_sites() for the exact field list; the `magic` byte
    image, every u8 field and the 8-bit note streams are left untouched.

.vrm VRAM-image entries (LT_VRAM bigfile entries, found structurally: either a
packed marker 0x20 or an exact 0x14 + w*h*2 rect/size match):

    struct VramHeader
    {
        char data[0xC];        /* word 0: 0x10 TIM-ish magic, or 0x20 = packed */
        RECT rect;             /* 0xC: s16 x, y, w, h - read as numbers */
        /* u16 pixels[]; */    /* 0x14: 16-bit colour values */
    };

    LOAD_VramFileCallback() reads the marker, every packed chunk size, every
    RECT and then hands the pixel array to LoadImage(), which copies it into
    VRAM as u16 VALUES whose bits are the PSX 5:5:5:1 colour fields. So the
    pixels are numeric too: each u16 is byte-swapped per element (an unswapped
    file shows PSX black 0x8000 as 0x0080, i.e. a solid dark-green screen).
    See vram_swap_sites().

Usage
-----
    python tools/ctr360/cook_disc.py --check            # validate, no writes
    python tools/ctr360/cook_disc.py --out <image.bin>  # write a cooked copy

The tool verifies each conversion by converting the result back and comparing
byte-for-byte with the original region; nothing is written unless every
covered region round-trips.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iso_bigfile import IsoImage, BigFile, SECTOR, DATA_OFF, DATA_LEN  # noqa: E402

BI_LANGUAGEFILE = 234
LANGUAGE_ENTRIES = list(range(BI_LANGUAGEFILE, BI_LANGUAGEFILE + 8))

# KART.HWL (CD file, ISO9660, not a BIGFILE entry) - the HOWL sound bank/header.
HWL_PATH = 'SOUNDS/KART.HWL'

# Main menu level: its SpawnType1 count and title camera path are host-read
# (see dram_spawntype1_sites). TITLE_INTRO_MENU_READY_FRAME in MM_Title.c.
MENU_LEVEL_ENTRY = 216
TITLE_CAMERA_FRAMES = 231

# Files whose loader treats them as raw little-endian numbers.
NUMERIC_VRAM_FILE_MAX = 0xFF  # not used yet; kept for the next converter


def apply_swaps(raw, sites):
    """Apply byte swaps. A site is either (offset, size) - reverse those bytes -
    or (offset, size, elementSize) - reverse every elementSize-byte element
    inside the range (16-bit pixel data is a sequence of u16 VALUES, not a byte
    stream, so its bytes must be swapped per element).

    Every site is its own inverse, so applying the same site list twice must
    reproduce the original bytes exactly."""
    out = bytearray(raw)
    for site in sites:
        off = site[0]
        size = site[1]
        if len(site) == 2:
            out[off:off + size] = out[off:off + size][::-1]
        else:
            elem = site[2]
            end = off + size
            if (elem == 2) and ((size & 1) == 0):
                # fast path: swap the halves of every u16 in one step
                chunk = out[off:end]
                chunk[0::2], chunk[1::2] = chunk[1::2], chunk[0::2]
                out[off:end] = chunk
            else:
                p = off
                while (p + elem) <= end:
                    out[p:p + elem] = out[p:p + elem][::-1]
                    p += elem
    return bytes(out)


def site_span(site):
    """(offset, size[, elementSize]) -> (offset, size).

    A site may carry a third element size for per-element swaps (see
    apply_swaps); everything that only needs the covered byte range goes
    through this helper so both shapes are accepted."""
    return (site[0], site[1])


def hwl_swap_sites(raw):
    """Parse KART.HWL (little-endian on disc) and return the byte ranges that
    hold numbers the game reads with raw struct access.

    Validated layout (matches howl_LoadHeader / howl_ParseHeader / Bank_Alloc /
    Bank_AssignSpuAddrs / howl_LoadSong against the retail file):

        HowlHeader: int magic, version, unk1, unk2,
                    numSpuAddrs, numOtherFX, numEngineFX, numBanks,
                    numSequences, headerSize                     (40 bytes)
        SpuAddrEntry  spuAddrs[numSpuAddrs]        u16 spuAddr, u16 spuSize
        OtherFX       otherFX[numOtherFX]          u16 pitch, u16 spuIndex, u16 duration
        EngineFX      engineFX[numEngineFX]        u16 pitch, u16 unk, u16 spuIndex
        u16 bankOffsets[numBanks]   (sector offsets, used by Bank_Alloc)
        u16 songOffsets[numSequences] (sector offsets, used by howl_SetSong)

        per bank block @ bankOffsets[b] * 2048:
            s16 numSamples, s16 sampleIndex[numSamples]

        per song block @ songOffsets[s] * 2048:
            CseqHeader: int songSize, u8 numLongSamples, u8 numShortSamples, u16 numSongs
            SampleInstrument[numLongSamples]: u8,u8, s16 alwaysZero, basePitch,
                                              spuIndex, ad, sr
            SampleDrums[numShortSamples]:     u8,u8, s16 pitch, spuIndex, alwaysZero
            s16 songStartOffsets[numSongs]

    `magic` is compared by the game as a byte image, and u8 fields are read
    byte-wise, so neither is swapped.
    """
    n = len(raw)
    if n < 40:
        raise SystemExit('KART.HWL: too small')

    magic, version, unk1, unk2, numSpuAddrs, numOtherFX, numEngineFX, numBanks, numSequences, headerSize = \
        struct.unpack_from('<10i', raw, 0)
    if magic != 0x4c574f48:  # 'HOWL' as LE int
        raise SystemExit('KART.HWL: magic mismatch (%08x)' % magic)
    for name, count in (('numSpuAddrs', numSpuAddrs), ('numOtherFX', numOtherFX),
                        ('numEngineFX', numEngineFX), ('numBanks', numBanks),
                        ('numSequences', numSequences)):
        if not (0 < count < 4096):
            raise SystemExit('KART.HWL: implausible %s=%d' % (name, count))

    sites = []
    sites.append((4, 4))                       # version (numeric compare in howl_LoadHeader)
    for word in range(4, 10):                  # numSpuAddrs .. headerSize
        sites.append((word * 4, 4))

    off = 40
    spu_off = off
    for i in range(numSpuAddrs):
        sites.append((spu_off + i * 4, 2))
        sites.append((spu_off + i * 4 + 2, 2))
    off += 4 * numSpuAddrs

    other_off = off
    for i in range(numOtherFX):
        for field in (2, 4, 6):
            sites.append((other_off + i * 8 + field, 2))
    off += 8 * numOtherFX

    engine_off = off
    for i in range(numEngineFX):
        for field in (2, 4, 6):
            sites.append((engine_off + i * 8 + field, 2))
    off += 8 * numEngineFX

    banks_off = off
    bank_offsets = struct.unpack_from('<%dH' % numBanks, raw, banks_off)
    for i in range(numBanks):
        sites.append((banks_off + i * 2, 2))
    off += 2 * numBanks

    songs_off = off
    song_offsets = struct.unpack_from('<%dH' % numSequences, raw, songs_off)
    for i in range(numSequences):
        sites.append((songs_off + i * 2, 2))
    off += 2 * numSequences

    if off > 40 + headerSize:
        raise SystemExit('KART.HWL: tables end (%d) past headerSize+40 (%d)' % (off, 40 + headerSize))

    sector = DATA_LEN
    for b in range(numBanks):
        base = bank_offsets[b] * sector
        if base + 2 > n:
            raise SystemExit('KART.HWL: bank %d offset %d out of file' % (b, bank_offsets[b]))
        num_samples, = struct.unpack_from('<h', raw, base)
        if not (0 < num_samples <= 1023):
            raise SystemExit('KART.HWL: bank %d numSamples=%d implausible' % (b, num_samples))
        sites.append((base, 2))
        for i in range(num_samples):
            idx_off = base + 2 + i * 2
            index, = struct.unpack_from('<h', raw, idx_off)
            if not (0 <= index < numSpuAddrs):
                raise SystemExit('KART.HWL: bank %d index[%d]=%d out of range' % (b, i, index))
            sites.append((idx_off, 2))

    for s in range(numSequences):
        base = song_offsets[s] * sector
        if base + 8 > n:
            raise SystemExit('KART.HWL: song %d offset %d out of file' % (s, song_offsets[s]))
        song_size, = struct.unpack_from('<i', raw, base)
        num_long = raw[base + 4]
        num_short = raw[base + 5]
        num_songs, = struct.unpack_from('<H', raw, base + 6)
        if not (0 < song_size <= n) or not (0 <= num_long < 200) or not (0 <= num_short < 200) or not (0 < num_songs < 1000):
            raise SystemExit('KART.HWL: song %d header implausible (size=%d long=%d short=%d songs=%d)'
                             % (s, song_size, num_long, num_short, num_songs))
        sites.append((base, 4))               # songSize
        sites.append((base + 6, 2))           # numSongs
        table_end = 8 + 12 * num_long + 8 * num_short + 2 * num_songs
        if table_end > song_size:
            raise SystemExit('KART.HWL: song %d tables (%d) exceed songSize (%d)' % (s, table_end, song_size))
        for i in range(num_long):
            for field in (2, 4, 6, 8, 10):    # alwaysZero, basePitch, spuIndex, ad, sr
                sites.append((base + 8 + i * 12 + field, 2))
        drums = base + 8 + 12 * num_long
        for i in range(num_short):
            for field in (2, 4, 6):           # pitch, spuIndex, alwaysZero
                sites.append((drums + i * 8 + field, 2))
        starts = drums + 8 * num_short
        for i in range(num_songs):
            sites.append((starts + i * 2, 2))

        # Song data: per-song CseqSongHeader (bpm/tpqn are s16 numbers) and its
        # u16 sequence-offset array. SongPool_Start() turns those offsets into
        # note-stream pointers, so byte-swapped values would walk garbage
        # (Channel_ParseSongToChannels then spins on an invalid note opcode).
        # The note streams themselves are 8-bit opcode/delta data - not cooked.
        song_starts = struct.unpack_from('<%dh' % num_songs, raw, starts)
        data_off = (starts + 2 * num_songs + 3) & ~3
        for i in range(num_songs):
            if song_starts[i] < 0:
                raise SystemExit('KART.HWL: song %d/%d negative start offset' % (s, i))
            csh = data_off + song_starts[i]
            if csh + 6 > n:
                raise SystemExit('KART.HWL: song %d/%d header past end of file' % (s, i))
            num_seqs = raw[csh + 1]
            bpm, tpqn = struct.unpack_from('<hh', raw, csh + 2)
            if not (0 < num_seqs <= 32) or not (0 < bpm < 400) or not (0 < tpqn < 1024):
                raise SystemExit('KART.HWL: song %d/%d header implausible (numSeqs=%d bpm=%d tpqn=%d)'
                                 % (s, i, num_seqs, bpm, tpqn))
            sites.append((csh + 2, 2))        # bpm
            sites.append((csh + 4, 2))        # tpqn
            for j in range(num_seqs):
                seq_off, = struct.unpack_from('<H', raw, csh + 6 + j * 2)
                if seq_off >= song_size:
                    raise SystemExit('KART.HWL: song %d/%d seq %d offset %d past songSize %d'
                                     % (s, i, j, seq_off, song_size))
                sites.append((csh + 6 + j * 2, 2))

    return sites



class ImageWriter:
    """Writes cooked bytes back into a 2352-byte-per-sector raw image."""

    def __init__(self, path, readonly=True):
        self.path = path
        self.f = open(path, 'rb' if readonly else 'r+b')

    def write_at(self, lba, offset, data):
        """Write `data` at byte `offset` inside the file that starts at `lba`.

        The image stores 2048 payload bytes per 2352-byte sector; splits across
        sectors are handled here so callers can treat it as a byte stream.
        """
        pos = 0
        while pos < len(data):
            sector = (offset + pos) // DATA_LEN
            within = (offset + pos) % DATA_LEN
            take = min(DATA_LEN - within, len(data) - pos)
            self.f.seek((lba + sector) * SECTOR + DATA_OFF + within)
            self.f.write(data[pos:pos + take])
            pos += take

    def read_at(self, lba, offset, size):
        out = bytearray()
        while len(out) < size:
            sector = (offset + len(out)) // DATA_LEN
            within = (offset + len(out)) % DATA_LEN
            take = min(DATA_LEN - within, size - len(out))
            self.f.seek((lba + sector) * SECTOR + DATA_OFF + within)
            out += self.f.read(take)
        return bytes(out)

    def close(self):
        self.f.close()


def swap_u32_list(data, offset, count):
    out = bytearray(data)
    for i in range(count):
        at = offset + i * 4
        v = struct.unpack_from('<I', out, at)[0]
        struct.pack_into('>I', out, at, v)
    return bytes(out)


def convert_language_file(data):
    """LE -> BE for one LngFile region. Returns the converted bytes."""
    if len(data) < 8:
        raise ValueError('language file too small: %d' % len(data))
    num_strings, offset_to_ptr_arr = struct.unpack_from('<ii', data, 0)
    if num_strings <= 0 or num_strings > 100000:
        raise ValueError('implausible numStrings %d' % num_strings)
    if offset_to_ptr_arr < 8 or offset_to_ptr_arr + num_strings * 4 > len(data):
        raise ValueError('pointer table out of range: off=%d n=%d size=%d'
                         % (offset_to_ptr_arr, num_strings, len(data)))

    out = bytearray(data)
    struct.pack_into('>ii', out, 0, num_strings, offset_to_ptr_arr)
    out = bytearray(swap_u32_list(bytes(out), offset_to_ptr_arr, num_strings))

    # Every table entry is a self-relative offset from the file start; after the
    # swap each must still land inside the file.
    for i in range(num_strings):
        rel = struct.unpack_from('>I', out, offset_to_ptr_arr + i * 4)[0]
        if rel >= len(out):
            raise ValueError('string %d offset 0x%x outside file (%d bytes)'
                             % (i, rel, len(out)))
    return bytes(out)


def convert_back_language_file(data):
    """BE -> LE, the inverse, for round-trip verification."""
    num_strings, offset_to_ptr_arr = struct.unpack_from('>ii', data, 0)
    out = bytearray(data)
    struct.pack_into('<ii', out, 0, num_strings, offset_to_ptr_arr)
    out = bytearray(swap_u32_list(bytes(out), offset_to_ptr_arr, num_strings))
    return bytes(out)



# --- BIGFILE.BIG directory -------------------------------------------------

BIGFILE_HEADER_BYTES = 8
BIGFILE_ENTRY_BYTES = 8


def convert_bigfile_directory(data):
    """LE -> BE for the BigHeader + BigEntry[] table at the start of BIGFILE.BIG."""
    if len(data) < BIGFILE_HEADER_BYTES:
        raise ValueError('bigfile directory too small')
    cdpos, num_entry = struct.unpack_from('<ii', data, 0)
    if not (0 < num_entry < 8192):
        raise ValueError('implausible numEntry %d' % num_entry)
    need = BIGFILE_HEADER_BYTES + num_entry * BIGFILE_ENTRY_BYTES
    if len(data) < need:
        raise ValueError('directory truncated: need %d, have %d' % (need, len(data)))

    out = bytearray(data)
    struct.pack_into('>ii', out, 0, cdpos, num_entry)
    for i in range(num_entry):
        at = BIGFILE_HEADER_BYTES + i * BIGFILE_ENTRY_BYTES
        off, size = struct.unpack_from('<ii', out, at)
        struct.pack_into('>ii', out, at, off, size)
    return bytes(out)


def convert_back_bigfile_directory(data):
    cdpos, num_entry = struct.unpack_from('>ii', data, 0)
    out = bytearray(data)
    struct.pack_into('<ii', out, 0, cdpos, num_entry)
    for i in range(num_entry):
        at = BIGFILE_HEADER_BYTES + i * BIGFILE_ENTRY_BYTES
        off, size = struct.unpack_from('>ii', out, at)
        struct.pack_into('<ii', out, at, off, size)
    return bytes(out)


CONVERTERS = {
    'language': (convert_language_file, convert_back_language_file),
}


VRAM_HEADER_SIZE = 0x14
VRAM_RECT_OFFSET = 0xC
VRAM_MAX_W = 1024
VRAM_MAX_H = 512


def _vram_rect_ok(x, y, w, h):
    return ((0 <= x) and (0 <= y) and (0 < w <= VRAM_MAX_W) and (0 < h <= VRAM_MAX_H)
            and ((x + w) <= VRAM_MAX_W) and ((y + h) <= VRAM_MAX_H))


def vram_is_vram(head, file_size):
    """True when a bigfile entry's head looks like a .vrm (LT_VRAM) file.

    Two shapes exist, both read by LOAD_VramFileCallback:
      single: [0xC bytes (word 0 = TIM-ish magic)][RECT rect (4*s16)][pixels]
      packed: [u32 0x20][u32 size][VramHeader ...] ... [u32 size == 0]
    Detection uses the packed marker or an exact rect/pixel-size match.
    """
    if len(head) < VRAM_HEADER_SIZE:
        return False
    first, = struct.unpack_from('<I', head, 0)
    if first == 0x20:
        return True
    if file_size < VRAM_HEADER_SIZE + 2:
        return False
    x, y, w, h = struct.unpack_from('<4h', head, VRAM_RECT_OFFSET)
    if not _vram_rect_ok(x, y, w, h):
        return False
    want = VRAM_HEADER_SIZE + (w * h * 2)
    return want <= file_size <= want + 3


def vram_swap_sites(raw, entry_index):
    """Byte-swap sites for a .vrm entry: the packed marker, the chunk sizes, every
    VramHeader rect field, and every 16-bit PIXEL VALUE.

    The pixels are not opaque: the loader copies them into VRAM as u16 values
    whose bits are the PSX 5:5:5:1 colour fields, so an unswapped LE file shows
    black (0x8000) as 0x0080 - a solid dark-green screen with the artwork's real
    brightness left in place."""
    n = len(raw)
    if n < VRAM_HEADER_SIZE + 2:
        return None

    first, = struct.unpack_from('<I', raw, 0)
    if first == 0x20:
        sites = [(0, 4)]
        off = 4
        guard = 0
        while True:
            guard += 1
            if guard > 4096:
                raise SystemExit('entry %d: vram chunk walk did not terminate' % entry_index)
            if (off + 4) > n:
                raise SystemExit('entry %d: vram size word past end of entry' % entry_index)
            size, = struct.unpack_from('<I', raw, off)
            sites.append((off, 4))
            off += 4
            if size == 0:
                break
            if ((size & 3) != 0) or (size < VRAM_HEADER_SIZE) or ((off + size) > n):
                raise SystemExit('entry %d: vram chunk size %d invalid (off %d, %d bytes)' % (entry_index, size, off, n))
            x, y, w, h = struct.unpack_from('<4h', raw, off + VRAM_RECT_OFFSET)
            if not _vram_rect_ok(x, y, w, h):
                raise SystemExit('entry %d: vram rect %d,%d %dx%d implausible' % (entry_index, x, y, w, h))
            if size < VRAM_HEADER_SIZE + (w * h * 2):
                raise SystemExit('entry %d: vram chunk %d bytes smaller than %dx%d pixel data'
                                 % (entry_index, size, w, h))
            for k in range(4):
                sites.append((off + VRAM_RECT_OFFSET + k * 2, 2))
            # Pixel VALUES are 16-bit colour fields the loader copies into VRAM,
            # so each u16 must be swapped - not the whole pixel area as bytes.
            sites.append((off + VRAM_HEADER_SIZE, w * h * 2, 2))
            off += size
        return sites

    x, y, w, h = struct.unpack_from('<4h', raw, VRAM_RECT_OFFSET)
    if not _vram_rect_ok(x, y, w, h):
        return None
    want = VRAM_HEADER_SIZE + (w * h * 2)
    if not (want <= n <= want + 3):
        return None
    return ([(VRAM_RECT_OFFSET + k * 2, 2) for k in range(4)]
            + [(VRAM_HEADER_SIZE, w * h * 2, 2)])


DRAM_PTR_MAP_EXCLUDED_HINT = 'entries already covered by another converter'


def dram_swap_sites(raw, entry_index, excluded):
    """Byte-swap sites for a bigfile entry that carries a DRAM pointer map.

    Layout (LOAD_DramFileCallback / LOAD_RunPtrMap):
        word 0              int  offset to the map, or negative when absent
        content             the file body; `origin` = content (file + 4)
        map at origin+mapOff: int numBytes; then numBytes/4 x int offsets
                              (offsets are relative to `origin`)
    The loader patches every listed word with `value += origin`. On big-endian
    input that arithmetic runs on byte-swapped values, so the map offset, the
    map's own offsets, numBytes and every listed pointer word must all be
    swapped - which is exactly the site list the map already spells out.

    Returns None when the entry does not look like a pointer-mapped file.
    """
    if entry_index in excluded:
        return None
    n = len(raw)
    if n < 16:
        return None
    map_off, = struct.unpack_from('<i', raw, 0)
    if map_off < 0:
        return None
    map_at = 4 + map_off
    if (map_at + 8) > n:
        return None
    num_bytes, = struct.unpack_from('<i', raw, map_at)
    if num_bytes <= 0 or (num_bytes & 3) or (map_at + 4 + num_bytes) > n:
        return None
    count = num_bytes >> 2
    if count < 4:
        return None
    offs = struct.unpack_from('<%di' % count, raw, map_at + 4)
    first = offs[0]
    if (first < 0) or (first & 3):
        return None
    # Structural invariants of the format: offsets ascend, stay inside the file
    # and address the content (before the map itself, which sits at the end).
    prev = -1
    for o in offs:
        if (o < 0) or (o & 3) or ((4 + o + 4) > n) or (o < prev):
            return None
        if 4 + o >= map_at:
            return None
        prev = o
    if (num_bytes >> 2) < 16:
        # not enough pointers to be confident; require ascending start instead
        return None

    sites = [(0, 4), (map_at, 4)]
    for i in range(count):
        sites.append((map_at + 4 + i * 4, 4))
    for o in offs:
        sites.append((4 + o, 4))

    # No two sites may overlap: an overlapped word would be swapped twice and
    # silently revert to little-endian.
    seen = set()
    for off, size in map(site_span, sites):
        for b in range(off, off + size):
            if b in seen:
                raise SystemExit('entry %d: dram map sites overlap at byte %d' % (entry_index, b))
            seen.add(b)
    return sites


def dram_external_map_sites(raw, pointer_map, entry_index):
    """A LEV with a negative map marker uses the following BIGFILE PTR entry.

    LOAD_DramFileCallback leaves relocation to LOAD_Callback_PatchMem for
    these files (adventure hubs, intro scenes and credits). The external map
    contains a numeric byte count and ascending offsets from LEV content+0;
    use those same offsets as the authority for cooking pointer words.
    """
    if len(raw) < 0x140 or struct.unpack_from('<i', raw)[0] >= 0:
        return None
    if len(pointer_map) < 68:
        return None
    num_bytes = struct.unpack_from('<I', pointer_map)[0]
    if num_bytes & 3 or num_bytes + 4 != len(pointer_map):
        return None
    offsets = struct.unpack_from('<%dI' % (num_bytes // 4), pointer_map, 4)
    previous = -1
    for offset in offsets:
        if offset & 3 or offset <= previous or offset + 8 > len(raw):
            return None
        previous = offset
    sites = [(0, 4)] + [(4 + offset, 4) for offset in offsets]
    if not dram_level_scalar_sites(raw, sites, entry_index):
        return None
    return sites, [(0, len(pointer_map), 4)]


def dram_pack_scalar_sites(raw, sites, entry_index):
    """Extra swap sites for a pointer-mapped MODEL PACK.

    The map covers pointers only; the scalars around them are read raw too and
    are what the consumer walks with:
      LevTexLookup at content[0]        : int numIcon, int numIconGroup
      struct Model at each list target  : s16 id, s16 numHeaders
    A byte-swapped numIcon makes DecalGlobal_Store walk millions of entries (and
    a byte-swapped Model.id indexes gGT->modelPtr far out of bounds), so these
    are cooked alongside the pointers.

    The model list is the map's leading run of consecutive words starting at
    frame offset 4; the run ends before the NULL terminator, which the map
    deliberately does not list. Returns [] when the entry is not such a pack.
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    def s16(off):
        return struct.unpack_from('<h', base, off)[0]

    if 4 not in frame and (0 not in frame or u32(8) != 0):
        return None
    lookup_rel = u32(4)                      # content[0] = offset of the lookup
    if lookup_rel == 0 or (lookup_rel & 3):
        return None
    lookup = 4 + lookup_rel
    if (lookup + 16) > n:
        return None
    num_icon = u32(lookup)
    num_group = u32(lookup + 8)
    if not (0 < num_icon <= 4096) or not (0 <= num_group <= 1024):
        return None
    # the lookup's pointer fields must be map-covered, in frame coordinates
    if (lookup_rel + 4) not in frame or (lookup_rel + 12) not in frame:
        return None

    extra = [(lookup, 4), (lookup + 8, 4)]

    # model list: consecutive frame offsets 4, 8, 12, ... while the map keeps
    # listing them; each listed word is a relative pointer to a struct Model.
    off = 4
    models = []
    while off in frame:
        target = u32(4 + off)
        if (target == 0) or (target & 3) or ((4 + target + 0x18) > n):
            break
        name = base[4 + target:4 + target + 16]
        printable = sum(1 for b in name if 32 <= b < 127)
        if printable < 2:
            print('  note: entry %d model list target 0x%x has no name (%r); stopping scan'
                  % (entry_index, target, name))
            break
        extra.append((4 + target + 0x10, 2))   # s16 id
        extra.append((4 + target + 0x12, 2))   # s16 numHeaders
        models.append(target)
        off += 4
    # A font-only MPK has a relocated lookup followed by a NULL model list.
    # The validated lookup/table shape above distinguishes it from a level.
    if len(models) == 0 and (0 not in frame or u32(8) != 0):
        return None
    return extra, models


def dram_level_scalar_sites(raw, sites, entry_index):
    """Extra swap sites for a LEVEL/TRACK file.

    Every level file puts `struct Level` at content+0 (frame offsets):
      0  ptr_mesh_info      4  ptr_skybox       8  ptr_anim_tex
      12 numInstances       16 ptrInstDefs       20 numModels
      24 ptrModelsPtrArray
    The pointer fields are map-covered; numInstances and numModels are read raw
    and feed every walk over the level. Identified by exactly this shape - the
    other track files (entry 514 for the ND crate: 10 instances, 20 models) match
    it at content+0 only, while unrelated structures deeper in files do not.

    ptr_skybox and ptrInstDefs are OPTIONAL: the main menu level (entry 216)
    has no skybox and no InstDefs, and both read as 0 there. Requiring them
    non-zero used to reject that level wholesale, which left its numModels at
    the retail little-endian value (21 -> 0x15000000 as a host load) and turned
    the per-frame model walk into a runaway (bounded only by the guest-side
    walk guards). numInstances must be 0 exactly when ptrInstDefs is 0.
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    # required: mesh_info, anim_tex, models array - mapped, aligned, in-file
    for f in (0, 8):
        if f not in frame:
            return None
        v = u32(4 + f)
        if (v & 3) or v == 0 or (v + 0x10) > n:
            return None
    # optional: skybox, InstDefs - 0 is legal; non-zero must look like a pointer
    for f in (4, 16):
        v = u32(4 + f)
        if v != 0 and ((v & 3) or (v + 0x10) > n):
            return None
    num_inst = u32(4 + 12)
    num_models = u32(4 + 20)
    if not (0 <= num_models <= 4096) or num_inst > 4096:
        return None
    model_list = u32(4 + 24)
    if num_models:
        if 24 not in frame or not model_list or model_list & 3 or model_list + 0x10 > n:
            return None
    elif model_list != 0:
        return None
    if (u32(4 + 16) == 0) != (num_inst == 0):
        return None
    # A few non-level pointer arrays mimic the first seven Level words.
    # Require a real mesh header with bounded arrays before classifying one.
    mesh = 4 + u32(4)
    if n < 4 + 0x194 or mesh + 0x20 > n:
        return None
    nq, nv, _, qr, vr, _, br, nb = struct.unpack_from('<8I', base, mesh)
    for count, rel, stride in ((nq, qr, 0x5c), (nv, vr, 0x10), (nb, br, 0x20)):
        if count > 65535 or (count and (not rel or rel & 3)) or 4 + rel + count * stride > n:
            return None
    return [(4 + 12, 4), (4 + 20, 4)], (num_inst, num_models)


def dram_mesh_scalar_sites(raw, sites, entry_index):
    """Native mesh/BSP records; texture layouts, vertex colors and PVS stay bytes.

    All offsets below are from namespace_Level.h. Pointer-map words already
    have their own sites; validate array bounds and references before adding
    only the numeric fields read directly by collision and the 226 renderer.
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    n = len(raw)
    extra = []

    def u32(off):
        return struct.unpack_from('<I', raw, off)[0]

    def array(rel, count, stride, name):
        if count > 65535 or (count and (not rel or rel & 3)) or 4 + rel + count * stride > n:
            raise SystemExit('entry %d: invalid mesh %s array' % (entry_index, name))
        return 4 + rel

    mesh_rel = u32(4)
    mesh = array(mesh_rel, 1, 0x20, 'header')
    nq, nv, _, qr, vr, _, br, nb = struct.unpack_from('<8I', raw, mesh)
    qa = array(qr, nq, 0x5c, 'quad')
    va = array(vr, nv, 0x10, 'vertex')
    ba = array(br, nb, 0x20, 'BSP')
    for off in (0, 4, 8, 0x14, 0x1c):
        extra.append((mesh + off, 4))
    for i in range(nq):
        q = qa + i * 0x5c
        if any(v >= nv for v in struct.unpack_from('<9H', raw, q)):
            raise SystemExit('entry %d: quad %d vertex index outside mesh' % (entry_index, i))
        # draw_order_high is consumed only as four retail byte offsets.
        # draw_order_low is consumed as a numeric bitfield word.
        extra.extend([(q, 0x14, 2), (q + 0x14, 4),
                      (q + 0x2c, 12, 2), (q + 0x3c, 2), (q + 0x48, 20, 2)])
    for i in range(nv):
        extra.append((va + i * 0x10, 8, 2))
    visited = set()

    def node(b, hitbox=False):
        if b in visited:
            return
        if b & 3 or b + 0x20 > n:
            raise SystemExit('entry %d: BSP outside level' % entry_index)
        visited.add(b)
        flag = struct.unpack_from('<H', raw, b)[0]
        extra.append((b, 0x10, 2))
        if hitbox:
            extra.append((b + 0x10, 12, 2))
        elif flag & 1:
            count = u32(b + 0x18)
            rel = u32(b + 0x1c)
            if count > nq or (count and (rel < qr or (rel - qr) % 0x5c or rel + count * 0x5c > qr + nq * 0x5c)):
                raise SystemExit('entry %d: invalid BSP leaf quads' % entry_index)
            extra.extend([(b + 0x10, 4), (b + 0x18, 4)])
            hit_rel = u32(b + 0x14)
            if hit_rel:
                h = 4 + hit_rel
                while h + 4 <= n and u32(h):
                    node(h, True)
                    h += 0x20
                if h + 4 > n:
                    raise SystemExit('entry %d: unterminated BSP hitboxes' % entry_index)
        else:
            for child in struct.unpack_from('<2H', raw, b + 0x18):
                if child != 0xffff and (child & 0x3fff) >= nb:
                    raise SystemExit('entry %d: BSP child outside mesh' % entry_index)
            extra.append((b + 0x10, 0x10, 2))

    for i in range(nb):
        node(ba + i * 0x20)
    return extra, (nq, nv, nb)


def dram_level_runtime_sites(raw, sites, entry_index):
    """Level startup scalars and native position arrays; packed PVS stays LE.

    Skybox and its gradients, TextureLayout, OVert samples and clear RGB keep
    their explicit byte/LE readers. Driver/checkpoint/scenery positions have
    native SVec3 consumers, while SCVert animation offsets are numeric u32s.
    """
    extra = [(4 + 0x6c, 8 * 12, 2), (4 + 0x17c, 12, 2)]
    for off in (0x34, 0xdc, 0x138, 0x140, 0x148, 0x174):
        extra.append((4 + off, 4))
    rain = 4 + 0x104
    extra.extend([(rain, 4), (rain + 4, 4, 2), (rain + 0x18, 8, 2),
                  (rain + 0x20, 16, 4)])

    def array(count_off, ptr_off, stride, name):
        count, = struct.unpack_from('<I', raw, 4 + count_off)
        rel, = struct.unpack_from('<I', raw, 4 + ptr_off)
        if count > 65535 or (count and (not rel or rel & 3)) or 4 + rel + count * stride > len(raw):
            raise SystemExit('entry %d: invalid level %s array' % (entry_index, name))
        return count, 4 + rel

    count, at = array(0x174, 0x178, 0x10, 'scenery')
    for i in range(count):
        extra.append((at + i * 0x10 + 4, 12, 4))
    array(0x34, 0x38, 8, 'water')  # pointer pairs; OVert colors remain LE
    count, at = array(0x148, 0x14c, 0xc, 'checkpoint')
    for i in range(count):
        extra.append((at + i * 0xc, 8, 2))
    for count_off, ptr_off, stride in ((0x138, 0x13c, 6), (0x140, 0x144, 12)):
        count, at = array(count_off, ptr_off, 8, 'spawn')
        for i in range(count):
            head = at + i * 8
            nc, rel = struct.unpack_from('<2I', raw, head)
            if nc > 65535 or (nc and not rel) or 4 + rel + nc * stride > len(raw):
                raise SystemExit('entry %d: invalid spawn coordinates' % entry_index)
            extra.append((head, 4))
            if nc:
                extra.append((4 + rel, nc * stride, 2))
    nav_rel, = struct.unpack_from('<I', raw, 4 + 0x188)
    if nav_rel:
        if nav_rel & 3 or 4 + nav_rel + 12 > len(raw):
            raise SystemExit('entry %d: invalid navigation table' % entry_index)
        seen = set()
        # BOTS_NAV_PATH_COUNT = 3. numPoints is the last frame index,
        # and BOTS_InitNavPath rewrites the retail absolute `last` pointer.
        for rel in struct.unpack_from('<3I', raw, 4 + nav_rel):
            if not rel or rel in seen:
                continue
            seen.add(rel)
            at = 4 + rel
            if rel & 3 or at + 0x4c > len(raw):
                raise SystemExit('entry %d: invalid navigation header' % entry_index)
            magic, points = struct.unpack_from('<2h', raw, at)
            if magic != -0x1303 or points < 0 or at + 0x4c + (points + 1) * 0x14 > len(raw):
                raise SystemExit('entry %d: invalid navigation frames' % entry_index)
            extra.extend([(at, 4, 2), (at + 4, 4), (at + 0xc, 0x40, 2)])
            for i in range(points + 1):
                f = at + 0x4c + i * 0x14
                extra.extend([(f, 6, 2), (f + 0xa, 8, 2)])
    return extra


def dram_decal_scalar_sites(raw, sites, entry_index, is_pack, avoid=()):
    """Cook the numeric fields surrounding already-relocated icon pointers.

    Both MPKs and levels own a LevTexLookup. The MPK's two counts were already
    cooked, but level counts, Icon.global_IconArray_Index and IconGroup's two
    s16 fields were not. In particular font group 4 became 1024 on Xenon and
    DecalGlobal_Store rejected it. TextureLayout remains its existing byte/LE
    contract; names and the mapped pointers are not touched here.
    """
    base = bytes(raw)
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    occupied = {site_span(s) for s in list(sites) + list(avoid)}
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    head = 0 if is_pack else 0x3c
    if head not in frame:
        return []
    lookup_rel = u32(4 + head)
    lookup = 4 + lookup_rel
    if lookup_rel == 0 or lookup_rel & 3 or lookup + 16 > n:
        raise SystemExit('entry %d: invalid decal lookup' % entry_index)
    ni, icons_rel, ng, groups_rel = struct.unpack_from('<4I', base, lookup)
    if ni > 4096 or ng > 1024:
        raise SystemExit('entry %d: invalid decal counts %d/%d' % (entry_index, ni, ng))
    extra = []

    def add(off, size):
        if (off, size) not in occupied:
            extra.append((off, size))
            occupied.add((off, size))

    add(lookup, 4)
    add(lookup + 8, 4)
    if ni:
        if (lookup_rel + 4) not in frame or icons_rel & 3 or 4 + icons_rel + ni * 0x20 > n:
            raise SystemExit('entry %d: invalid decal icon array' % entry_index)
        for i in range(ni):
            icon = 4 + icons_rel + i * 0x20
            name = base[icon:icon + 16]
            prefix = name.split(b'\0', 1)[0]
            if prefix and all(32 <= b < 127 for b in prefix) and not name[len(prefix):].strip(b'\0'):
                add(icon + 0x10, 4)
            else:
                # Four battle LEVs omit the unused `time` texture's 12
                # bytes. The counted fixed-stride tail then aliases bubble
                # UVs and the group pointer table. These are not numeric
                # Icon IDs. DecalGlobal_Store rejects them in either byte
                # order; never cook their UV words as an index.
                value = u32(icon + 0x10)
                reversed_value = int.from_bytes(base[icon + 0x10:icon + 0x14], 'big')
                if min(value, reversed_value) < 0x88:
                    raise SystemExit('entry %d: ambiguous live icon row %d' % (entry_index, i))
    if ng:
        if (lookup_rel + 12) not in frame or groups_rel & 3 or 4 + groups_rel + ng * 4 > n:
            raise SystemExit('entry %d: invalid decal group array' % entry_index)
        for i in range(ng):
            ptr_rel = groups_rel + i * 4
            if ptr_rel not in frame:
                raise SystemExit('entry %d: unmapped decal group pointer' % entry_index)
            group_rel = u32(4 + ptr_rel)
            group = 4 + group_rel
            if group_rel & 3 or group + 0x14 > n:
                raise SystemExit('entry %d: invalid decal group' % entry_index)
            count = struct.unpack_from('<h', base, group + 0x12)[0]
            if count < 0 or group + 0x14 + count * 4 > n:
                raise SystemExit('entry %d: invalid decal glyph count' % entry_index)
            add(group + 0x10, 2)
            add(group + 0x12, 2)
            for j in range(count):
                icon_rel = u32(group + 0x14 + j * 4)
                if icon_rel == 0:
                    continue  # Shipped locktowood group has an unused NULL slot.
                icon = 4 + icon_rel
                if icon_rel & 3 or icon + 0x20 > n:
                    raise SystemExit('entry %d: invalid group icon' % entry_index)
                add(icon + 0x10, 4)
    return extra


def dram_spawntype1_sites(raw, sites, entry_index):
    """SpawnType1 scalars for a level file (+ the menu's title camera path).

    `struct Level`'s frame word 0x134 points (map-covered) at the level's
    SpawnType1 list:
        s32 count; void *entries[count];
    `count` is NOT map-covered and every consumer reads it with a plain host
    load (MM_Title_Init's `count > 2` gate, CAM_*/RB_* spawners) while the
    retail file stores it little-endian, so the menu's 4 reads as 0x04000000
    host-side.

    The main menu level's title camera path is ST1_CAMERA_PATH = entries[3]:
    a flat array of { SVec3 pos; SVec3 rot; } frames that MM_Title_CameraMove
    indexes by introtimer (0..TITLE_INTRO_MENU_READY_FRAME) and reads with host
    loads, so each s16 is cooked. Only the menu walks it this way (other levels'
    paths are segment-structured CAM_Path_* input), hence the entry check.
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    if 0x134 not in frame:
        return None
    spo = u32(4 + 0x134)
    if spo == 0 or (spo & 3) or (4 + spo + 16) > n:
        return None
    st1 = 4 + spo
    count = struct.unpack_from('<i', base, st1)[0]
    if not (1 <= count <= 16):
        return None
    entries = []
    for i in range(count):
        e = u32(st1 + 4 + i * 4)
        if e != 0 and ((e & 3) or (4 + e + 4) > n):
            return None
        entries.append(e)
    extra = [(st1, 4)]
    # UIMapSpawnMetadata: ten native s16 fields. TextureLayout bytes elsewhere
    # remain LE. Uncooked bounds/scale/mode project racers off the minimap.
    if entries[0]:
        map_at = 4 + entries[0]
        if map_at + 0x14 > n:
            raise ValueError(f'entry {entry_index}: truncated minimap metadata')
        fields = struct.unpack_from('<10h', base, map_at)
        if (fields[0] == fields[2] or fields[1] == fields[3] or
                not 0 < fields[4] <= 512 or not 0 < fields[5] <= 256 or
                not 0 <= fields[8] <= 3 or fields[9] not in (0, 1)):
            raise ValueError(f'entry {entry_index}: invalid minimap metadata {fields}')
        extra.extend((map_at + i * 2, 2) for i in range(10))
    # CAM_ThTick consumes ST1_CAMERA_EOR with native halfword reads. These
    # variable-size records are distinct from the raw segmented CAM_Path data
    # in entries[3]. Sizes below are retail EndOfRace_Camera_Size (payload
    # bytes following respawn point and mode). Validate the whole table before
    # adding any sites. Some files share a zero-valued final camera record
    # with the following path header, so the next target is not a valid bound.
    if entry_index != MENU_LEVEL_ENTRY and len(entries) > 2 and entries[2]:
        eor = 4 + entries[2]
        bound = n
        if eor + 2 > bound:
            raise ValueError(f'entry {entry_index}: EOR camera header outside its data')
        cameras = struct.unpack_from('<h', base, eor)[0]
        sizes = (0, -1, -1, 12, 6, -1, -1, 6, 12, 16, 6, 12, 20, 16, 12, 0, 0)
        if not 0 <= cameras <= 256:
            raise ValueError(f'entry {entry_index}: invalid EOR camera count {cameras}')
        camera_sites = [(eor, 2)]
        cursor = eor + 2
        for _ in range(cameras):
            if cursor + 4 > bound:
                raise ValueError(f'entry {entry_index}: truncated EOR camera record')
            mode = abs(struct.unpack_from('<h', base, cursor + 2)[0])
            if mode >= len(sizes) or sizes[mode] < 0:
                raise ValueError(f'entry {entry_index}: invalid EOR camera mode {mode}')
            end = cursor + 4 + sizes[mode]
            if end > bound:
                raise ValueError(f'entry {entry_index}: EOR camera payload outside its data')
            camera_sites.extend((at, 2) for at in range(cursor, end, 2))
            cursor = end
        extra.extend(camera_sites)
    if entry_index == MENU_LEVEL_ENTRY and len(entries) > 3 and entries[3] != 0:
        cam = 4 + entries[3]
        if (cam + TITLE_CAMERA_FRAMES * 12) > n:
            return None
        for f in range(TITLE_CAMERA_FRAMES):
            for k in range(6):
                extra.append((cam + f * 12 + k * 2, 2))
    # Built-in TT tapes: scalar GhostHeader is native, padding and compressed
    # replay opcodes retain their original byte stream (including BE fields).
    if entry_index != MENU_LEVEL_ENTRY and count >= 6:
        for slot in (4, 5):
            if not entries[slot]:
                continue
            ghost = 4 + entries[slot]
            if ghost + 40 > n:
                raise ValueError(f'entry {entry_index}: truncated ghost header')
            version, length, level, character = struct.unpack_from('<4h', base, ghost)
            if version != -4 or not 0 <= length <= 0x3e00 - 40 or not 0 <= level < 18 or not 0 <= character < 16 or ghost + 40 + length > n:
                raise ValueError(f'entry {entry_index}: invalid built-in ghost header')
            extra.extend((ghost + i, 2) for i in (0, 2, 4, 6))
            extra.extend((ghost + i, 4) for i in (8, 12, 16))
    return extra, count


def dram_instance_scalar_sites(raw, sites, entry_index, num_inst):
    """InstDef scalars for a level file (struct InstDef, stride 0x40).

    Per instance: name[0x10] (string, untouched), model pointer (map-covered),
    scale (3 * s16 + pad), colorRGBA, flags, two ints, ptrInstance
    (map-covered), pos and rot (3 * s16 each), modelID. The drawing and
    collision code reads every one of those scalars raw, so a byte-swapped
    colour/position/modelID is as wrong as a swapped pointer - it just fails
    differently. Structure is validated per entry (printable name, in-file
    model pointer whose target also has a printable name).
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    if 16 not in frame:
        return None
    inst_rel = u32(4 + 16)          # frame-relative, as stored in the file
    if inst_rel == 0 or (inst_rel & 3):
        return None
    if (4 + inst_rel + (num_inst * 0x40)) > n:
        return None

    extra = []
    for k in range(num_inst):
        off_frame = inst_rel + (k * 0x40)      # frame coords
        off_file = 4 + off_frame               # file coords
        if sum(1 for b in base[off_file:off_file + 0x10] if 32 <= b < 127) < 1:
            return None
        if (off_frame + 0x10) not in frame:
            return None
        model_rel = u32(off_file + 0x10)
        if model_rel == 0 or (4 + model_rel + 0x18) > n:
            return None
        model_file = 4 + model_rel
        # Instances can reference the track's one-letter models too.
        if sum(1 for b in base[model_file:model_file + 0x10] if 32 <= b < 127) < 1:
            return None
        # ptrInstance is frequently NULL, and NULLs are never in the map
        # (relocating one with += base would break it): accept either state,
        # but require value and map to agree.
        ptr_inst = u32(off_file + 0x2C)
        if ptr_inst == 0:
            if (off_frame + 0x2C) in frame:
                return None
        elif (off_frame + 0x2C) not in frame:
            return None
        for f, sz in ((0x14, 2), (0x16, 2), (0x18, 2), (0x1A, 2),
                      (0x1C, 4), (0x20, 4), (0x24, 4), (0x28, 4),
                      (0x30, 2), (0x32, 2), (0x34, 2),
                      (0x36, 2), (0x38, 2), (0x3A, 2), (0x3C, 4)):
            extra.append((off_file + f, sz))
    return extra


def _animtex_sites_from(base, n, atx, seen, extra, frame):
    """Walk one AnimTex chain (all values in FRAME coords; file = frame + 4).

    Stride = sizeof(struct AnimTex) = 0xC (int* + 4*s16, proven by the runtime
    c2 delta 0x400C = 0xC + 4096*4), then numFrames pointer words. The walk
    ends when an entry's word0 equals the first entry's address. numFrames,
    frameOffset, frameSkip are s16 scalars; an uncooked numFrames (16 ->
    0x1000) multiplies the stride, so the consumer walk leaves the data and
    wedges. ptrActiveTex (word0) and the ptrarray entries are relocated
    pointers - leave them to the pointer map.
    """
    if atx == 0 or (atx % 4) != 0 or (4 + atx + 0xC) > n:
        return
    cur = atx
    for _ in range(64):
        if cur in seen or (4 + cur + 0xC) > n:
            return
        if cur not in frame:
            return
        if (cur + 4) in frame or (cur + 6) in frame or (cur + 8) in frame:
            return
        nf = struct.unpack_from('<h', base, 4 + cur + 4)[0]
        if not (1 <= nf <= 255):
            return
        seen.add(cur)
        extra.append((4 + cur + 4, 2))
        extra.append((4 + cur + 6, 2))
        extra.append((4 + cur + 8, 2))
        nxt = cur + 0xC + (nf * 4)
        if (4 + nxt + 4) > n:
            return
        if struct.unpack_from('<I', base, 4 + nxt)[0] == atx:
            return
        cur = nxt


def _animtex_chain_sites(base, n, hfile, seen, extra, frame):
    """ModelHeader.animtex (at header FILE offset + 0x3C) -> chain walk."""
    atx = struct.unpack_from('<I', base, hfile + 0x3C)[0]
    _animtex_sites_from(base, n, atx, seen, extra, frame)


def dram_racer_model_sites(raw, sites, entry_index):
    """Recognize every standalone Model by its mapped header graph.

    LOAD_DramFileCallback uses this format for racers, masks, podiums,
    victory/defeat animations and boss scenes. Entry-number lists omitted
    most Adventure scenes. Require a printable model/header name, a mapped
    header-array pointer, a bounded native scalar layout and mapped geometry
    pointers in every header; arbitrary named DRAM content is not sufficient.
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    n = len(raw)
    name = raw[4:20].split(b'\0', 1)[0]
    known = entry_index in (439, 441, 443, 445) or any(
        start <= entry_index < start + 16 for start in (242, 308, 332))
    def reject(reason):
        if known:
            raise ValueError(f'entry {entry_index}: {reason}')
        return None
    if n < 28 or not name or not all(32 <= b < 127 for b in name) or 0x14 not in frame:
        return reject('invalid standalone Model')
    if entry_index in (439, 441, 443, 445) and name != (b'akubig' if entry_index < 442 else b'ukabig'):
        raise ValueError(f'entry {entry_index}: unexpected talking-mask Model name')
    nh = struct.unpack_from('<h', raw, 4 + 0x12)[0]
    hr = struct.unpack_from('<I', raw, 4 + 0x14)[0]
    if not 1 <= nh <= 64 or hr & 3 or hr == 0 or 4 + hr + nh * 0x40 > n:
        return reject('invalid standalone ModelHeader array')
    for i in range(nh):
        h = 4 + hr + i * 0x40
        hn = raw[h:h+16].split(b'\0', 1)[0]
        if not hn or not all(32 <= b < 127 for b in hn):
            return reject('invalid standalone ModelHeader name')
        for field in (0x20, 0x2c):
            target = struct.unpack_from('<I', raw, h + field)[0]
            if h + field - 4 not in frame or target == 0 or target & 3 or 4 + target + 4 > n:
                return reject('unmapped standalone ModelHeader geometry')
    extra = [(4 + 0x10, 2), (4 + 0x12, 2)]
    seen_animtex = set()
    for i in range(nh):
        h = 4 + hr + i * 0x40
        hn = raw[h:h+16].split(b'\0', 1)[0]
        if not hn or not all(32 <= b < 127 for b in hn):
            raise ValueError(f'entry {entry_index}: invalid standalone ModelHeader name')
        for off, size in ((0x10, 4), (0x14, 2), (0x16, 2), (0x30, 4), (0x34, 4)):
            if size == 4 and h + off - 4 in frame:
                continue
            extra.append((h + off, size))
        _animtex_chain_sites(raw, n, h, seen_animtex, extra, frame)
    return extra


def dram_model_array_sites(raw, sites, entry_index):
    """Fallback for files whose map's leading run IS a model-pointer array.

    Racer model files (BI_RACERMODELHI/MED/LOW sets) have no lookup head, so
    the pack detector rejects them and their models' id/numHeaders stay
    little-endian: id reads as id<<8 and numHeaders as 0x0100 (=256), which
    sends CTR_CycleTex_AllModels' header walk into unrelated bytes and then
    into a garbage animtex chain (a silent stall). Walk the map's listed
    words from frame offset 4 exactly like the consumer does, validating each
    target by its printable name, and cook id + numHeaders + every
    ModelHeader scalar (map as arbiter for 4-byte slots).
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    def s16(off):
        return struct.unpack_from('<h', base, off)[0]

    extra = []
    seen_animtex = set()
    models = 0
    off = 4
    while off in frame:
        rel = u32(4 + off)
        if rel == 0 or (rel & 3):
            break
        mfile = 4 + rel
        if (mfile + 0x40) > n:
            return None
        if sum(1 for b in base[mfile:mfile + 0x10] if 32 <= b < 127) < 2:
            return None
        extra.append((mfile + 0x10, 2))
        extra.append((mfile + 0x12, 2))
        num_headers = s16(mfile + 0x12)
        if not (0 <= num_headers <= 64):
            return None
        hrel = u32(mfile + 0x14)
        if hrel == 0 or (hrel & 3):
            return None
        for h in range(num_headers):
            hfile = 4 + hrel + (h * 0x40)
            if (hfile + 0x40) > n:
                return None
            if sum(1 for b in base[hfile:hfile + 0x10] if 32 <= b < 127) < 2:
                return None
            for f, sz in ((0x10, 4), (0x14, 2), (0x16, 2),
                          (0x30, 4), (0x34, 4)):
                if sz == 4 and (hrel + (h * 0x40) + f) in frame:
                    continue
                extra.append((hfile + f, sz))
            _animtex_chain_sites(base, n, hfile, seen_animtex, extra, frame)
        models += 1
        off += 4
    if models < 3:
        return None
    return extra, models


def dram_level_model_sites(raw, sites, entry_index, num_models):
    """Model scalars for models EMBEDDED IN A LEVEL FILE (struct Level at
    content+0, ptrModelsPtrArray at frame word 24).

    The level's own models are stored into gGT->modelPtr[] by
    LibraryOfModels_Store, indexed by each model's s16 `id`. An uncooked id
    reads as id<<8 (e.g. 0x00BE -> 0xBE00 = -16896 as s16), indexing far below
    modelPtr - into whatever static memory lives there (in ctr360 it landed on
    data.metaPhys[15].offset and killed the driver spawn). Cook id +
    numHeaders per model, and the scalar fields of every ModelHeader, with the
    loader's pointer map as the arbiter for 4-byte slots (map-covered =>
    pointer, leave it to the loader's += base).
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    def s16(off):
        return struct.unpack_from('<h', base, off)[0]

    if 24 not in frame:
        return None
    arr_rel = u32(4 + 24)
    if arr_rel == 0 or (arr_rel & 3):
        return None
    if (4 + arr_rel + (num_models * 4)) > n:
        return None

    extra = []
    seen_animtex = set()
    for k in range(num_models):
        rel = u32(4 + arr_rel + (k * 4))
        if rel == 0 or (rel & 3):
            return None
        mfile = 4 + rel
        if (mfile + 0x40) > n:
            return None
        # Track files have valid single-letter models/headers ("r", "t", "c").
        # Reject empty names without dropping the entire level's scalar cook.
        if sum(1 for b in base[mfile:mfile + 0x10] if 32 <= b < 127) < 1:
            return None
        extra.append((mfile + 0x10, 2))
        extra.append((mfile + 0x12, 2))
        num_headers = s16(mfile + 0x12)
        if not (0 <= num_headers <= 64):
            return None
        hrel = u32(mfile + 0x14)
        if hrel == 0 or (hrel & 3):
            return None
        for h in range(num_headers):
            hfile = 4 + hrel + (h * 0x40)
            if (hfile + 0x40) > n:
                return None
            if sum(1 for b in base[hfile:hfile + 0x10] if 32 <= b < 127) < 1:
                return None
            for f, sz in ((0x10, 4), (0x14, 2), (0x16, 2),
                          (0x30, 4), (0x34, 4)):
                if sz == 4 and (hrel + (h * 0x40) + f) in frame:
                    continue
                extra.append((hfile + f, sz))
            _animtex_chain_sites(base, n, hfile, seen_animtex, extra, frame)
    return extra


def dram_model_anim_sites(raw, sites, entry_index, num_models=None, avoid=None, model_rels=None):
    """Static and animated ModelFrame scalars in a pointer-mapped pack.

    Each header names `numAnimations` (u32 @0x34) and `ptrAnimations` (word
    @0x38, map-covered). Each animation is a `struct ModelAnim`: u16 numFrames
    @0x10, s16 frameSize @0x12, ModelFrame array at +0x18 with stride
    `frameSize`. Per frame the scalars are pos (3 * s16) + pad @0..7 and
    vertexOffset (int, the 0x1C distance to the vertex data) @0x18. Without
    Static headers instead name a single ModelFrame at ptrFrameData (+0x24),
    with the same scalar layout and byte-packed vertex payload. Without
    this cook the 360 reads e.g. numFrames 115 as 29440 and vertexOffset 0x1C
    as 0x1C000000, so QueueDraw picks a frame pointer outside guest RAM.

    `num_models` not None -> level shape (ptrModelsPtrArray at frame word 24);
    otherwise pack shape (the map's leading run of consecutive model words).
    """
    if __import__("os").environ.get("CTR_NO_ANIM"):
        return []
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    def s16(off):
        return struct.unpack_from('<h', base, off)[0]

    models = []
    if model_rels is not None:
        models = list(model_rels)
    elif num_models is not None:
        if 24 not in frame:
            return None
        arr_rel = u32(4 + 24)
        if arr_rel == 0 or (arr_rel & 3) or (4 + arr_rel + (num_models * 4)) > n:
            return None
        for k in range(num_models):
            rel = u32(4 + arr_rel + (k * 4))
            if rel == 0 or (rel & 3):
                return None
            models.append(rel)
    else:
        off = 4
        while off in frame:
            target = u32(4 + off)
            if target == 0 or (target & 3):
                break
            name = base[4 + target:4 + target + 0x10]
            if sum(1 for b in name if 32 <= b < 127) < 2:
                break
            models.append(target)
            off += 4
    if not models:
        return None

    extra = []
    n_anims = 0
    n_frames = 0
    n_static = 0
    for mrel in models:
        mfile = 4 + mrel
        num_headers = s16(mfile + 0x12)
        if not (1 <= num_headers <= 64):
            continue
        hrel = u32(mfile + 0x14)
        if hrel == 0 or (hrel & 3):
            continue
        for k in range(num_headers):
            hfile = 4 + hrel + (k * 0x40)
            if (hfile + 0x40) > n:
                continue
            nanim = u32(hfile + 0x34)
            panims = u32(hfile + 0x38)
            if panims == 0:
                frel = u32(hfile + 0x24)
                fo = 4 + frel
                # Accept only an actual loader-mapped static frame with the
                # retail ModelFrame layout. Its compressed vertices are bytes;
                # neither those nor the opaque 16-byte frame block are scalars.
                if (hfile + 0x24 - 4) not in frame or frel == 0 or (frel & 3):
                    continue
                if fo + 0x1c > n or not (0x1c <= u32(fo + 0x18) < n - fo):
                    raise ValueError('entry %d: invalid static ModelFrame at %#x'
                                     % (entry_index, frel))
                extra.append((fo, 8, 2))
                extra.append((fo + 0x18, 4))
                n_static += 1
                continue
            if not (1 <= nanim <= 64) or panims == 0 or (panims & 3):
                continue
            if (4 + panims + nanim * 4) > n:
                continue
            for a in range(nanim):
                arel = u32(4 + panims + (a * 4))
                if arel == 0 or (arel & 3):
                    continue
                afile = 4 + arel
                if (afile + 0x18) > n:
                    continue
                nf, fs = struct.unpack_from('<Hh', base, afile + 0x10)
                if not (1 <= (nf & 0x7fff) <= 0x800) or not (0x1C <= fs <= 0x2000):
                    continue
                extra.append((afile + 0x10, 2))
                extra.append((afile + 0x12, 2))
                n_anims += 1
                # RenderBucket_GetFrame halves the frame index when bit 15
                # requests interpolation, and an odd index reads the next
                # stored frame. These animations contain keyframes, not one
                # ModelFrame for every logical interpolation tick. Walking
                # nf records crossed into texture data in intro entry 540.
                stored_frames = nf & 0x7fff
                if nf & 0x8000:
                    stored_frames = (stored_frames >> 1) + 1
                for i in range(stored_frames):
                    fo = afile + 0x18 + (i * fs)
                    if (fo + 0x1C) > n:
                        break
                    # pos is three s16 fields (x, y, z) plus a pad halfword:
                    # swap PER HALFWORD. A whole-block reverse (size 8, no
                    # element size) rotates the fields instead of swapping
                    # them, which fed every reader a neighbouring coordinate
                    # (session 9: the degenerate bbox corners that culled
                    # every instance, and misplaced draw geometry).
                    extra.append((fo, 8, 2))
                    extra.append((fo + 0x18, 4))
                    n_frames += 1
    if not extra:
        return None

    # Keep only sites nothing else covers: a loader-map word (authoritative -
    # the loader adds the base to it) or an earlier cook pass in `avoid`.
    covered = set()
    for off, size in map(site_span, sites):
        covered.update(range(off, off + size))
    if avoid:
        for off, size in map(site_span, avoid):
            covered.update(range(off, off + size))
    out = []
    n_dropped = 0
    for site in extra:
        off, size = site_span(site)
        rng = list(range(off, off + size))
        if any(b in covered for b in rng):
            n_dropped += 1
            continue
        covered.update(rng)
        out.append(site)
    if not out:
        return None
    print('  entry %d: anim sites: %d anim(s), %d frame(s), %d static frame(s), %d site(s) kept (%d dropped)'
          % (entry_index, n_anims, n_frames, n_static, len(out), n_dropped))
    return out


def dram_model_cmdlist_sites(raw, sites, entry_index, num_models=None, avoid=None, model_rels=None):
    """Command-list + color-layout words for every model of a pack/level.

    Layout (verified against entry 514): commandList = [u32 cachedColorCount]
    [u32 command ...] [0xFFFFFFFF]. The count, every command word (bit-packed:
    flags >>24, stackIndex >>16, ...) and every color word must be swapped so
    their bit patterns survive a big-endian read. Un-swapped, the count reads as
    count<<24 and RenderBucket_CopyScratchColorCache copies ~150M words, so the
    draw path reads far outside guest RAM (Xenia: fault at 0x3483A583).
    The leading count only controls the scratch cache copy. Commands can also
    index later colors directly in ptrColors (e.g. oxidebigship caches 26 but
    references through index 63). Cook those referenced words as well.
    """
    if __import__("os").environ.get("CTR_NO_CMDL"):
        return []
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    def s16(off):
        return struct.unpack_from('<h', base, off)[0]

    models = []
    if model_rels is not None:
        models = list(model_rels)
    elif num_models is not None:
        if 24 not in frame:
            return None
        arr_rel = u32(4 + 24)
        if arr_rel == 0 or (arr_rel & 3) or (4 + arr_rel + (num_models * 4)) > n:
            return None
        for k in range(num_models):
            rel = u32(4 + arr_rel + (k * 4))
            if rel == 0 or (rel & 3):
                return None
            models.append(rel)
    else:
        off = 4
        while off in frame:
            target = u32(4 + off)
            if target == 0 or (target & 3):
                break
            name = base[4 + target:4 + target + 0x10]
            if sum(1 for b in name if 32 <= b < 127) < 2:
                break
            models.append(target)
            off += 4
    if not models:
        return None

    extra = []
    n_cmds = 0
    n_lists = 0
    for mrel in models:
        num_headers = s16(4 + mrel + 0x12)
        if not (1 <= num_headers <= 64):
            continue
        hrel = u32(4 + mrel + 0x14)
        if hrel == 0 or (hrel & 3):
            continue
        for k in range(num_headers):
            hfile = 4 + hrel + (k * 0x40)
            if (hfile + 0x40) > n:
                continue
            cmd_rel = u32(hfile + 0x20)
            colors_rel = u32(hfile + 0x2C)
            if cmd_rel == 0 or (cmd_rel & 3) or (4 + cmd_rel + 8) > n:
                continue
            cfile = 4 + cmd_rel
            count = u32(cfile)
            if not (1 <= count <= 0x1000):
                continue
            extra.append((cfile, 4))
            n_lists += 1
            color_indices = set(range(count))
            p = cfile + 4
            for i in range(0x4000):
                if (p + 4) > n:
                    break
                w = u32(p)
                extra.append((p, 4))
                n_cmds += 1
                p += 4
                if w == 0xFFFFFFFF:
                    break
                # Match GetCommandColor and the two-color command reader.
                # Cache references use the already converted leading words;
                # direct references name numeric words in the source layout.
                if (w >> 16) == 0:
                    if (w & 1) == 0:
                        color_indices.add((w >> 9) & 0x7f)
                    if (w & 2) == 0:
                        color_indices.add((w >> 2) & 0x7f)
                elif (w & 0x08000000) == 0:
                    color_indices.add((w >> 9) & 0x7f)
            if colors_rel != 0 and (colors_rel & 3) == 0 and (4 + colors_rel + (count * 4)) <= n:
                cfo = 4 + colors_rel
                for i in sorted(color_indices):
                    if cfo + (i * 4) + 4 > n:
                        raise ValueError('entry %d: command color index %d exceeds file'
                                         % (entry_index, i))
                    extra.append((cfo + (i * 4), 4))
    if not extra:
        return None

    covered = set()
    for off, size in map(site_span, sites):
        covered.update(range(off, off + size))
    if avoid:
        for off, size in map(site_span, avoid):
            covered.update(range(off, off + size))
    out = []
    n_dropped = 0
    for site in extra:
        off, size = site_span(site)
        rng = list(range(off, off + size))
        if any(b in covered for b in rng):
            n_dropped += 1
            continue
        covered.update(rng)
        out.append(site)
    if not out:
        return None
    print('  entry %d: cmd lists: %d list(s), %d command(s), %d site(s) kept (%d dropped)'
          % (entry_index, n_lists, n_cmds, len(out), n_dropped))
    return out


def dram_model_header_scalar_sites(raw, sites, entry_index, num_inst_unused=None):
    if __import__("os").environ.get("CTR_NO_MHDR"):
        return []
    """ModelHeader scalars for every model of a pointer-mapped model pack.

    Graph: content[1..] is the model list (the map's leading run of consecutive
    words), each entry points at a `struct Model` (name[0x10], s16 id, s16
    numHeaders, ModelHeader *headers). Headers are contiguous with stride 0x40.

    Every pointer field inside a header is map-covered by construction (the file's
    own relocation list names exactly the words the loader patches with +base), so
    only the non-pointer scalars need cooking - and the map is the arbiter for the
    two "unknown" 4-byte fields: covered => pointer (skip), uncovered => scalar.
    Scalars cooked: maxDistanceLOD, flags, scale (3 * s16 + pad), unk1/unk3 when
    uncovered, numAnimations.
    """
    frame = {s[0] - 4 for s in sites if s[0] >= 4}
    base = bytes(raw)
    n = len(base)

    def u32(off):
        return struct.unpack_from('<I', base, off)[0]

    # model list = map's leading run of consecutive frame offsets from 4
    models = []
    off = 4
    while off in frame:
        target = u32(4 + off)
        if target == 0 or (target & 3):
            break
        name = base[4 + target:4 + target + 0x10]
        if sum(1 for b in name if 32 <= b < 127) < 2:
            break
        models.append(target)
        off += 4
    if not models:
        return None

    extra = []
    seen_animtex = set()
    headers = 0
    for mrel in models:
        mfile = 4 + mrel
        num_headers = struct.unpack_from('<h', base, mfile + 0x12)[0]
        if not (1 <= num_headers <= 64):
            return None
        hrel = u32(mfile + 0x14)
        if hrel == 0 or (hrel & 3):
            return None
        for k in range(num_headers):
            hframe = hrel + (k * 0x40)
            hfile = 4 + hframe
            if (hfile + 0x40) > n:
                return None
            if sum(1 for b in base[hfile:hfile + 0x10] if 32 <= b < 127) < 2:
                return None
            for f, sz in ((0x10, 4), (0x14, 2), (0x16, 2),
                          (0x30, 4), (0x34, 4)):
                if sz == 4 and (hframe + f) in frame:
                    continue          # the loader relocates this word: a pointer
                extra.append((hfile + f, sz))
            _animtex_chain_sites(base, n, hfile, seen_animtex, extra, frame)
            headers += 1
    if not extra:
        return None
    return extra, headers


def cook(bin_path, out_path=None, check_only=True):
    iso = IsoImage(bin_path)
    big = BigFile(iso)
    writer = None if check_only else ImageWriter(out_path, readonly=False)

    converted = 0

    # BIGFILE.BIG directory: header + entry table, read raw by the game.
    dir_size = BIGFILE_HEADER_BYTES + big.num_entry * BIGFILE_ENTRY_BYTES
    raw_dir = iso.read(big.lba, dir_size)
    cooked_dir = convert_bigfile_directory(raw_dir)
    if convert_back_bigfile_directory(cooked_dir) != raw_dir:
        raise SystemExit('bigfile directory: round-trip mismatch')
    if writer is not None:
        writer.write_at(big.lba, 0, cooked_dir)
    converted += 1
    print('bigfile directory: %d entries, %d bytes -> %s'
      % (big.num_entry, dir_size, 'cooked' if writer else 'ok'))

    # .vrm (LT_VRAM) bigfile entries: LOAD_VramFileCallback reads the packed
    # marker, the chunk sizes and every VramHeader RECT as raw numbers, and
    # LoadImage copies the 16-bit pixel VALUES into VRAM, so they are swapped
    # per element too.
    vram_indices = []
    for entry_index in range(big.num_entry):
        offset_sectors, size = big.entries[entry_index]
        if size < VRAM_HEADER_SIZE:
            continue
        head = iso.read(big.lba + offset_sectors, VRAM_HEADER_SIZE)
        if not vram_is_vram(head, size):
            continue
        byte_offset = offset_sectors * DATA_LEN
        raw = iso.read(big.lba + offset_sectors, size)
        if len(raw) < size:
            raise SystemExit('vram entry %d: short read (%d of %d)' % (entry_index, len(raw), size))
        sites = vram_swap_sites(raw, entry_index)
        if not sites:
            continue
        cooked = apply_swaps(raw, sites)
        if apply_swaps(cooked, sites) != raw:
            raise SystemExit('vram entry %d: round-trip mismatch' % entry_index)
        if writer is not None:
            writer.write_at(big.lba, byte_offset, cooked)
        converted += 1
        vram_indices.append(entry_index)
        first_words = struct.unpack_from('<4I', raw, 0)
        print('vram entry %d: %d bytes, %d site(s), head=%08x %08x %08x %08x -> %s'
              % (entry_index, size, len(sites), first_words[0], first_words[1], first_words[2], first_words[3],
                 'cooked' if writer else 'ok'))
    print('vram entries: %d %s' % (len(vram_indices), vram_indices[:24]))

    # Pointer-mapped DRAM files (levels, model packs, ...): the file's own
    # pointer map lists every word the loader relocates with `value += content
    # base`, so the cook is exact rather than guessed - word 0 (map offset), the
    # map's numBytes, the map's offsets and every listed pointer word.
    dram_indices = []
    dram_sites = 0
    external_maps = []
    packs = []
    levels = []
    model_headers = []
    anim_cooked = []
    cmd_cooked = []
    instanced = []
    level_models = []
    model_arrays = []
    spawntype1 = []
    excluded = set(vram_indices) | set(LANGUAGE_ENTRIES)
    for entry_index in range(big.num_entry):
        offset_sectors, size = big.entries[entry_index]
        if size < 16 or entry_index in excluded:
            continue
        head = iso.read(big.lba + offset_sectors, 16)
        if len(head) < 16:
            continue
        map_off, = struct.unpack_from('<i', head, 0)
        if (map_off >= 0) and ((4 + map_off + 8) > size):
            continue
        byte_offset = offset_sectors * DATA_LEN
        raw = iso.read(big.lba + offset_sectors, size)
        if len(raw) < size:
            raise SystemExit('dram entry %d: short read (%d of %d)' % (entry_index, len(raw), size))
        if map_off < 0:
            if entry_index + 1 >= big.num_entry:
                continue
            map_index = entry_index + 1
            map_sectors, map_size = big.entries[map_index]
            pointer_map = iso.read(big.lba + map_sectors, map_size)
            external = dram_external_map_sites(raw, pointer_map, entry_index)
            if not external:
                continue
            sites, map_sites = external
            cooked_map = apply_swaps(pointer_map, map_sites)
            if apply_swaps(cooked_map, map_sites) != pointer_map:
                raise SystemExit('external map entry %d: round-trip mismatch' % map_index)
            if writer is not None:
                writer.write_at(big.lba, map_sectors * DATA_LEN, cooked_map)
            excluded.add(map_index)
            external_maps.append((entry_index, map_index, map_size))
            converted += 1
        else:
            sites = dram_swap_sites(raw, entry_index, excluded)
        if not sites:
            continue
        pack = dram_pack_scalar_sites(raw, sites, entry_index)
        lvl = None if pack else dram_level_scalar_sites(raw, sites, entry_index)
        extra = None
        if pack:
            extra, models = pack
            packs.append((entry_index, len(models)))
            hdrs = dram_model_header_scalar_sites(raw, sites, entry_index)
            if hdrs:
                extra = list(extra) + list(hdrs[0])
                model_headers.append((entry_index, hdrs[1]))
            anims = dram_model_anim_sites(raw, sites, entry_index, avoid=extra)
            if anims:
                extra = list(extra) + list(anims)
                anim_cooked.append((entry_index, len(anims)))
            cmds = dram_model_cmdlist_sites(raw, sites, entry_index, avoid=extra)
            if cmds:
                extra = list(extra) + list(cmds)
                cmd_cooked.append((entry_index, len(cmds)))
        elif lvl:
            extra, counts = lvl
            levels.append((entry_index, counts))
            mesh_sites, mesh_counts = dram_mesh_scalar_sites(raw, sites, entry_index)
            extra = list(extra) + mesh_sites + dram_level_runtime_sites(raw, sites, entry_index)
            inst = dram_instance_scalar_sites(raw, sites, entry_index, counts[0])
            if inst:
                extra = list(extra) + list(inst)
                instanced.append((entry_index, len(inst) // 14))
            lvl_models = dram_level_model_sites(raw, sites, entry_index, counts[1])
            if lvl_models:
                extra = list(extra) + list(lvl_models)
                level_models.append((entry_index, len(lvl_models)))
            lvl_anims = dram_model_anim_sites(raw, sites, entry_index, num_models=counts[1], avoid=extra)
            if lvl_anims:
                extra = list(extra) + list(lvl_anims)
                anim_cooked.append((entry_index, len(lvl_anims)))
            lvl_cmds = dram_model_cmdlist_sites(raw, sites, entry_index, num_models=counts[1], avoid=extra)
            if lvl_cmds:
                extra = list(extra) + list(lvl_cmds)
                cmd_cooked.append((entry_index, len(lvl_cmds)))
            lev_atx = struct.unpack_from("<I", raw, 4 + 8)[0]
            _animtex_sites_from(raw, len(raw), lev_atx, set(), extra, {_s[0] - 4 for _s in sites if _s[0] >= 4})
            st1 = dram_spawntype1_sites(raw, sites, entry_index)
            if st1:
                extra = list(extra) + list(st1[0])
                spawntype1.append((entry_index, st1[1]))
        else:
            racer = dram_racer_model_sites(raw, sites, entry_index)
            if racer:
                extra = racer
                model_arrays.append((entry_index, 1))
                anims = dram_model_anim_sites(raw, sites, entry_index, avoid=extra, model_rels=[0])
                if anims:
                    extra = list(extra) + list(anims)
                    anim_cooked.append((entry_index, len(anims)))
                cmds = dram_model_cmdlist_sites(raw, sites, entry_index, avoid=extra, model_rels=[0])
                if cmds:
                    extra = list(extra) + list(cmds)
                    cmd_cooked.append((entry_index, len(cmds)))
            else:
                arr = dram_model_array_sites(raw, sites, entry_index)
                if arr:
                    extra, nmodels = arr
                    model_arrays.append((entry_index, nmodels))
        if pack or lvl:
            decals = dram_decal_scalar_sites(raw, sites, entry_index, bool(pack), avoid=extra or ())
            extra = list(extra or ()) + decals
        if extra:
            all_sites = list(sites) + list(extra)
            seen = set()
            for off, size in map(site_span, all_sites):
                for b in range(off, off + size):
                    if b in seen:
                        raise SystemExit('entry %d: merged sites overlap at byte %d' % (entry_index, b))
                    seen.add(b)
            sites = all_sites
        cooked = apply_swaps(raw, sites)
        if apply_swaps(cooked, sites) != raw:
            raise SystemExit('dram entry %d: round-trip mismatch' % entry_index)
        if writer is not None:
            writer.write_at(big.lba, byte_offset, cooked)
        converted += 1
        dram_indices.append(entry_index)
        dram_sites += len(sites)
    print('dram pointer-map entries: %d, %d site(s) total' % (len(dram_indices), dram_sites))
    print('external level maps (level, map, bytes): %s' % (external_maps,))
    print('dram entries (first 24): %s' % (dram_indices[:24],))
    print('model packs (entry, models): %s' % (packs[:16],))
    print('model headers cooked (entry, header count): %s' % (model_headers[:16],))
    print('level headers (entry, (instances, models)): %s' % (levels[:24],))
    print('levels with cooked InstDef scalars (entry, instances): %s' % (instanced[:24],))
    print('level-embedded models cooked (entry, sites): %s' % (level_models[:24],))
    print('level SpawnType1 cooked (entry, count): %s' % (spawntype1[:24],))
    print('map-only model arrays cooked (entry, models): %s' % (model_arrays[:24],))
    print('model anims cooked (entry, sites): %s' % (anim_cooked[:24],))
    print('model command lists cooked (entry, sites): %s' % (cmd_cooked[:24],))

    for entry_index in LANGUAGE_ENTRIES:
        offset_sectors, size = big.entries[entry_index]
        if size == 0:
            print('entry %d: empty, skipped' % entry_index)
            continue
        byte_offset = offset_sectors * DATA_LEN
        raw = iso.read(big.lba + offset_sectors, size)
        if len(raw) < size:
            raise SystemExit('entry %d: short read (%d of %d)' % (entry_index, len(raw), size))

        cooked = convert_language_file(raw)
        back = convert_back_language_file(cooked)
        if back != raw:
            raise SystemExit('entry %d: round-trip mismatch' % entry_index)

        n = struct.unpack_from('>i', cooked, 0)[0]
        if writer is not None:
            writer.write_at(big.lba, byte_offset, cooked)
        converted += 1
        print('entry %d: %d bytes, numStrings=%d, ptr table at %d -> %s'
              % (entry_index, size, n, struct.unpack_from('>i', cooked, 4)[0],
                 'cooked' if writer else 'ok'))

    # --- KART.HWL: HOWL header, pointer tables and bank/song blocks --------
    hwl = iso.find(HWL_PATH)
    if hwl is None:
        raise SystemExit('KART.HWL: not found in the ISO')
    raw_hwl = iso.read(hwl.lba, hwl.size)
    if len(raw_hwl) != hwl.size:
        raise SystemExit('KART.HWL: short read (%d of %d)' % (len(raw_hwl), hwl.size))
    sites = hwl_swap_sites(raw_hwl)
    cooked_hwl = apply_swaps(raw_hwl, sites)
    # The site list is derived from the pristine file and every site is its own
    # inverse, so applying the same list twice must reproduce the original bytes.
    if apply_swaps(cooked_hwl, sites) != raw_hwl:
        raise SystemExit('KART.HWL: round-trip mismatch')
    if writer is not None:
        writer.write_at(hwl.lba, 0, cooked_hwl)
    converted += 1
    print('KART.HWL: %d bytes, %d numeric site(s) -> %s'
          % (hwl.size, len(sites), 'cooked' if writer else 'ok'))

    if check_only:
        print('check only: %d region(s) validated, nothing written' % converted)
    else:
        print('wrote %d region(s) into %s' % (converted, out_path))

    if writer:
        writer.close()
    iso.close()
    return converted


def main():
    ap = argparse.ArgumentParser(description='ctr360 disc cooker (WIP)')
    ap.add_argument('--disc', default=os.path.join('..', 'CTR - Crash Team Racing (USA)',
                                                   'CTR - Crash Team Racing (USA).bin'))
    ap.add_argument('--out', help='write a cooked copy here (e.g. ctr-u-360.bin)')
    ap.add_argument('--check', action='store_true', help='validate only, no writes')
    args = ap.parse_args()

    if not args.check and not args.out:
        raise SystemExit('pass --check or --out <image>')

    if args.out:
        import shutil
        shutil.copyfile(args.disc, args.out)
        print('copied retail dump -> %s' % args.out)

    cook(args.disc, args.out, check_only=args.check)
    if args.out and not args.check:
        # A reversible swap list alone cannot detect omitted native fields.
        # Independently compare every discoverable Model graph with the dump.
        from pathlib import Path
        from audit_endian_assets import audit
        report = Path(args.out).with_suffix('.endian-audit.json')
        if audit(Path(args.disc), Path(args.out), report):
            raise SystemExit('cooked model/animation/command byte-order audit failed; see ' + str(report))
        from audit_endian_levels import audit as audit_levels
        report = Path(args.out).with_suffix('.level-audit.json')
        if audit_levels(Path(args.disc), Path(args.out), report):
            raise SystemExit('cooked level/minimap/water byte-order audit failed; see ' + str(report))


if __name__ == '__main__':
    main()
