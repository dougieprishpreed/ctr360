#!/usr/bin/env python3
"""Session-7i: print the range + depth feeding each normal OT entry.

lp showed the draw's OT link writes landing on model-pack pointers
(0x8270xxxx) instead of the OT pool. The entry comes from
RenderBucket_GetNormalOTEntry(activeRange, depthMac0) = activeRange + (MAC0>>17);
this probe prints all three so the wild entry can be attributed to either the
range or the depth bin (a huge bin implies a bad MAC0 from the projection).
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

ANCHOR = (TAB + 'return RenderBucket_DrawInstPrim_NormalAtOTEntry(ctx, command, tex, '
          'RenderBucket_GetNormalOTEntry(activeRange, depthMac0));')
BODY = (TAB + '{ static int s_or = 0; if (sdata->frameCounter >= 199 && s_or < 60) { s_or++; '
        'Platform_Log("[trace] or f=%d cmd=%08x r=%08x d=%08x e=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)command, (unsigned)activeRange, (unsigned)depthMac0, '
        '(unsigned)(u32)RenderBucket_GetNormalOTEntry(activeRange, depthMac0)); } }')


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    if 'trace] or ' in text:
        print('or: already present')
        return 0
    idx = text.find(ANCHOR + '\n')
    if idx < 0:
        idx = text.find(ANCHOR + '\r\n')
    if idx < 0:
        print('or: anchor not found')
        return 1
    text = text[:idx] + BODY.replace(NL, nl) + nl + text[idx:]
    io.open(RB, 'w', newline='').write(text)
    print('or: inserted before the AtOTEntry return')
    return 0


if __name__ == '__main__':
    sys.exit(main())
