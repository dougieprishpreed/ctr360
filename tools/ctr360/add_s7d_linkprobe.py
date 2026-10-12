#!/usr/bin/env python3
"""Session-7d: probe RenderBucket_LinkPrimRaw's OT entry + value.

d3->d4 proved the clobber happens inside RenderBucket_DispatchDrawInstPrim.
LinkPrimRaw is the only writer there that stores into an OT entry
(`*otEntry = RenderBucket_OTAddress(prim)`), so print the entry address, its
old value, the prim pointer and the new value; the address tells which
otRangeNormal/otRangeSecondary/instPlayerBase chain went wrong.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

BODY = (TAB + '{ static int s_lp = 0; if (sdata->frameCounter >= 199 && s_lp < 80) { s_lp++; '
        'Platform_Log("[trace] lp f=%d ot=%08x old=%08x prim=%08x val=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)otEntry, (unsigned)(u32)*otEntry, '
        '(unsigned)(u32)prim, (unsigned)(u32)RenderBucket_OTAddress(prim)); } }')


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    if 'trace] lp ' in text:
        print('lp: already present')
        return 0
    anchor = '\tRenderBucket_WritePackedWord(prim, CtrGpu_PackOTTag(*otEntry, lenWord));\n'
    idx = text.find(anchor)
    if idx < 0:
        idx = text.find(anchor.replace('\n', '\r\n'))
        anchor = anchor.replace('\n', '\r\n')
    if idx < 0:
        print('lp: anchor not found')
        return 1
    text = text[:idx + len(anchor)] + BODY.replace(NL, nl) + NL + text[idx + len(anchor):]
    io.open(RB, 'w', newline='').write(text)
    print('lp: inserted after the tag write')
    return 0


if __name__ == '__main__':
    sys.exit(main())
