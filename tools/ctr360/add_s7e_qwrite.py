#!/usr/bin/env python3
"""Session-7e: compare the OT-range write (QueueDraw) with the draw's read.

lp showed the OT entries landing all over the mempack (0x8270xxxx pack,
0x826fxxxx pool) instead of the 0x826eae04..0x826ece00 OT pool, so the
idpp->otRangeNormal/Secondary values the draw reads are bogus. Print the idpp
address + the range at the queue's write site, next to the instance, to see
whether the queue wrote the range into the wrong idpp (off-by-item) or the
allocation itself was bogus.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

BODY = (TAB + '{ static int s_qw = 0; if (sdata->frameCounter >= 199 && s_qw < 80) { s_qw++; '
        'Platform_Log("[trace] qw f=%d inst=%08x idpp=%08x rn=%08x rs=%08x prim=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)inst, (unsigned)(u32)idpp, '
        '(unsigned)(u32)idpp->otRangeNormal, (unsigned)(u32)idpp->otRangeSecondary, '
        '(unsigned)(u32)primaryRange); } }')


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    if 'trace] qw ' in text:
        print('qw: already present')
        return 0
    anchor = '\tidpp->otRangeNormal = primaryRange;\n'
    idx = text.find(anchor)
    if idx < 0:
        idx = text.find(anchor.replace('\n', '\r\n'))
        anchor = anchor.replace('\n', '\r\n')
    if idx < 0:
        print('qw: anchor not found')
        return 1
    text = text[:idx + len(anchor)] + BODY.replace(NL, nl) + NL + text[idx + len(anchor):]
    io.open(RB, 'w', newline='').write(text)
    print('qw: inserted after the range store')
    return 0


if __name__ == '__main__':
    sys.exit(main())
