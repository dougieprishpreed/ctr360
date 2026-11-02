"""Check the end-of-race quip table's layout against what the 360 converts to host order.

data850 holds the retail executable's little-endian bytes; UI_VsQuip.c rewrites every
QuipStr (s16, s16, s32) and QuipMetaRaw (u32, u32, s16, s16, s32, s32, s32) field in
host order once. Read as host fields without that, a big-endian console byte-swapped
every PSX pointer and the priority pass wrote to wild addresses at the end of each
multiplayer race. This checks the four regions the conversion walks really are those
records: every quip pointer names a QuipStr of its own region (one retail Battle quip
ends at the next region's start), and the driver fields are inside struct Driver.
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
data = (root / 'game/zGlobal_DATA.c').read_text()
quip = (root / 'game/UI/UI_VsQuip.c').read_text()

start = data.index('.data850 =')
body = data[data.index('{', start) + 1:data.index('}', start)]
table = bytes(int(v, 16) for v in re.findall(r'0x([0-9a-fA-F]{1,2})\b', body))
assert len(table) == 0x850, hex(len(table))

def define(name):
    return int(re.search(r'#define %s\s+0x([0-9a-fA-F]+)' % name, quip)[1], 16)

base = define('UI_QUIP_DATA_BASE_PSX')
vs_meta, vs_end, bat_meta, bat_end = (define(n) for n in ('UI_QUIP_VS_META_OFF', 'UI_QUIP_VS_META_END',
                                                          'UI_QUIP_BAT_META_OFF', 'UI_QUIP_BAT_META_END'))
assert 'UI_VsQuipFieldsToHost(data.data850, 0, UI_QUIP_VS_META_OFF, sizeof(struct QuipStr), strFields' in quip
assert 'UI_VsQuipFieldsToHost(data.data850, UI_QUIP_VS_META_END, UI_QUIP_BAT_META_OFF, sizeof(struct QuipStr), strFields' in quip
assert 'strFields[] = {2, 2, 4}' in quip and 'metaFields[] = {4, 4, 2, 2, 4, 4, 4}' in quip
assert vs_meta % 8 == 0 and (vs_end - vs_meta) % 0x18 == 0 and (bat_meta - vs_end) % 8 == 0 and (bat_end - bat_meta) % 0x18 == 0
assert bat_end == len(table)

def metas(lo, hi, endian):
    for at in range(lo, hi, 0x18):
        yield [int.from_bytes(table[at + o:at + o + n], endian, signed=s)
               for o, n, s in ((0, 4, 0), (4, 4, 0), (8, 2, 1), (10, 2, 1), (12, 4, 1), (16, 4, 1), (20, 4, 1))]

DRIVER_FIELDS_END = 0x600  # quips read driver counters at 0x4f0-0x57f
def check(lo, hi, strings, endian):
    bad = 0
    for curr, nxt, kind, flags, threshold, offset, size in metas(lo, hi, endian):
        c, n = curr - base, nxt - base
        if not (strings[0] <= c < strings[1] and (c - strings[0]) % 8 == 0 and c < n <= strings[1]):
            bad += 1
        elif not (0 <= offset < DRIVER_FIELDS_END and size in (1, 2, 4, 8) and 0 <= kind <= 9):
            bad += 1
    return bad

vs = check(vs_meta, vs_end, (0, vs_meta), 'little')
battle = check(bat_meta, bat_end, (vs_end, bat_meta), 'little')
assert vs == 0 and battle == 0, (vs, battle)
print('PASS: quip table = VS strings 0x%x, VS rules 0x%x-0x%x (%d), Battle strings 0x%x, Battle rules 0x%x-0x%x (%d); '
      'every pointer names its own strings and every driver field fits'
      % (vs_meta, vs_meta, vs_end, (vs_end - vs_meta) // 0x18, vs_end, bat_meta, bat_end, (bat_end - bat_meta) // 0x18))
# The console before the fix: the same bytes read as big-endian fields.
assert check(vs_meta, vs_end, (0, vs_meta), 'big') == (vs_end - vs_meta) // 0x18
print('PASS: read big-endian without the conversion, every VS rule points outside the table (the multiplayer race-end freeze)')
