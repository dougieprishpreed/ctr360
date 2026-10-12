#!/usr/bin/env python3
"""Session-7j: read MFC2(24) at the gte_stopz site.

or showed depthMac0 (GTE reg 24 = MAC0) has a wild high 24 bits and a low byte
equal to the prim command byte. Print MFC2(24) directly next to the local.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

ANCHOR = 'gte_stopz(&depthMac0);'
BODY = ('{ static int s_mf = 0; if (sdata->frameCounter >= 199 && s_mf < 40) { s_mf++; '
        'Platform_Log("[trace] mf f=%d cmd=%08x mfc=%08x loc=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)command, (unsigned)MFC2(24), '
        '(unsigned)depthMac0); } }')


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else chr(10)
    if 'trace] mf ' in text:
        print('mf: already present')
        return 0
    idx = text.find(ANCHOR)
    if idx < 0:
        print('mf: anchor not found')
        return 1
    eol = text.find(nl, idx) + len(nl)
    text = text[:eol] + '\t' + BODY + nl + text[eol:]
    io.open(RB, 'w', newline='').write(text)
    print('mf: inserted after gte_stopz')
    return 0


if __name__ == '__main__':
    sys.exit(main())
