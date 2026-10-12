#!/usr/bin/env python3
"""Session-6n: watch the PVS visInstSrc list slot across the frame phases.

At f=205 the QueueLevInstances walk dies on `visInstSrc[1]` = 0x00ef0458
(garbage; f=204 had a valid 826f6950). The list is the level's PVS array
(`cDC->visInstSrc = pvs->visInstSrc`), so something writes a bad word into it
during f=204. This adds a `vsw` probe printing the first two list words at five
phases (preamble, render-in/rf10, rf11, rf14, rf19), gated to f>=199, so the
phase where slot 1 flips names the writer's window.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'

BODY_TMPL = (TAB + '{ static int s_vsw = 0; u32 *vs; if (sdata->frameCounter >= 199 && s_vsw < 400) '
             '{ s_vsw++; vs = (u32 *)GAME_TRACKER->cameraDC[0].visInstSrc; '
             'Platform_Log("[trace] vsw %s f=%%d vs=%%08x w0=%%08x w1=%%08x w2=%%08x' + ESCN + '", '
             '(int)sdata->frameCounter, (unsigned)(u32)vs, '
             '(unsigned)(vs ? vs[0] : 0), (unsigned)(vs ? vs[1] : 0), (unsigned)(vs ? vs[2] : 0)); } }' + NL)

SITES = [
    (os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame.c'),
     'Platform_Log("[trace] frame: pre-Hub_Main f=%d', 'preamble'),
    (os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf10 f=%d', 'rf10'),
    (os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf11 f=%d', 'rf11'),
    (os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf14 f=%d', 'rf14'),
    (os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf19 f=%d', 'rf19'),
]


def main():
    changed = 0
    for path, anchor, tag in SITES:
        text = io.open(path, 'r', newline='').read()
        if ('trace] vsw ' + tag) in text:
            print('%s: present' % tag)
            continue
        nl = '\r\n' if '\r\n' in text else NL
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('%s: anchor not found' % tag)
        eol = text.find(nl, idx)
        text = text[:eol + len(nl)] + (BODY_TMPL % tag).replace(NL, nl) + text[eol + len(nl):]
        io.open(path, 'w', newline='').write(text)
        changed += 1
        print('%s: inserted' % tag)
    print('vsw watches ok (%d inserted)' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
