#!/usr/bin/env python3
"""Session-6m: re-gate the instance-list walk probes (q1/q2/q6/q8) to f>=199.

At f=205 the QueueLevInstances walk visits the new `spawn` instance (mid=192)
and then hangs on the next entry before QueueDraw's qd1 site. q1 (list head),
q2 (per instance), q6/q8 (non-level list) are all capped out; re-gating them to
frame 199 shows the list contents and the exact entry the walk dies on.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')


def main():
    text = io.open(FILE, 'r', newline='').read()
    changed = 0
    for tag, old, new in (
        ('q7', 'if (s_q7 < 60)', 'if (sdata->frameCounter >= 199 && s_q7 < 400)'),
        ('q1', 'if (s_q1 < 24)', 'if (sdata->frameCounter >= 199 && s_q1 < 400)'),
        ('q2', 'if (s_q2 < 48)', 'if (sdata->frameCounter >= 199 && s_q2 < 400)'),
        ('q6', 'if (s_q6 < 48)', 'if (sdata->frameCounter >= 199 && s_q6 < 400)'),
        ('q8', 'if (s_q8 < 60)', 'if (sdata->frameCounter >= 199 && s_q8 < 400)'),
    ):
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
            print('%s: re-gated' % tag)
        else:
            print('%s: condition not found' % tag)
    io.open(FILE, 'w', newline='').write(text)
    print('list-walk re-gate ok (%d change(s))' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
