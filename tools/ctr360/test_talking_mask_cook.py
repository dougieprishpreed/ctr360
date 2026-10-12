"""Validate the actual retail talking masks against the Xenon asset contract."""
from pathlib import Path
import struct
import cook_disc as cook

root = Path(__file__).resolve().parents[2]
iso = cook.IsoImage(str(root.parent / 'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin'))
big = cook.BigFile(iso)
converted = cook.IsoImage(str(root / 'build-360/ctr-u-360.bin'))
for entry in (439, 441, 443, 445):
    sector, size = big.entries[entry]
    raw = iso.read(big.lba + sector, size)
    cooked = converted.read(big.lba + sector, size)
    sites = cook.dram_swap_sites(raw, entry, set())
    extra = cook.dram_racer_model_sites(raw, sites, entry)
    extra += cook.dram_model_anim_sites(raw, sites, entry, avoid=extra, model_rels=[0])
    extra += cook.dram_model_cmdlist_sites(raw, sites, entry, avoid=extra, model_rels=[0])
    spans = [range(off, off + length) for off, length in map(cook.site_span, sites + extra)]
    assert sum(map(len, spans)) == len(set().union(*spans)), 'overlapping conversions'
    assert cook.apply_swaps(raw, sites + extra) == cooked
    assert cook.apply_swaps(cooked, sites + extra) == raw
    assert raw[4:20] == cooked[4:20], 'model name changed'
    assert struct.unpack_from('>h', cooked, 22)[0] == 1
    header = 4 + struct.unpack_from('>I', cooked, 24)[0]
    assert struct.unpack_from('>I', cooked, header + 0x34)[0] == 1
    anim_array = 4 + struct.unpack_from('>I', cooked, header + 0x38)[0]
    animation = 4 + struct.unpack_from('>I', cooked, anim_array)[0]
    assert struct.unpack_from('>H', cooked, animation + 0x10)[0] == 0x800d
    stride = struct.unpack_from('>h', cooked, animation + 0x12)[0]
    for frame in range(7):
        pos = animation + 0x18 + frame * stride
        assert struct.unpack_from('>I', cooked, pos + 0x18)[0] == 0x1c
        assert raw[pos + 0x1c:pos + stride] == cooked[pos + 0x1c:pos + stride], 'compressed vertices changed'
    commands = 4 + struct.unpack_from('>I', cooked, header + 0x20)[0]
    count = struct.unpack_from('>I', cooked, commands)[0]
    assert count == struct.unpack_from('<I', raw, commands)[0] and 0 < count < 256
    assert struct.unpack_from('>I', raw, commands)[0] == count << 24
    bad = bytearray(raw)
    bad[4:10] = b'broken'
    try:
        cook.dram_racer_model_sites(bad, sites, entry)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid mask name accepted')
    print(f'entry {entry}: native header, 13 animation ticks / 7 keyframes, {count} cached colors, byte payloads and round trip verified')
# Format detection is independent of BIGFILE entry number.
assert cook.dram_racer_model_sites(raw, sites, 438) is not None
