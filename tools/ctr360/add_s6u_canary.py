#!/usr/bin/env python3
"""Session-6u: canary probe after every dispatch (fresh tag `cnr`).

Instead of rewriting the drifted w3/w4 probes, insert a new probe right after
`RenderBucket_DispatchDrawFunc(&ctx);` that prints the dispatched instance, its
own next, and the Jit taken head's next. The line where the canary flips names
the culprit instance's draw.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')
ANCHOR = 'RenderBucket_DispatchDrawFunc(&ctx);'

BODY = (TAB + TAB + '{ static int s_cnr = 0; struct Instance *h0; if (sdata->frameCounter >= 199 && s_cnr < 400) '
        '{ s_cnr++; h0 = (struct Instance *)GAME_TRACKER->JitPools.instance.taken.first; '
        'Platform_Log("[trace] cnr f=%d inst=%08x next=%08x canary=%08x\n", '
        '(int)sdata->frameCounter, (unsigned)(u32)entry->inst, '
        '(unsigned)(u32)((struct Instance *)entry->inst)->next, '
        '(unsigned)(h0 ? (u32)h0->next : 0)); } }' + NL)


def main():
    text = io.open(RB, 'r', newline='').read()
    if 'trace] cnr ' in text:
        print('cnr: present')
        return 0
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(ANCHOR)
    if idx < 0:
        raise SystemExit('dispatch anchor not found')
    if text.find(ANCHOR, idx + 1) >= 0:
        raise SystemExit('dispatch anchor not unique')
    eol = text.find(nl, idx)
    text = text[:eol + len(nl)] + BODY.replace(NL, nl) + text[eol + len(nl):]
    io.open(RB, 'w', newline='').write(text)
    print('cnr: inserted after the dispatch call')
    return 0


if __name__ == '__main__':
    sys.exit(main())
