#!/usr/bin/env python3
"""Session-6l: re-gate the qd* probes to fire every call from f=199.

The phase probes put the f=205 hang inside RenderBucket_QueueAllInstances; the
qd* probes capped out long before, so the log only shows "the walk got as far
as f=204 mid=193". This re-gates qd1/qd2/qd3/qd4/qd6/qi to fire on every call
from frame 199 (capped at 200 lines each) so the LAST line names the instance
whose QueueDraw hangs.
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')


def main():
    text = io.open(FILE, 'r', newline='').read()
    changed = 0

    # qd1/qd2/qd3: `if (s_qdN < 24)`
    for tag in ('qd1', 'qd2', 'qd3'):
        old = 'if (s_%s < 24)' % tag
        new = 'if (sdata->frameCounter >= 199 && s_%s < 200)' % tag
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
            print('%s: re-gated' % tag)

    # qd4/qd6: `(s_qdN++ % 30) == 0`
    for tag in ('qd4', 'qd6'):
        old = '(s_%s++ %% 30) == 0' % tag
        new = 'sdata->frameCounter >= 199 && s_%s++ < 200' % tag
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
            print('%s: re-gated' % tag)

    # qi: `(gameMode1 & 0x2000) && !(gameMode1 & 0x40000000) && s_qi < 150`
    old = 's_qi < 150'
    new = 'sdata->frameCounter >= 199 && s_qi < 200'
    if old in text:
        text = text.replace(old, new, 1)
        changed += 1
        print('qi: re-gated')

    io.open(FILE, 'w', newline='').write(text)
    print('qd re-gate ok (%d change(s))' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
