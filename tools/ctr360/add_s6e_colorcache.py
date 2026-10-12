#!/usr/bin/env python3
"""Session-6e: probe RenderBucket_CopyScratchColorCache's copy bounds.

The w3/w4 watches narrowed the clobber to the first RBI entry's dispatch at
f=13 (inst 826f7300, mh 82742a8c), and the only whole-array write before the
switch is the color-cache copy:

    count = commandList[0];
    for (i = 0; i < count; i++) scratchColor[i] = colorLayout[i];

With the GTE fix the instances finally pass the bounds cull, so Execute runs
for the first time (pre-fix rbe ents=0) - and this copy is the prime suspect
for writing past the 1 KiB scratchpad. Probe prints the count and both
pointers for the first entries.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'

BODY = (TAB + '{ static int s_cc = 0; if (s_cc < 40) { s_cc++; '
        'Platform_Log("[trace] cc f=%d cnt=%u cmd=%08x col=%08x scr=%08x' + ESCN + '", '
        '(int)sdata->frameCounter, (unsigned)count, (unsigned)(u32)commandList, '
        '(unsigned)(u32)colorLayout, (unsigned)(u32)scratchColor); } }' + NL)

ANCHOR = '\tu32 count = commandList[0];'


def main():
    text = io.open(FILE, 'r', newline='').read()
    if 'trace] cc ' in text:
        print('cc: already present')
        return 0
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(ANCHOR)
    if idx < 0:
        raise SystemExit('cc: anchor not found')
    eol = text.find(nl, idx)
    text = text[:eol + len(nl)] + BODY.replace(NL, nl) + text[eol + len(nl):]
    io.open(FILE, 'w', newline='').write(text)
    print('cc: inserted after count load')
    return 0


if __name__ == '__main__':
    sys.exit(main())
