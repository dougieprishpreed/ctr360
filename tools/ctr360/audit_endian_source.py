"""Inventory native byte-order boundaries; fail on high-confidence hazards.

This is a source review aid, not a full C type checker. Ignore excluded
CTR_NATIVE/PSX branches; retain both branches of unrelated conditionals.
Report word-index packet writes for manual layout review (tags and native
numeric scratch copies can be correct). Keep line numbers and exact source.
"""
import argparse
import json
from pathlib import Path
import re


def native_lines(source):
    stack = []
    active = True
    source = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group().count("\n"), source, flags=re.S)
    for number, line in enumerate(source.splitlines(), 1):
        directive = re.match(r'\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)', line)
        if directive:
            op, expr = directive.groups()
            expr = expr.strip()
            if op in ('if', 'ifdef', 'ifndef'):
                value = None
                if expr == 'CTR_NATIVE' and op in ('ifdef', 'ifndef'):
                    value = op == 'ifdef'
                elif re.fullmatch(r'defined\s*\(?\s*CTR_NATIVE\s*\)?', expr):
                    value = True
                elif re.fullmatch(r'!\s*defined\s*\(?\s*CTR_NATIVE\s*\)?', expr):
                    value = False
                stack.append((active, value))
                active = active and value is not False
            elif op in ('else', 'elif') and stack:
                parent, value = stack[-1]
                active = parent and (value is None or value is False)
            elif op == 'endif' and stack:
                active, _ = stack.pop()
            continue
        if active:
            yield number, line


def findings(source):
    function = ''
    for number, line in native_lines(source):
        if line.lstrip().startswith('//'):
            continue
        definition = re.match(r'^(?:static\s+|inline\s+|__inline\s+)*(?:void|int|u32|s32|s16|MATRIX\s*\*)\s+(\w+)\s*\(', line)
        if definition:
            function = definition[1]
        if re.search(r'CTR_ReadU(?:16|32)(?:Aligned)?LE\([^;]*(?:&data\b|&(?:driver|d)->(?:rotCurr|AxisAngle\d_normalVec|posCurr))', line):
            yield number, 'error', 'LE reader on native runtime state', line.strip()
        if re.search(r'\*\s*\([^)]*(?:u32|s32|int|CtrPackedU32)[^)]*\)\s*&[^;]*(?:teamOfEachPlayer|animFrame|vertSplit|->(?:r[0-3]|x[0-3]|u[0-3])\b)\s*=', line):
            if re.search(r'=\s*\*\s*\([^)]*(?:u32|s32|int|CtrPackedU32)[^)]*\)', line):
                yield number, 'review', 'whole-word byte copy: verify matching byte layouts', line.strip()
            else:
                yield number, 'error', 'whole-word store spans byte/halfword fields', line.strip()
        if re.search(r'(?:\b(?:packet|poly|prim|polyCursor)\s*\[[^\]]+\]|VEH_\w+_WORD\([^;]+\))\s*=', line):
            yield number, 'review', 'word-index store: verify tag versus mixed packet fields', line.strip()
        if re.search(r'CTR_(?:Read|Write)U(?:16|32)(?:Aligned)?LE\([^;]*&\w+->(?:flagsAxis|flagsOscillatorAxis|vel\.z)\b', line):
            yield number, 'error', 'LE word spans native particle/tracker halfwords', line.strip()
        if re.search(r'packet->line\.(?:color\w*|xy\d)\s*=', line):
            yield number, 'error', 'particle line packet needs color-byte/native-XY writers', line.strip()
        if re.search(r'\*\s*\(\s*(?:u8|s8|char)\s*\*\s*\)\s*&\w+->(?:cameraID|state)\b', line):
            yield number, 'error', 'address-order byte of native scalar; use a numeric cast', line.strip()
        if re.search(r'CTR_GteStoreMAC\(\s*(?:&(?:mac|lightMac|viewMac)\.?\w*|out|vec|output)\s*\)', line):
            yield number, 'error', 'packed MAC store used for a native numeric vector', line.strip()
        if re.search(r'(?<!Runtime)(?:SetTransMatrix|CTR_GteSetTransMatrix|gte_SetTransMatrix)\(&(?:inst|plantInst|pDst|pSrc|driverInst)->matrix\)', line):
            yield number, 'error', 'packed translation loader used for world instance state', line.strip()
        # Two explicit exceptions: RaceFlag's compiled numeric constant has its
        # own numeric GTE loader; RotAxisAngle publishes its temporary native
        # result through a complete LE serialization loop before returning.
        if function not in ('RaceFlag_LoadMatrix', 'VehPhysForce_RotAxisAngle'):
            for access in re.finditer(r'(?:\.m|->m)\[[^\]]+\]\[[^\]]+\]', line):
                prefix = line[:access.start()]
                expression = re.search(r'[\w>\.\-()\[\]]+$', prefix)
                start = expression.start() if expression else access.start()
                # Taking the address is valid; numeric evaluation requires a
                # reader. All-zero stores preserve bytes on either host.
                if '&' in line[max(0, start-2):start] or re.match(r'\s*=\s*0\s*;', line[access.end():]):
                    continue
                if re.search(r'CTR_PSX_OBSERVE_MEMORY', line):
                    continue
                yield number, 'error', 'native evaluation of packed LE rotation element', line.strip()
                break


def self_test():
    text = '''#ifdef CTR_NATIVE
*(u32 *)&p->r0 = 0x3a000000;
#else
*(u32 *)&p->r0 = 0x3a000000;
#endif
CTR_ReadU32AlignedLE(&driver->rotCurr.x);
packet[0] = tag;
'''
    found = list(findings(text))
    assert [(x[0], x[1]) for x in found] == [(2, 'error'), (6, 'error'), (7, 'review')]
    assert not list(findings('#ifndef CTR_NATIVE\n*(u32 *)&p->r0 = 1;\n#endif'))
    assert not list(findings('CtrGpu_WriteColorCode(&p->r0, color);'))
    for bad in ('p->flagsAxis = CTR_ReadU32LE(&p->flagsAxis);',
                'CTR_WriteU32LE(&p->flagsAxis, bits);',
                'packet->line.xy0 = MFC2(12);',
                'CTR_GteStoreMAC(&mac.vx);',
                'SetTransMatrix(&inst->matrix);',
                'speed = inst->matrix.m[0][2];'):
        assert any(item[1] == 'error' for item in findings(bad)), bad
    assert not list(findings('speed = (s16)CTR_ReadU16LE(&inst->matrix.m[0][2]);'))
    assert not list(findings('CTR_WriteU16LE(&inst->matrix.m[0][0], 4096);'))
    print('source-audit detector/branch self-test passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=Path('build-360/results/endian-source.json'))
    args = parser.parse_args()
    self_test()
    root = Path(__file__).resolve().parents[2]
    result = {'scope': 'game sources, native-visible branches', 'files': 0, 'errors': [], 'review': [],
              'boundary_inventory': [],
              'rotation_exceptions': {
                  'RaceFlag_LoadMatrix': 'compiled constant; numeric GTE transfer',
                  'VehPhysForce_RotAxisAngle': 'native staging then complete LE serialization'}}
    for path in sorted((root/'game').rglob('*.c')):
        result['files'] += 1
        for line, severity, reason, source in findings(path.read_text(encoding='latin1')):
            result['errors' if severity == 'error' else 'review'].append(
                {'file': path.relative_to(root).as_posix(), 'line': line, 'reason': reason, 'source': source})
        for line, source in native_lines(path.read_text(encoding='latin1')):
            if source.lstrip().startswith('//'):
                continue
            if re.search(r'CTR_(?:Read|Write)U\d+(?:Aligned)?LE|(?:SetTransMatrix|StoreMAC)\(|\([^)]*\b(?:u32|s32|s16|u16|int)\s*\*\s*\)|(?:\.m|->m)\[', source):
                result['boundary_inventory'].append({'file': path.relative_to(root).as_posix(), 'line': line, 'source': source.strip()})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'files': result['files'], 'errors': len(result['errors']),
                      'manual_review_sites': len(result['review']),
                      'inventory_sites': len(result['boundary_inventory']), 'report': str(args.report)}))
    raise SystemExit(bool(result['errors']))
