"""Independently walk every mapped Model graph in the user's disc.

Compare PSX LE numbers with the staged Xenon BE numbers, not just involutive
swap lists. No entry-number whitelist; discover Models through relocation
targets and their mapped, named header arrays. Exit nonzero on any mismatch.
JSON includes coverage and unidentified mapped files, which need other format
contracts. This is model/animation/command coverage, not proof of all endianness.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct

import cook_disc as cook


def named(raw, off):
    name = raw[off:off+16].split(b'\0', 1)[0]
    return name if name and all(32 <= c < 127 for c in name) else None


def model_roots(raw, mapped):
    def word(off):
        return struct.unpack_from('<I', raw, off)[0]
    targets = {0} | {word(4+p) for p in mapped}
    roots = []
    for rel in sorted(targets):
        m = 4+rel
        if rel & 3 or m+24 > len(raw) or not named(raw, m) or rel+0x14 not in mapped:
            continue
        count = struct.unpack_from('<h', raw, m+0x12)[0]
        hrel = word(m+0x14)
        if not 1 <= count <= 64 or not hrel or hrel & 3 or 4+hrel+count*64 > len(raw):
            continue
        if all(named(raw, 4+hrel+i*64) and hrel+i*64+0x20 in mapped and
               hrel+i*64+0x2c in mapped for i in range(count)):
            roots.append(rel)
    return roots


def audit(retail, cooked, report_path):
    original = cook.IsoImage(str(retail))
    target = cook.IsoImage(str(cooked))
    big = cook.BigFile(original)
    report = {'retail': str(retail), 'cooked': str(cooked), 'entries': [],
              'unidentified_mapped_entries': [], 'failures': [], 'coverage': Counter()}
    failures = report['failures']
    coverage = report['coverage']
    excluded = set(cook.LANGUAGE_ENTRIES)
    for entry, (sector, size) in enumerate(big.entries):
        if size < 32 or entry in excluded:
            continue
        raw = original.read(big.lba+sector, size)
        if cook.vram_is_vram(raw[:20], size):
            coverage['vram_entries_excluded'] += 1
            continue
        sites = cook.dram_swap_sites(raw, entry, excluded)
        if not sites and struct.unpack_from('<i', raw)[0] < 0 and entry+1 < big.num_entry:
            ms, mn = big.entries[entry+1]
            external = cook.dram_external_map_sites(raw, original.read(big.lba+ms, mn), entry)
            if external:
                sites = external[0]
                excluded.add(entry+1)
        if not sites:
            continue
        out = target.read(big.lba+sector, size)
        mapped = {s[0]-4 for s in sites if s[0] >= 4}
        coverage['mapped_entries'] += 1
        checked = set()

        def check(off, width, label):
            if (off, width) in checked:
                return
            checked.add((off, width))
            if off < 0 or off+width > size:
                failures.append({'entry': entry, 'field': label, 'offset': off, 'error': 'outside file'})
                return
            before = int.from_bytes(raw[off:off+width], 'little')
            after = int.from_bytes(out[off:off+width], 'big')
            coverage['numeric_fields'] += 1
            if before != after:
                failures.append({'entry': entry, 'field': label, 'offset': off,
                                 'retail_value': before, 'xenon_value': after})

        def word(off):
            if off < 0 or off+4 > size:
                raise ValueError(f'pointer outside entry {entry}: {off:#x}')
            return int.from_bytes(raw[off:off+4], 'little')

        def frame(fo, end):
            for k in range(4):
                check(fo+k*2, 2, 'ModelFrame.position/pad')
            check(fo+24, 4, 'ModelFrame.vertexOffset')
            vertex = word(fo+24)
            if vertex < 28 or fo+vertex >= end:
                raise ValueError(f'invalid ModelFrame vertex span {fo:#x}/{vertex:#x}')
            # Header's opaque block and compressed vertices are byte payloads.
            for a, b in ((fo+8, fo+24), (fo+vertex, end)):
                if raw[a:b] != out[a:b]:
                    failures.append({'entry': entry, 'field': 'ModelFrame.byte_payload', 'offset': a})
            coverage['model_frames'] += 1

        roots = model_roots(raw, mapped)
        if not roots:
            report['unidentified_mapped_entries'].append(entry)
        details = {'entry': entry, 'models': []}
        for rel in roots:
            m = 4+rel
            name = named(raw, m).decode('ascii')
            details['models'].append({'offset': rel, 'name': name})
            coverage['models'] += 1
            if rel == 0:
                coverage['standalone_models'] += 1
            check(m+16, 2, 'Model.id')
            check(m+18, 2, 'Model.numHeaders')
            count = int.from_bytes(raw[m+18:m+20], 'little')
            hroot = word(m+20)
            for hi in range(count):
                h = 4+hroot+hi*64
                coverage['model_headers'] += 1
                for offset, width, label in ((16, 4, 'unk1'), (20, 2, 'maxDistanceLOD'),
                    (22, 2, 'flags'), (48, 4, 'unk3'), (52, 4, 'numAnimations')):
                    check(h+offset, width, 'ModelHeader.'+label)
                # scale remains packed LE: GTE scale readers explicitly decode it.
                if raw[h+24:h+32] != out[h+24:h+32]:
                    failures.append({'entry': entry, 'field': 'ModelHeader.packed_LE_scale', 'offset': h+24})
                try:
                    cmd = 4+word(h+32)
                    colors = 4+word(h+44)
                    cache_count = word(cmd)
                    if cache_count > 128:
                        raise ValueError(f'color cache exceeds 7-bit command addressing: {cache_count}')
                    check(cmd, 4, 'command.cacheCount')
                    coverage['max_cache_count'] = max(coverage['max_cache_count'], cache_count)
                    color_ids = set(range(cache_count))
                    for ci in range(0x4000):
                        p = cmd+4+ci*4
                        command = word(p)
                        check(p, 4, 'command.word')
                        if command == 0xffffffff:
                            break
                        if command >> 16 == 0:
                            if not command & 1:
                                color_ids.add(command >> 9 & 127)
                            if not command & 2:
                                color_ids.add(command >> 2 & 127)
                        elif not command & 0x08000000:
                            color_ids.add(command >> 9 & 127)
                        coverage['commands'] += 1
                    else:
                        raise ValueError('missing bounded command terminator')
                    for color_id in color_ids:
                        check(colors+color_id*4, 4, 'command.color')
                    anim_count = word(h+52)
                    anims = word(h+56)
                    if not anims:
                        frel = word(h+36)
                        if frel and h+36-4 in mapped:
                            # No explicit static-frame stride; its byte payload end
                            # may share subsequent objects, so check header only.
                            f = 4+frel
                            for k in range(4):
                                check(f+k*2, 2, 'staticFrame.position/pad')
                            check(f+24, 4, 'staticFrame.vertexOffset')
                            coverage['static_frames'] += 1
                    else:
                        if not 1 <= anim_count <= 64:
                            raise ValueError('unbounded animation array')
                        for ai in range(anim_count):
                            a = 4+word(4+anims+ai*4)
                            check(a+16, 2, 'ModelAnim.numFrames')
                            check(a+18, 2, 'ModelAnim.frameSize')
                            nf = int.from_bytes(raw[a+16:a+18], 'little')
                            stride = int.from_bytes(raw[a+18:a+20], 'little')
                            logical = nf & 0x7fff
                            stored = (logical >> 1)+1 if nf & 0x8000 else logical
                            if not 1 <= logical <= 0x800 or not 28 <= stride <= 0x2000 or a+24+stored*stride > size:
                                raise ValueError('unbounded animation frames')
                            coverage['animations'] += 1
                            for fi in range(stored):
                                f = a+24+fi*stride
                                frame(f, f+stride)
                except (ValueError, IndexError) as exc:
                    failures.append({'entry': entry, 'model': name, 'header': hi, 'error': str(exc)})
        if roots:
            report['entries'].append(details)
        for off, width in sites:
            check(off, width, 'relocation/map')
    report['coverage'] = dict(coverage)
    original.close()
    target.close()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'coverage': report['coverage'], 'failures': len(failures),
                      'unidentified_mapped_entries': report['unidentified_mapped_entries'],
                      'report': str(report_path)}))
    return bool(failures)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retail', type=Path, default=root.parent/'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin')
    parser.add_argument('--cooked', type=Path, default=root/'build-360/ctr-u-360.bin')
    parser.add_argument('--report', type=Path, default=root/'build-360/results/endian-assets.json')
    args = parser.parse_args()
    raise SystemExit(audit(args.retail, args.cooked, args.report))
