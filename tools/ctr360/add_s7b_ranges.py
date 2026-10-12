#!/usr/bin/env python3
"""Session-7b: probe the OT ranges + prim cursor around the mirrored dispatch.

d1..d4 are clean through the whole plain draw; the clobber lands between the
last d4 and cnr, i.e. in the mirror/reflection tail (DrawSpecialMirroredPass
-> DispatchDrawInstPrimAtRange with ctx->idpp->otRangeSecondary, then the
final DispatchDrawInstPrimAtRange with otRangeNormal). This probe prints the
dispatched instance's `next` plus both OT ranges and the prim cursor at those
two call sites.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')


def body(tag):
    return (TAB + '{ static int s_pp = 0; if (sdata->frameCounter >= 199 && s_pp < 600) { s_pp++; '
            'Platform_Log("[trace] pp ' + tag + ' f=%d inst=%08x next=%08x rn=%08x rs=%08x prim=%08x' + ESCN + '", '
            '(int)sdata->frameCounter, (unsigned)(u32)ctx->inst, '
            '(unsigned)(u32)((struct Instance *)ctx->inst)->next, '
            '(unsigned)(u32)ctx->idpp->otRangeNormal, (unsigned)(u32)ctx->idpp->otRangeSecondary, '
            '(unsigned)(u32)ctx->primMem->cursor); } }')


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    changed = 0
    # site 1: after the mirrored-range dispatch inside DrawSpecialMirroredPass
    if 'trace] pp mir' not in text:
        anchor = '\tret = RenderBucket_DispatchDrawInstPrimAtRange(ctx, command, tex, ctx->idpp->otRangeSecondary, depthMac0);\n'
        idx = text.find(anchor)
        if idx < 0:
            idx = text.find(anchor.replace('\n', '\r\n'))
            anchor = anchor.replace('\n', '\r\n')
        if idx < 0:
            print('mir: anchor not found')
        else:
            text = text[:idx + len(anchor)] + body('mir').replace(NL, nl) + NL + text[idx + len(anchor):]
            changed += 1
            print('mir: inserted')
    # site 2: after the normal-range dispatch block (end of the mirrored helper)
    if 'trace] pp nrm' not in text:
        anchor = '\tif (RenderBucket_DispatchDrawInstPrimAtRange(ctx, command, tex, ctx->idpp->otRangeNormal, depthMac0) < 0)\n'
        idx = text.find(anchor)
        if idx < 0:
            idx = text.find(anchor.replace('\n', '\r\n'))
        if idx < 0:
            print('nrm: anchor not found')
        else:
            brace = text.find('}', text.find('return -1;', idx))
            eol = text.find('\n', brace)
            text = text[:eol + 1] + body('nrm').replace(NL, nl) + NL + text[eol + 1:]
            changed += 1
            print('nrm: inserted')
    io.open(RB, 'w', newline='').write(text)
    print('session-7b ok (%d inserts)' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
