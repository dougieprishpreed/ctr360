#!/usr/bin/env python3
"""Session-7g: compare PrepareDrawContext's idpp with the queue's idpp.

qw showed the drawn instance (826f8068) has otRangeSecondary = 0x80008000 at
queue time, and lp showed other instances' OT writes landing on model-pack
pointers (0x8270xxxx) - the signature of a write meant for another idpp field
(e.g. idpp->ptrTexLayout = mh->ptrTexLayout) landing on the range fields. Print
the prepare's idpp address and its key fields, plus the instance, so the
addresses can be compared against the queue's (qw) lines.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

BODY = (TAB + '{ static int s_pc = 0; if (sdata->frameCounter >= 199 && s_pc < 80) { s_pc++; '
        'Platform_Log("[trace] pc f=%d inst=%08x idpp=%08x txl=%08x rn=%08x rs=%08x pb=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)inst, (unsigned)(u32)idpp, '
        '(unsigned)(u32)idpp->ptrTexLayout, (unsigned)(u32)idpp->otRangeNormal, '
        '(unsigned)(u32)idpp->otRangeSecondary, (unsigned)(u32)idpp->pushBuffer); } }')


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    if 'trace] pc ' in text:
        print('pc: already present')
        return 0
    anchor = '\tctx->idpp = idpp;\n'
    idx = text.find(anchor)
    if idx < 0:
        idx = text.find(anchor.replace('\n', '\r\n'))
        anchor = anchor.replace('\n', '\r\n')
    if idx < 0:
        print('pc: anchor not found')
        return 1
    text = text[:idx + len(anchor)] + BODY.replace(NL, nl) + NL + text[idx + len(anchor):]
    io.open(RB, 'w', newline='').write(text)
    print('pc: inserted after the idpp store')
    return 0


if __name__ == '__main__':
    sys.exit(main())
