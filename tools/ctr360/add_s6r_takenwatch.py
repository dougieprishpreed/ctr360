#!/usr/bin/env python3
"""Session-6r: watch the Jit taken-list head's first node across frame phases.

q8 showed the corruption precisely: at f=204 the Jit list is
826f7d68 -> 826f6bb0 -> ... -> 0; at f=205 the first node's `next` is
0x00ef0458. So something writes the FIRST NODE's next (Instance+0) during
f=204. These phase probes print the taken head + the first node + its next.
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
FILES = [os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame.c'),
         os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c')]

BODY = (TAB + '{ static int s_pw = 0; struct Instance *n0; '
        'if (sdata->frameCounter >= 199 && s_pw < 400) { s_pw++; '
        'n0 = (struct Instance *)GAME_TRACKER->JitPools.instance.taken.first; '
        'Platform_Log("[trace] pw %s f=%%d head=%%08x n0=%%08x n0next=%%08x n0model=%%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)GAME_TRACKER->JitPools.instance.taken.first, '
        '(unsigned)(u32)n0, (unsigned)(n0 ? (u32)n0->next : 0), '
        '(unsigned)(n0 ? (u32)n0->model : 0)); } }' + NL)

TAGS = ('pre', 'rf10', 'rf11', 'rf14', 'rf19')


def main():
    changed = 0
    for path in FILES:
        text = io.open(path, 'r', newline='').read()
        nl = '\r\n' if '\r\n' in text else NL
        for tag in TAGS:
            pat = re.compile(r'^\t\{ extern u32 g_ctr360VwList; static int s_pw = 0;.*trace\] pw ' + tag + r'.*\}\r?$', re.M)
            m = pat.search(text)
            if not m:
                continue
            text = text[:m.start()] + (BODY % tag).replace(NL, nl).rstrip(nl) + text[m.end():]
            changed += 1
            print('%s: rewritten' % tag)
        io.open(path, 'w', newline='').write(text)
    print('session-6r ok (%d rewrites)' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
