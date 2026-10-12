#!/usr/bin/env python3
"""Session-6h: bracket inside RenderBucket_DrawFunc_Normal.

The OT range is clean (ota/otd), so the pack write is a different write inside
the normal draw func. Four probes, each after a complete statement, name the
call that flips the watched field (big1 header[3].animtex = ptrMPK + 0x54 + 0x114):

  d1 - after RenderBucket_DispatchUncompressAnimationFrame
  d2 - after RenderBucket_ProjectPrim_Normal
  d3 - after RenderBucket_GetCommandTexture
  d4 - after the DispatchDrawInstPrim if-block (brace-skipped)
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'

ANCHORS = [
    ('d1', '\t\tdecoded = RenderBucket_DispatchUncompressAnimationFrame(ctx, command, stackIndex);', False),
    ('d2', '\t\t\tshouldDraw = RenderBucket_ProjectPrim_Normal(ctx, drawCommand, useRtps, reuseFirstVertex, &depthMac0);', False),
    ('d3', '\t\t\ttex = RenderBucket_GetCommandTexture(ctx, drawCommand, &isValidTexture);', False),
    ('d4', '\t\t\tif (RenderBucket_DispatchDrawInstPrim(ctx, drawCommand, tex, depthMac0) < 0)', True),
]


def body(tag):
    return (TAB + TAB + '{ static int s_' + tag + ' = 0; u8 *w; if (s_' + tag + ' < 60 && ((u32)sdata->ptrMPK >> 24) == 0x82) '
            '{ s_' + tag + '++; w = (u8 *)sdata->ptrMPK; '
            'Platform_Log("[trace] ' + tag + ' f=%d h3c=%08x' + ESCN + '", '
            '(int)sdata->frameCounter, (unsigned)(*(u32 *)(w + 0x54 + 0x114))); } }' + NL)


def main():
    text = io.open(FILE, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    inserted = 0
    for tag, anchor, skip_block in ANCHORS:
        if ('trace] ' + tag + ' ') in text:
            print('%s: already present' % tag)
            continue
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('%s: anchor not found' % tag)
        eol = text.find(nl, idx)
        if skip_block:
            # never insert between an if(...) and its '{': jump past the block
            brace = text.find('}', text.find('return;', idx))
            eol = text.find(nl, brace)
        text = text[:eol + len(nl)] + body(tag).replace(NL, nl) + text[eol + len(nl):]
        inserted += 1
        print('%s: inserted' % tag)
    io.open(FILE, 'w', newline='').write(text)
    print('draw-func watches ok (%d inserted)' % inserted)


if __name__ == '__main__':
    sys.exit(main())
