#!/usr/bin/env python3
"""Session-6o: watch the PVS list from inside the QueueLevInstances walk.

The phase watches read cDC->visInstSrc as NULL (the field is only live inside
the walk), so this probe sits in the walk itself, right after the NULL check,
and prints the list pointer plus its first three words, gated to f>=199.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
PATH = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')
ANCHOR = 'if (visInstSrc == 0)'

BODY = (TAB + '{ static int s_vw2 = 0; if (sdata->frameCounter >= 199 && s_vw2 < 400) { s_vw2++; '
        'Platform_Log("[trace] vw2 f=%s pl=%d vs=%08x w0=%08x w1=%08x w2=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, player, (unsigned)(u32)visInstSrc, '
        '(unsigned)visInstSrc[0], (unsigned)visInstSrc[1], (unsigned)visInstSrc[2]); } }' + NL)


def main():
    text = io.open(PATH, 'r', newline='').read()
    if 'trace] vw2 ' in text:
        print('vw2: present')
        return 0
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(ANCHOR)
    if idx < 0:
        raise SystemExit('anchor not found')
    # walk to the closing brace of the NULL-check block, insert after that line
    brace = text.find('}', text.find('continue;', idx))
    if brace < 0:
        raise SystemExit('block end not found')
    eol = text.find(nl, brace)
    text = text[:eol + len(nl)] + BODY.replace(NL, nl) + text[eol + len(nl):]
    io.open(PATH, 'w', newline='').write(text)
    print('vw2: inserted in QueueLevInstances')
    return 0


if __name__ == '__main__':
    sys.exit(main())
