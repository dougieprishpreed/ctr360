"""Add value-printing probes: BOOT_TRACE entries may carry a verbatim C line.

Form: (rel, anchor, label, expected, when, c_line) - when c_line is present it is
inserted instead of the generated marker log."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\build_360_mirror.py'
NL = chr(13) + chr(10)
s = io.open(P, encoding='utf-8', newline='').read()

# 1. teach the inserter about the optional verbatim line
old = '        for rel2, anchor, label, expected, when in entries:'
new = ('        for entry2 in entries:' + NL +
       '            rel2, anchor, label, expected, when = entry2[:5]' + NL +
       '            c_line = entry2[5] if len(entry2) > 5 else None')
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

old2 = "                lines.insert(at, chr(9) + ('Platform_Log(\"[boot] ' + label + 'Qn\");').replace('Q', chr(92)))"
new2 = ("                if c_line is not None:" + NL +
        "                    lines.insert(at, chr(9) + c_line)" + NL +
        "                else:" + NL +
        "                    lines.insert(at, chr(9) + ('Platform_Log(\"[boot] ' + label + 'Qn\");').replace('Q', chr(92)))")
assert s.count(old2) == 1, s.count(old2)
s = s.replace(old2, new2)

# 2. the value probes
marker = 'BOOT_TRACE = ['
Q = chr(34)          # double quote
B = chr(92)          # backslash
def lit(text):
    return Q + text.replace(B, B + B).replace(Q, B + Q) + Q

probe_lang = ('Platform_Log("[boot] lang values: n=%d off=%d f=%08x\\n", numStrings, (int)lngFile->offsetToPtrArr, '
              '(unsigned)(u32)lngFile);')
probe_hs = ('Platform_Log("[boot] hs: lng=%08x num=%d id=%d nlo=%d\\n", (unsigned)(u32)sdata->lngStrings, '
            '(int)sdata->numLngStrings, (int)characterID, (int)characters[characterID].name_LNG_short);')

extra = NL.join([
    '    ("game/LOAD/LOAD_Assets.c",',
    '     "sdata->numLngStrings = numStrings;",',
    '     "lang values", 1, "after",',
    '     ' + lit(probe_lang) + '),',
    '    ("game/GAMEPROG.c",',
    '     "strcpy(track->scoreEntry[mode][0].name, GAME_LANGUAGE_STRINGS[characters[characterID].name_LNG_short]);",',
    '     "hs values", 1, "before",',
    '     ' + lit(probe_hs) + '),',
    '',
])
assert s.count(marker) == 1
s = s.replace(marker, marker + NL + extra, 1)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
import ast
ast.parse(io.open(P, encoding='utf-8').read())
print('verbatim-line support + value probes added; tool parses OK')
print('probe_lang =', probe_lang)
