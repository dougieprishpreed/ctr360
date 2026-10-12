"""Scratch: validate the Cseq song-data layout (CseqSongHeader + seq offset array)
for every song block in KART.HWL, so the cooker can cook exactly those fields.
"""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage

IMG = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
SECTOR = 2048

iso = IsoImage(IMG)
e = iso.find(r'SOUNDS\KART.HWL')
raw = iso.read(e.lba, e.size)

magic, version, unk1, unk2, numSpuAddrs, numOtherFX, numEngineFX, numBanks, numSequences, headerSize = struct.unpack_from('<10i', raw, 0)
off = 40 + 4 * numSpuAddrs + 8 * numOtherFX + 8 * numEngineFX
bank_offsets = struct.unpack_from('<%dH' % numBanks, raw, off)
off += 2 * numBanks
song_offsets = struct.unpack_from('<%dH' % numSequences, raw, off)

bad = 0
tot_songs = 0
tot_seqs = 0
for s in range(numSequences):
    base = song_offsets[s] * SECTOR
    song_size, = struct.unpack_from('<i', raw, base)
    num_long = raw[base + 4]
    num_short = raw[base + 5]
    num_songs, = struct.unpack_from('<H', raw, base + 6)
    addr = base + 8 + 12 * num_long + 8 * num_short + 2 * num_songs
    song_starts = struct.unpack_from('<%dh' % num_songs, raw, base + 8 + 12 * num_long + 8 * num_short)
    data = (addr + 3) & ~3
    tot_songs += num_songs
    ok = True
    for i in range(num_songs):
        csh = data + song_starts[i]
        unk = raw[csh]
        num_seqs = raw[csh + 1]
        bpm, tpqn = struct.unpack_from('<hh', raw, csh + 2)
        seq_off = struct.unpack_from('<%dH' % num_seqs, raw, csh + 6) if num_seqs else ()
        sane = (0 < num_seqs <= 32) and (0 < bpm < 400) and (0 < tpqn < 1024) and all(o < song_size for o in seq_off)
        if not sane:
            ok = False
            bad += 1
            print("song block %d song %d: unk=%d numSeqs=%d bpm=%d tpqn=%d offs=%s songSize=%d"
                  % (s, i, unk, num_seqs, bpm, tpqn, seq_off[:8], song_size))
        tot_seqs += num_seqs
    if s == 28 or s == 0:
        i = 0
        csh = data + song_starts[i]
        print("block %d (sector %d) songSize=%d long=%d short=%d numSongs=%d -> csh@+%d numSeqs=%d bpm=%d tpqn=%d offs=%s"
              % (s, song_offsets[s], song_size, num_long, num_short, num_songs, song_starts[i],
                 raw[csh + 1], *struct.unpack_from('<hh', raw, csh + 2),
                 struct.unpack_from('<%dH' % raw[csh + 1], raw, csh + 6)[:6]))
print("blocks=%d songs=%d seqs=%d implausible=%d" % (numSequences, tot_songs, tot_seqs, bad))
iso.close()
