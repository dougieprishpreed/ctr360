"""Compare native level fields and opaque water/color bytes with the PSX dump.

Discovery shares only the relocation/Level classifier with the cooker. Field
checks below follow runtime struct layouts, independently of its swap lists.
This covers mesh, scenery/water data, minimap and EOR cameras, not all formats.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct

import cook_disc as cook


def audit(retail, cooked, report_path):
    original, target = cook.IsoImage(str(retail)), cook.IsoImage(str(cooked))
    big = cook.BigFile(original)
    coverage = Counter()
    failures, entries = [], []
    excluded = set(cook.LANGUAGE_ENTRIES)
    for entry, (sector, size) in enumerate(big.entries):
        if size < 0x198 or entry in excluded:
            continue
        raw = original.read(big.lba + sector, size)
        if cook.vram_is_vram(raw[:20], size):
            continue
        mapped_sites = cook.dram_swap_sites(raw, entry, excluded)
        if not mapped_sites and struct.unpack_from('<i', raw)[0] < 0 and entry + 1 < big.num_entry:
            ms, mn = big.entries[entry + 1]
            external = cook.dram_external_map_sites(raw, original.read(big.lba + ms, mn), entry)
            if external:
                mapped_sites = external[0]
                excluded.add(entry + 1)
        if not mapped_sites or not cook.dram_level_scalar_sites(raw, mapped_sites, entry):
            continue
        out = target.read(big.lba + sector, size)
        checked = set()

        def word(off):
            return struct.unpack_from('<I', raw, off)[0]

        def check(off, width, label):
            if (off, width) in checked:
                return
            checked.add((off, width))
            if not 0 <= off <= size - width:
                raise ValueError(f'{label}: outside level')
            expected = int.from_bytes(raw[off:off+width], 'little')
            actual = int.from_bytes(out[off:off+width], 'big')
            coverage['numeric_fields'] += 1
            if actual != expected:
                coverage['numeric_failures'] += 1
                if len(failures) < 100:
                    failures.append({'entry': entry, 'offset': off, 'field': label,
                                     'expected': expected, 'actual': actual})

        def array(off, count, width, label):
            for i in range(count):
                check(off+i*width, width, label)

        def opaque(off, count, label):
            if not 0 <= off <= size - count:
                raise ValueError(f'{label}: outside level')
            coverage['opaque_bytes'] += count
            if raw[off:off+count] != out[off:off+count]:
                coverage['opaque_failures'] += 1
                if len(failures) < 100:
                    failures.append({'entry': entry, 'offset': off, 'field': label,
                                     'error': 'byte image changed'})

        try:
            coverage['levels'] += 1
            for off in (12, 20, 0x34, 0xdc, 0x138, 0x140, 0x148, 0x174):
                check(4+off, 4, 'Level count')
            array(4+0x6c, 8*6, 2, 'Level driver start')
            array(4+0x17c, 6, 2, 'Level position')
            mesh = 4+word(4)
            array(mesh, 8, 4, 'MeshInfo')
            nq, nv, _, qr, vr, _, br, nb = struct.unpack_from('<8I', raw, mesh)
            coverage['quadblocks'] += nq
            coverage['vertices'] += nv
            for i in range(nq):
                q = 4+qr+i*0x5c
                array(q, 10, 2, 'QuadBlock index/flags')
                check(q+0x14, 4, 'QuadBlock low draw order')
                opaque(q+0x18, 4, 'QuadBlock high draw-order bytes')
                array(q+0x2c, 6, 2, 'QuadBlock bounds')
                opaque(q+0x38, 4, 'QuadBlock terrain/weather')
                check(q+0x3c, 2, 'QuadBlock ID')
                opaque(q+0x3e, 2, 'QuadBlock checkpoint/normal shift')
                array(q+0x48, 10, 2, 'QuadBlock normal')
            for i in range(nv):
                v = 4+vr+i*16
                array(v, 4, 2, 'LevVertex position/flags')
                opaque(v+8, 8, 'LevVertex color/UV bytes')
            for i in range(nb):
                b = 4+br+i*32
                array(b, 8, 2, 'BSP header/bounds')
                if struct.unpack_from('<H', raw, b)[0] & 1:
                    check(b+0x10, 4, 'BSP leaf ID')
                    check(b+0x18, 4, 'BSP leaf quad count')
                else:
                    array(b+0x10, 8, 2, 'BSP branch values')
            count = word(4+0x174)
            ptr = 4+word(4+0x178)
            coverage['scenery_vertices'] += count
            for i in range(count):
                array(ptr+i*16+4, 3, 4, 'SCVert packed numeric offsets')
            count = word(4+0x34)
            ptr = 4+word(4+0x38)
            seen_water = set()
            coverage['water_vertices'] += count
            for i in range(count):
                w = word(ptr+i*8+4)
                if w not in seen_water:
                    seen_water.add(w)
                    opaque(4+w, 28*2, 'OVert animation samples LE')
            spawn = word(4+0x134)
            detail = {'entry': entry, 'quads': nq, 'vertices': nv, 'water': count}
            if spawn:
                st = 4+spawn
                check(st, 4, 'SpawnType1 count')
                nc = word(st)
                if not 0 <= nc <= 16:
                    raise ValueError('invalid SpawnType1 count')
                mrel = word(st+4) if nc else 0
                if mrel:
                    array(4+mrel, 10, 2, 'UIMapSpawnMetadata')
                    detail['minimap'] = list(struct.unpack_from('<10h', raw, 4+mrel))
                    coverage['minimaps'] += 1
                if entry != cook.MENU_LEVEL_ENTRY and nc > 2 and word(st+12):
                    at = 4+word(st+12)
                    modes = (0, -1, -1, 12, 6, -1, -1, 6, 12, 16, 6, 12, 20, 16, 12, 0, 0)
                    cameras = struct.unpack_from('<h', raw, at)[0]
                    check(at, 2, 'EOR camera count')
                    at += 2
                    if not 0 <= cameras <= 256:
                        raise ValueError('invalid EOR count')
                    for _ in range(cameras):
                        mode = abs(struct.unpack_from('<h', raw, at+2)[0])
                        if mode >= len(modes) or modes[mode] < 0:
                            raise ValueError('invalid EOR mode')
                        array(at, 2+modes[mode]//2, 2, 'EOR camera scalar')
                        at += 4+modes[mode]
                        coverage['eor_cameras'] += 1
            entries.append(detail)
        except (ValueError, struct.error) as exc:
            failures.append({'entry': entry, 'error': str(exc)})
    original.close()
    target.close()
    report = {'retail': str(retail), 'cooked': str(cooked), 'coverage': dict(coverage),
              'entries': entries, 'failures': failures}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'coverage': dict(coverage), 'failures': len(failures), 'report': str(report_path)}))
    return bool(failures or coverage['numeric_failures'] or coverage['opaque_failures'])


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retail', type=Path, default=root.parent/'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin')
    parser.add_argument('--cooked', type=Path, default=root/'build-360/ctr-u-360.bin')
    parser.add_argument('--report', type=Path, default=root/'build-360/results/endian-levels.json')
    args = parser.parse_args()
    raise SystemExit(audit(args.retail, args.cooked, args.report))
