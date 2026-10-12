#!/usr/bin/env python3
"""Session-7a: re-point the in-draw probes at the instance's own `next`.

cb1/cb2 (session-6y) proved the setup callback does NOT write the clobbered
field; cnr shows the draw func does (inst=826f7f08: next 826f6d50 before the
draw, 00ef0458 after). The d1..d4 probes already bracket DrawFunc_Normal's
steps (uncompress -> ProjectPrim -> GetCommandTexture -> DispatchDrawInstPrim),
but they watch the old pack field; rewrite them to print the instance's next.
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

BODY = (TAB + '{ static int s_d%d = 0; if (sdata->frameCounter >= 199 && s_d%d < 400) { s_d%d++; '
        'Platform_Log("[trace] d%d f=%%d inst=%%08x next=%%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)ctx->inst, '
        '(unsigned)(u32)((struct Instance *)ctx->inst)->next); } }' + NL)


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    changed = 0
    for i in (1, 2, 3, 4):
        pat = re.compile(r'^\t+\{ static int s_d' + str(i) + r' = 0;.*trace\] d' + str(i) + r' .*\}\r?$', re.M)
        m = pat.search(text)
        if not m:
            print('d%d: not found' % i)
            continue
        text = text[:m.start()] + (BODY % (i, i, i, i)).replace(NL, nl).rstrip(nl) + text[m.end():]
        changed += 1
        print('d%d: rewritten' % i)
    io.open(RB, 'w', newline='').write(text)
    print('session-7a ok (%d rewrites)' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
