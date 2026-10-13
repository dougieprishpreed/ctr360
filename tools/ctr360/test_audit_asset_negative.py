"""Verify the independent audits reject omitted scalars and damaged opaque data.

Only an in-memory view of selected cooked entries is changed. The user image,
release folder and saves are never written. This is an audit negative control,
not execution of the PPC game or a GPU.
"""
from pathlib import Path
import json
import struct
import cook_disc as cook
import audit_endian_assets as assets
import audit_endian_levels as levels

root = Path(__file__).resolve().parents[2]
retail = root.parent / 'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin'
cooked = root / 'build-360/ctr-u-360.bin'
out = root / 'build-360/results/audit-asset-negative'
out.mkdir(parents=True, exist_ok=True)
original_class = cook.IsoImage
original = original_class(str(retail))
big = cook.BigFile(original)

def entry(number):
    sector, size = big.entries[number]
    return original.read(big.lba + sector, size), big.lba + sector

def word(data, offset):
    return struct.unpack_from('<I', data, offset)[0]

mutations = {}
raw, sector = entry(7)
spawn = 4 + word(raw, 4 + 0x134)
ghost = 4 + word(raw, spawn + 4 + 5 * 4)
mutations[sector] = [(ghost, raw[ghost:ghost+20])]

# Choose an actual nonzero weather record rather than manufacturing one.
for number, (relative, size) in enumerate(big.entries):
    if size < 0x198 or number in cook.LANGUAGE_ENTRIES:
        continue
    data = original.read(big.lba + relative, size)
    if cook.vram_is_vram(data[:20], size):
        continue
    sites = cook.dram_swap_sites(data, number, set(cook.LANGUAGE_ENTRIES))
    if not sites or not cook.dram_level_scalar_sites(data, sites, number):
        continue
    at = 4 + 0x104
    if struct.unpack_from('<H',data,at+4)[0]:
        # An omitted native count, plus a wrongly swapped retained sky field.
        sky = 4 + 0x48
        mutations.setdefault(big.lba+relative, []).extend([
            (at+4, data[at+4:at+6]), (sky, bytes([data[sky] ^ 1]))])
        break
else:
    raise AssertionError('no nonzero shipped weather record')

raw, sector = entry(547)
spawn = 4 + word(raw, 4 + 0x134)
credits = 4 + word(raw, spawn + 4 + 6 * 4)
mutations[sector] = [(credits, bytes([raw[credits] ^ 1]))]

raw, sector = entry(220)
lookup = 4 + word(raw, 4)
mutations[sector] = [(lookup, raw[lookup:lookup+4])]

# Reproduce the old stride-based cooker writing a bubble UV as a global ID.
raw, sector = entry(169)
lookup = 4 + word(raw, 4+0x3c)
alias = 4 + word(raw, lookup+4) + 7 * 32 + 16
mutations[sector] = [(alias, raw[alias:alias+4][::-1])]
original.close()

class MutatedImage:
    def __init__(self, path):
        self.image = original_class(path)
    def read(self, sector, size):
        result = bytearray(self.image.read(sector, size))
        for offset, replacement in mutations.get(sector, ()):
            assert offset + len(replacement) <= len(result)
            result[offset:offset+len(replacement)] = replacement
        return bytes(result)
    def close(self):
        self.image.close()

def factory(path):
    return MutatedImage(path) if Path(path).resolve() == cooked.resolve() else original_class(path)

cook.IsoImage = factory
try:
    assert assets.audit(retail, cooked, out/'assets.json')
    assert levels.audit(retail, cooked, out/'levels.json')
finally:
    cook.IsoImage = original_class

asset_failures = json.loads((out/'assets.json').read_text())['failures']
level_failures = json.loads((out/'levels.json').read_text())['failures']
assert any(f['entry']==220 and f.get('field')=='LevTexLookup.numIcon' for f in asset_failures)
assert any(f['entry']==169 and f.get('field')=='aliased icon opaque byte' for f in asset_failures)
assert any(f['entry']==7 and f.get('field','').startswith('GhostHeader') for f in level_failures)
assert any('RainBuffer' in f.get('field','') for f in level_failures)
assert any('SkyboxGlowGradient' in f.get('field','') for f in level_failures)
assert any(f['entry']==547 and f.get('field','').startswith('Credits') for f in level_failures)
print('PASS independent audits reject omitted ghost/weather/font scalars, the old alias UV write, and damaged sky/credits bytes; images unchanged')
