"""Scratch: decode XA/ENG.XNF (Little-endian) and report the intro XA track's length."""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage

IMG = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
XA_NUM_TYPES = 3
XA_HEADER_SIZE = 0x44
OFF_NUM_XAS_TOTAL = 0x0c
OFF_NUM_TRACKS_TOTAL = 0x10
OFF_NUM_SONGS = 0x2c
OFF_FIRST_SONG_INDEX = 0x38
ENTRY_BYTES = 4

iso = IsoImage(IMG)
e = iso.find('XA/ENG.XNF')
print("XA/ENG.XNF: lba=%d size=%d" % (e.lba, e.size))
data = iso.read(e.lba, e.size)

magic, version, num_types = struct.unpack_from('<III', data, 0)
num_xas_total, num_tracks_total = struct.unpack_from('<II', data, OFF_NUM_XAS_TOTAL)
print("magic=%08x version=%d numTypes=%d numXasTotal=%d numTracksTotal=%d" % (magic, version, num_types, num_xas_total, num_tracks_total))

xa_size_off = XA_HEADER_SIZE + num_xas_total * 4
for cat, name in ((0, 'MUSIC'), (1, 'EXTRA'), (2, 'GAME')):
    num_songs = struct.unpack_from('<I', data, OFF_NUM_SONGS + cat * 4)[0]
    first = struct.unpack_from('<I', data, OFF_FIRST_SONG_INDEX + cat * 4)[0]
    print("category %d %s: numSongs=%d firstSongIndex=%d" % (cat, name, num_songs, first))
    for xa in (0, 0x50):
        if xa >= num_songs:
            continue
        ent = xa_size_off + (first + xa) * ENTRY_BYTES
        ch, fileno, sectors = data[ent], data[ent + 1], struct.unpack_from('<h', data, ent + 2)[0]
        path = 'XA/' + ('MUSIC' if cat == 0 else ('ENG/EXTRA' if cat == 1 else 'ENG/GAME')) + '/S%02d.XA' % fileno
        f = iso.find(path)
        total = (f.size // 2336) if f else -1
        print("   xaID=%d -> file=%s channelFilter=0x%02x sectors=%d (%.2f s) fileSectors=%d size=%s"
              % (xa, path, ch, sectors, sectors / 75.0, total, f.size if f else 'MISSING'))
iso.close()
