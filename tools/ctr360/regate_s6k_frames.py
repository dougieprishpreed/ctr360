#!/usr/bin/env python3
"""Session-6k: re-gate the phase probes so they fire AT the wedge frame.

The w2/rf/csb probes all capped out long before f=205, so the 420 s log could
only say "the hang is inside MainFrame_RenderFrame at f=205". This script
rewrites their conditions to fire from frame 199 on (a window, not a cap), so
one 300 s run brackets the hang to a single render step:

  w2 rf10b..rf19  - the render steps (MainFrame_RenderFrame.c)
  csb             - the GHOST thread walk (CS_BoxScene.c)
  w3/w4           - the Execute loop per entry (RenderBucket_QueueExecute.c)
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)


def regate(path, old_cond, new_cond):
    text = io.open(path, 'r', newline='').read()
    n = text.count(old_cond)
    if n == 0:
        print('%s: no "%s" occurrences' % (os.path.basename(path), old_cond[:40]))
        return 0
    text = text.replace(old_cond, new_cond)
    io.open(path, 'w', newline='').write(text)
    print('%s: %d probe(s) re-gated' % (os.path.basename(path), n))
    return n


def main():
    changed = 0

    rf = os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c')
    for tag in ('rf10b', 'rf11', 'rf12', 'rf13', 'rf14', 'rf15', 'rf16', 'rf18', 'rf19'):
        old = 'if (s_w2 < 40 && ((u32)sdata->ptrMPK >> 24) == 0x82)'
        new = 'if (sdata->frameCounter >= 199 && ((u32)sdata->ptrMPK >> 24) == 0x82)'
        changed += regate(rf, old, new)

    box = os.path.join(ROOT, 'build-360', 'gen', 'game', '233', 'CS_BoxScene.c')
    changed += regate(box, 'if (s_csb < 60)', 'if (sdata->frameCounter >= 199)')

    ex = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')
    for tag in ('w3', 'w4'):
        old = 'if (s_%s < 60 && ((u32)sdata->ptrMPK >> 24) == 0x82)' % tag
        new = 'if (sdata->frameCounter >= 199 && ((u32)sdata->ptrMPK >> 24) == 0x82)'
        changed += regate(ex, old, new)

    print('re-gate ok (%d probe line(s))' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
