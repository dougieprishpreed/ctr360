#!/usr/bin/env python3
"""Session-6c: bracket the clobbering write inside MainFrame_RenderFrame.

The wch watch (session-6b) showed the write happens during f=13's
MainFrame_RenderFrame call (render-in clean, render-out clobbered). This script
adds a compact `w2` watch after every render step probe (rf10b..rf19) in the
compiled tree so one 60 s run names the exact step.

Each w2 line prints the frame counter and only the clobbered field
(big1 header[3].animtex = ptrMPK + 0x54 + 0x114). Escapes are built from chr()
codes - the earlier generator collapsed `\n` into a real newline and broke the
C string literal.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c')

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'

STEPS = ['rf10b', 'rf11', 'rf12', 'rf13', 'rf14', 'rf15', 'rf16', 'rf18', 'rf19']


def body(tag):
    return (TAB + '{ static int s_w2 = 0; u8 *w; if (s_w2 < 40 && ((u32)sdata->ptrMPK >> 24) == 0x82) '
            '{ s_w2++; w = (u8 *)sdata->ptrMPK; '
            'Platform_Log("[trace] w2 ' + tag + ' f=%d h3c=%08x' + ESCN + '", '
            '(int)sdata->frameCounter, (unsigned)(*(u32 *)(w + 0x54 + 0x114))); } }' + NL)


def main():
    text = io.open(FILE, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    inserted = 0
    for tag in STEPS:
        if ('trace] w2 ' + tag) in text:
            print('%s: already present' % tag)
            continue
        anchor = 'Platform_Log("[trace] ' + tag + ' f=%d'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('%s: anchor not found' % tag)
        eol = text.find(nl, idx)
        text = text[:eol + len(nl)] + body(tag).replace(NL, nl) + text[eol + len(nl):]
        inserted += 1
        print('%s: inserted' % tag)
    io.open(FILE, 'w', newline='').write(text)
    print('step watches ok (%d inserted)' % inserted)


if __name__ == '__main__':
    sys.exit(main())
