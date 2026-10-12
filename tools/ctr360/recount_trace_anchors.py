"""Recount every BOOT_TRACE anchor against the repo sources and report which
expectation counts need adjusting (anchor text can appear in more than one
place, e.g. GAMEPROG_GetPtrHighScoreTrack calls)."""
import io
import os
import re

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\build_360_mirror.py'
ROOT = r'F:\downloads\temp\python\hermes\ctrport\ctr360'

s = io.open(P, encoding='utf-8', newline='').read()
pat = re.compile(r'\(\s*"(game/[^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*(\d+),\s*"(\w+)"\s*\)')

bad = 0
for m in pat.finditer(s):
    rel, anchor, label, exp = m.group(1), m.group(2), m.group(3), int(m.group(4))
    p = os.path.join(ROOT, rel.replace('/', os.sep))
    if not os.path.isfile(p):
        print('MISSING FILE:', p)
        bad += 1
        continue
    t = io.open(p, encoding='utf-8', newline='').read()
    n = t.count(anchor)
    status = 'ok  ' if n == exp else 'FIX '
    if n != exp:
        bad += 1
    print('%s %-46s %-30s expected=%d found=%d' % (status, label[:46], anchor[:30], exp, n))
print('anchors needing fixes:', bad)
