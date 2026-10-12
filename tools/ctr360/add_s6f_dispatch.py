#!/usr/bin/env python3
"""Session-6f: bracket the clobber inside RenderBucket_DispatchDrawFunc.

cc showed the color-cache copy is clean (count=8). Next in the dispatch:
the instance setup callback, then the five draw-func cases. This script adds a
`dsp` probe after the setup callback and one before each case's `return`
(after its draw call), so the first probe that shows the flipped field names the
writer.

    dsp setup   - after RenderBucket_RunInstanceSetupCallback
    dsp caseN   - after each RenderBucket_DrawFunc_* call, before `return;`

Watched field: big1 header[3].animtex = ptrMPK + 0x54 + 0x114 (guarded on the
0x82 arena). Escapes are built from chr() codes.
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'

CASES = [
    ('setup', '\tif (RenderBucket_RunInstanceSetupCallback(ctx) == 0)'),
    ('case0', '\t\tRenderBucket_DrawFunc_Normal(ctx);'),
    ('case1', '\t\tRenderBucket_DrawFunc_NormalAlt(ctx);'),
    ('case2', '\t\tRenderBucket_DrawFunc_Split(ctx);'),
    ('case3', '\t\tRenderBucket_DrawFunc_Special(ctx);'),
    ('case4', '\t\tRenderBucket_DrawFunc_Reflection(ctx);'),
]


def body(tag):
    return (TAB + '{ static int s_dsp_%s = 0; u8 *w; if (s_dsp_%s < 60 && ((u32)sdata->ptrMPK >> 24) == 0x82) '
            '{ s_dsp_%s++; w = (u8 *)sdata->ptrMPK; '
            'Platform_Log("[trace] dsp %s f=%%d h3c=%%08x' % (tag, tag, tag, tag)
            + ESCN + '", (int)sdata->frameCounter, (unsigned)(*(u32 *)(w + 0x54 + 0x114))); } }' + NL)


def main():
    text = io.open(FILE, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    inserted = 0
    for tag, anchor in CASES:
        if ('trace] dsp ' + tag) in text:
            print('%s: already present' % tag)
            continue
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('%s: anchor not found' % tag)
        eol = text.find(nl, idx)
        if tag == 'setup':
            # NEVER insert between an if(...) and its '{': skip to the closing
            # brace of the callback-check block first (HANDOFF section 5)
            brace = text.find('}', text.find('return;', idx))
            eol = text.find(nl, brace)
        text = text[:eol + len(nl)] + body(tag).replace(NL, nl) + text[eol + len(nl):]
        inserted += 1
        print('%s: inserted' % tag)
    io.open(FILE, 'w', newline='').write(text)
    print('dispatch watches ok (%d inserted)' % inserted)


if __name__ == '__main__':
    sys.exit(main())
