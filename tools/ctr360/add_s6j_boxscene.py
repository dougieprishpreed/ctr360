#!/usr/bin/env python3
"""Session-6j: probe the GHOST thread-bucket walk in CS_BoxScene_InstanceSplitLines.

The 420 s run wedged at f=205 between the rf10 (render-in) and rf10b probes,
i.e. inside RenderAllBoxSceneSplitLines -> CS_BoxScene_InstanceSplitLines, which
is a bare

    t = GAME_TRACKER->threadBuckets[GHOST].thread;
    do { t->inst->vertSplit = split; t = t->siblingThread; } while (t != NULL);

loop - unbounded, so a cyclic siblingThread list (or a bad inst pointer) hangs
the frame. The probe prints each visited node (capped), which exposes the cycle.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', '233', 'CS_BoxScene.c')

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'

BODY = (TAB + TAB + '{ static int s_csb = 0; if (s_csb < 60) { s_csb++; '
        'Platform_Log("[trace] csb f=%d t=%08x sib=%08x inst=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)(u32)t, (unsigned)(u32)t->siblingThread, '
        '(unsigned)(u32)t->inst); } }' + NL)

ANCHOR = '\t\tt->inst->vertSplit = split;'


def main():
    text = io.open(FILE, 'r', newline='').read()
    if 'trace] csb ' in text:
        print('csb: already present')
        return 0
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(ANCHOR)
    if idx < 0:
        raise SystemExit('csb: anchor not found')
    text = text[:idx] + BODY.replace(NL, nl) + text[idx:]
    io.open(FILE, 'w', newline='').write(text)
    print('csb: inserted before vertSplit write')
    return 0


if __name__ == '__main__':
    sys.exit(main())
