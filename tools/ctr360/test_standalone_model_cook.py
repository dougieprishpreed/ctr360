"""Actual-disc format coverage, corruption rejection and byte preservation."""
import contextlib
import io
from pathlib import Path
import struct
import cook_disc as cook

root = Path(__file__).resolve().parents[2]
original = cook.IsoImage(str(root.parent/'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin'))
big = cook.BigFile(original)
cooked = cook.IsoImage(str(root/'build-360/ctr-u-360.bin'))
entries = []
with contextlib.redirect_stdout(io.StringIO()):
    for entry, (sector, size) in enumerate(big.entries):
        if size < 32:
            continue
        raw = original.read(big.lba+sector, size)
        sites = cook.dram_swap_sites(raw, entry, set(cook.LANGUAGE_ENTRIES))
        if not sites:
            continue
        extra = cook.dram_racer_model_sites(raw, sites, entry)
        if not extra:
            continue
        extra += cook.dram_model_anim_sites(raw, sites, entry, avoid=extra, model_rels=[0]) or []
        extra += cook.dram_model_cmdlist_sites(raw, sites, entry, avoid=extra, model_rels=[0]) or []
        all_sites = sites+extra
        spans = [range(off, off+length) for off, length in map(cook.site_span, all_sites)]
        assert sum(map(len, spans)) == len(set().union(*spans)), f'{entry}: overlapping conversions'
        target = cooked.read(big.lba+sector, size)
        assert cook.apply_swaps(raw, all_sites) == target, f'{entry}: staged conversion mismatch'
        assert cook.apply_swaps(target, all_sites) == raw, f'{entry}: round-trip mismatch'
        # An otherwise valid named model is rejected without its mapped header.
        no_header = [s for s in sites if s[0] != 24]
        assert cook.dram_racer_model_sites(raw, no_header, -1) is None
        bad = bytearray(raw)
        struct.pack_into('<h', bad, 22, 32767)
        assert cook.dram_racer_model_sites(bad, sites, -1) is None
        bad = bytearray(raw)
        struct.pack_into('<I', bad, 24, len(raw)+4)
        assert cook.dram_racer_model_sites(bad, sites, -1) is None
        entries.append(entry)
original.close()
cooked.close()
assert len(entries) == 152, f'unexpected standalone-format coverage: {entries}'
print(f'{len(entries)} standalone files: staged bytes, disjoint swaps, full round trips and malformed graphs checked')
