"""Add the BIGFILE directory converter to cook_disc.py (CRLF-aware)."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\cook_disc.py'
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

converter = '''
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


'''.replace(chr(10), NL)

anchor = 'CONVERTERS = {'
assert s.count(anchor) == 1
s = s.replace(anchor, converter + anchor, 1)

old = NL.join([
    '    converted = 0',
    '    for entry_index in LANGUAGE_ENTRIES:',
])
new = NL.join([
    '    converted = 0',
    '',
    '    # BIGFILE.BIG directory: header + entry table, read raw by the game.',
    '    dir_size = BIGFILE_HEADER_BYTES + big.num_entry * BIGFILE_ENTRY_BYTES',
    '    raw_dir = iso.read(big.lba, dir_size)',
    '    cooked_dir = convert_bigfile_directory(raw_dir)',
    '    if convert_back_bigfile_directory(cooked_dir) != raw_dir:',
    "        raise SystemExit('bigfile directory: round-trip mismatch')",
    '    if writer is not None:',
    '        writer.write_at(big.lba, 0, cooked_dir)',
    '    converted += 1',
    "    print('bigfile directory: %d entries, %d bytes -> %s'",
    "          % (big.num_entry, dir_size, 'cooked' if writer else 'ok'))",
    '',
    '    for entry_index in LANGUAGE_ENTRIES:',
])
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
import ast
ast.parse(io.open(P, encoding='utf-8').read())
print('bigfile directory converter added; parses OK')
