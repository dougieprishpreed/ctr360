#!/usr/bin/env python3
"""Session-6i: (a) make the d1..d4 watches print only when the field is nonzero,
(b) fix the remaining host-order read of ModelHeader.scale.z.

(a) The d1..d4 probes capped at 60 lines each and never saw the flip, so the
    clobbering command is past the cap (or on the color-only early path).
    Printing only nonzero values turns the log into "the first command that
    wrote it", whatever the cap. The arena guard stays FIRST so the probe can
    never fault.

(b) RenderBucket_BuildM3x3 reads the model scale through
    RenderBucket_ReadPackedWord(&mh->scale.x) (little-endian, matching the
    cooked image) but takes the z component with a plain struct read
    `(u16)mh->scale.z`, which is host-order: on the big-endian 360 that is the
    byte-swapped scale (qd4 showed m22 = 0xffffb534 for scale.z = 0x34b5).
    Route it through CTR_ReadU16LE like the x/y components.

Applies (b) to both the repo and the compiled tree.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TREE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')
REPO = os.path.join(ROOT, 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

NL = chr(10)
TAB = chr(9)

OLD_Z = 'CTC2((u16)mh->scale.z >> scaleZShift, 20);'
NEW_Z_LINES = [
    '// scale.z stays little-endian in the cooked image (same as the x/y',
    '// packed word); a plain struct read would byte-swap it on BE.',
    'CTC2((u32)CTR_ReadU16LE(&mh->scale.z) >> scaleZShift, 20);',
]

WATCH_FIELD = '(*(u32 *)(((u8 *)sdata->ptrMPK) + 0x54 + 0x114) != 0)'


def main():
    changed = 0

    # (a) probes print only on a nonzero watched field (arena guard first)
    text = io.open(TREE, 'r', newline='').read()
    for tag in ('d1', 'd2', 'd3', 'd4'):
        old = 'if (s_%s < 60 && ((u32)sdata->ptrMPK >> 24) == 0x82)' % tag
        new = 'if ((((u32)sdata->ptrMPK >> 24) == 0x82) && %s)' % WATCH_FIELD
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
            print('%s: prints only nonzero' % tag)
        else:
            print('%s: condition not found (already changed?)' % tag)
    io.open(TREE, 'w', newline='').write(text)

    # (b) scale.z little-endian read, repo + tree
    for path in (TREE, REPO):
        t = io.open(path, 'r', newline='').read()
        if 'CTR_ReadU16LE(&mh->scale.z)' in t:
            print('%s: scale.z already fixed' % os.path.basename(path))
            continue
        if OLD_Z not in t:
            print('%s: scale.z anchor not found' % os.path.basename(path))
            continue
        nl = '\r\n' if '\r\n' in t else NL
        new = nl.join(TAB + ln for ln in NEW_Z_LINES)
        t = t.replace(TAB + OLD_Z, new, 1)
        io.open(path, 'w', newline='').write(t)
        changed += 1
        print('%s: scale.z now read little-endian' % os.path.basename(path))

    print('ok (%d change(s))' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
