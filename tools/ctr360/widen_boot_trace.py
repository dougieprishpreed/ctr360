"""ctr360: widen the boot trace to multiple files and add three decisive probes:
 - the language table state right after LOAD_LangFile returns
 - each sub-step of GAMEPROG_NewGame_OnBoot
so the next console run says exactly which call spins."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\build_360_mirror.py'
BS = chr(92)
NL = chr(13) + chr(10)
s = io.open(P, encoding='utf-8', newline='').read()

# 1. BOOT_TRACE entries gain a leading file path
old_head = 'def apply_boot_trace(mirror, log):'
assert s.count(old_head) == 1, s.count(old_head)

old_body_start = s.index(old_head)
old_body_end = s.index('BOOT_TRACE = [', old_body_start)

new_fn = NL.join([
    'def apply_boot_trace(mirror, log):',
    '    """TEMPORARY diagnostic: log a line after each step of the boot path so a',
    '    hang can be located from the console log alone."""',
    '    per_file = {}',
    '    for entry in BOOT_TRACE:',
    '        rel, anchor, label, expected, when = entry',
    '        per_file.setdefault(rel, []).append(entry)',
    '',
    '    for rel, entries in per_file.items():',
    '        NLc = chr(10)',
    '        full = os.path.join(mirror, rel)',
    '        t = b2s(read_bytes(full))',
    '        if (chr(13) + NLc) in t:',
    '            NLc = chr(13) + NLc',
    '        for rel2, anchor, label, expected, when in entries:',
    '            lines = t.split(NLc)',
    '            hits = [i for i, line in enumerate(lines) if anchor in line]',
    '            if len(hits) != expected:',
    '                raise RuntimeError("boot trace anchor %r in %s: expected %d, found %d" % (label, rel, expected, len(hits)))',
    '            for i in reversed(hits):',
    '                at = i + 1 if when == "after" else i',
    '                lines.insert(at, chr(9) + (\'Platform_Log("[boot] \' + label + \'Qn");\').replace(\'Q\', chr(92)))',
    '            t = NLc.join(lines)',
    '        write_bytes(full, s2b(t))',
    '        log("boot trace: %d step(s) instrumented in %s" % (len(entries), rel))',
    '',
    '',
])
s = s[:old_body_start] + new_fn + s[old_body_end:]

# 2. every existing entry gets its file prefix (all currently MainMain.c)
lines = s.split(NL)
out = []
in_block = False
for line in lines:
    if line.startswith('BOOT_TRACE = ['):
        in_block = True
        out.append(line)
        continue
    if in_block and line.startswith(']'):
        in_block = False
        out.append(line)
        continue
    if in_block and line.strip().startswith('("'):
        out.append(line.replace('    ("', '    ("game/MAIN/MainMain.c", "', 1))
        continue
    out.append(line)
s = NL.join(out)

# 3. new probes
marker = 'BOOT_TRACE = ['
assert s.count(marker) == 1
extra = NL.join([
    '    ("game/MAIN/MainMain.c",',
    '     "LOAD_LangFile((int)sdata->ptrBigfile1, 1);",',
    '     "lang state", 1, "after"),',
    '    ("game/GAMEPROG.c",',
    '     "GAMEPROG_NewProfile_OutsideAdv(&GAME_SAVE);",',
    '     "NewProfile_OutsideAdv done", 1, "after"),',
    '    ("game/GAMEPROG.c",',
    '     "GAMEPROG_NewProfile_InsideAdv(&GAME_ADV_PROGRESS);",',
    '     "NewProfile_InsideAdv done", 1, "after"),',
    '    ("game/GAMEPROG.c",',
    '     "GAMEPROG_GetPtrHighScoreTrack();",',
    '     "GetPtrHighScoreTrack done", 1, "after"),',
    '',
])
s = s.replace(marker, marker + NL + extra, 1)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('boot trace widened')

import ast
ast.parse(io.open(P, encoding='utf-8').read())
print('tool parses OK')
