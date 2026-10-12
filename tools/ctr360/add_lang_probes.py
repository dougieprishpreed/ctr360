"""Add the decisive language-loading / high-score probes to BOOT_TRACE."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\build_360_mirror.py'
NL = chr(13) + chr(10)
s = io.open(P, encoding='utf-8', newline='').read()

marker = 'BOOT_TRACE = ['
assert s.count(marker) == 1
extra = NL.join([
    '    ("game/LOAD/LOAD_Assets.c",',
    '     "lngFile = LOAD_ReadFile_ex((struct BigHeader *)bigfilePtr, LT_SETADDR, BI_LANGUAGEFILE + lang, lngFile, &size, NULL);",',
    '     "lang: file read returned", 1, "after"),',
    '    ("game/LOAD/LOAD_Assets.c",',
    '     "numStrings = lngFile->numStrings;",',
    '     "lang: numStrings read", 1, "after"),',
    '    ("game/GAMEPROG.c",',
    '     "struct MetaDataCHAR *characters = GAME_CHARACTER_METADATA;",',
    '     "highscores: entering track loop", 1, "after"),',
    '    ("game/GAMEPROG.c",',
    '     "GAMEPROG_ResetHighScores(&save->progress);",',
    '     "ResetHighScores done", 1, "after"),',
    '',
])
s = s.replace(marker, marker + NL + extra, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)

import ast
ast.parse(io.open(P, encoding='utf-8').read())
print('probes added; tool parses OK')
print('BOOT_TRACE entries:', s.count('"after"),') + s.count('"before"),'))
