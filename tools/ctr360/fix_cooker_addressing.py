"""Fix the cooker's addressing: BIGFILE entries carry SECTOR offsets relative to
the bigfile start (iso_bigfile reads them as iso.read(lba + off, size)), so the
in-image byte offset is off * 2048."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\cook_disc.py'
s = io.open(P, encoding='utf-8').read()

old = """    for entry_index in LANGUAGE_ENTRIES:
        offset, size = big.entry_info(entry_index)
        if size == 0:
            print('entry %d: empty, skipped' % entry_index)
            continue
        raw = writer.read_at(big.lba, offset, size) if writer else iso.read(big.lba + offset // DATA_LEN, size)
        if len(raw) < size:
            raise SystemExit('entry %d: short read (%d of %d)' % (entry_index, len(raw), size))"""

new = """    for entry_index in LANGUAGE_ENTRIES:
        offset_sectors, size = big.entries[entry_index]
        if size == 0:
            print('entry %d: empty, skipped' % entry_index)
            continue
        byte_offset = offset_sectors * DATA_LEN
        raw = iso.read(big.lba + offset_sectors, size)
        if len(raw) < size:
            raise SystemExit('entry %d: short read (%d of %d)' % (entry_index, len(raw), size))"""

assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

old2 = """        n = struct.unpack_from('>i', cooked, 0)[0]
        if writer is not None:
            writer.write_at(big.lba, offset, cooked)"""
new2 = """        n = struct.unpack_from('>i', cooked, 0)[0]
        if writer is not None:
            writer.write_at(big.lba, byte_offset, cooked)"""
assert s.count(old2) == 1, s.count(old2)
s = s.replace(old2, new2)

io.open(P, 'w', encoding='utf-8').write(s)
print('cooker addressing fixed (sector offsets)')
