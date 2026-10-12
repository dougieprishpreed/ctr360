#!/usr/bin/env python3
"""Session-6t: per-dispatch canary on the Jit taken list.

The spawn (model 0xC0) is never queued, so its `next` is clobbered by another
instance's draw. This rewrites the session-6d w3/w4 probes in
RenderBucket_Execute's loop to print, for every dispatched entry, the instance,
its own next, and the taken head's next (the canary), gated to f>=199.
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

BODY = (TAB + '{ static int s_%s = 0; struct Instance *h0; if (sdata->frameCounter >= 199 && s_%s < 400) '
        '{ s_%s++; h0 = (struct Instance *)GAME_TRACKER->JitPools.instance.taken.first; '
        'Platform_Log("[trace] %s f=%%d inst=%%08x next=%%08x canary=%%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)entry->inst, '
        '(unsigned)(u32)((struct Instance *)entry->inst)->next, '
        '(unsigned)(h0 ? (u32)h0->next : 0)); } }' + NL)


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    changed = 0
    for tag, pat_src in (('w3', r'^\t\{ static int s_w3 = 0;.*trace\] w3 .*\}$'),
                         ('w4', r'^\t\{ static int s_w4 = 0;.*trace\] w4 .*\}$')):
        pat = re.compile(pat_src.replace(r'\}$', r'\}\r?$'), re.M)
        m = pat.search(text)
        if not m:
            print('%s: not found' % tag)
            continue
        text = text[:m.start()] + (BODY % (tag, tag, tag, tag)).replace(NL, nl).rstrip(nl) + text[m.end():]
        changed += 1
        print('%s: rewritten' % tag)
    io.open(RB, 'w', newline='').write(text)
    print('session-6t ok (%d rewrites)' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
