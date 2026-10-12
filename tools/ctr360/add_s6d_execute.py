#!/usr/bin/env python3
"""Session-6d: find which instance's draw writes the clobbered field.

The w2 step watches bracketed the write to RenderBucket_ExecuteAllInstances ->
RenderBucket_Execute's per-entry loop (render step rf13->rf14). This script
adds two probes inside that loop in the compiled tree:

  w3 - after RenderBucket_PrepareDrawContext, before the dispatch (pre-state)
  w4 - after RenderBucket_DispatchDrawFunc (post-state)

Each prints the frame, the entry, its instance and header, and the watched
field (big1 header[3].animtex = ptrMPK + 0x54 + 0x114). The entry whose
dispatch flips the field names the writer. Escapes are built from chr() codes.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'


def body(tag):
    return (TAB + TAB + '{ static int s_' + tag + ' = 0; u8 *w; if (s_' + tag + ' < 60 && ((u32)sdata->ptrMPK >> 24) == 0x82) '
            '{ s_' + tag + '++; w = (u8 *)sdata->ptrMPK; '
            'Platform_Log("[trace] ' + tag + ' f=%d ent=%08x inst=%08x mh=%08x h3c=%08x' + ESCN + '", '
            '(int)sdata->frameCounter, (unsigned)(u32)entry, (unsigned)(u32)entry->inst, (unsigned)(u32)ctx.mh, '
            '(unsigned)(*(u32 *)(w + 0x54 + 0x114))); } }' + NL)


def main():
    text = io.open(FILE, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL

    pre_anchor = '\t\tif (RenderBucket_PrepareDrawContext(&ctx, entry->inst, entry->instPlayerBase, param_2) == 0)'
    disp_anchor = '\t\tRenderBucket_DispatchDrawFunc(&ctx);'

    if 'trace] w3 ' not in text:
        idx = text.find(pre_anchor)
        if idx < 0:
            raise SystemExit('w3: prepare anchor not found')
        # insert after the closing brace of the `if (...) { continue; }` block
        brace = text.find('}', text.find('continue;', idx))
        eol = text.find(nl, brace)
        text = text[:eol + len(nl)] + body('w3').replace(NL, nl) + text[eol + len(nl):]
        print('w3: inserted after prepare')
    else:
        print('w3: already present')

    if 'trace] w4 ' not in text:
        idx = text.find(disp_anchor)
        if idx < 0:
            raise SystemExit('w4: dispatch anchor not found')
        eol = text.find(nl, idx)
        text = text[:eol + len(nl)] + body('w4').replace(NL, nl) + text[eol + len(nl):]
        print('w4: inserted after dispatch')
    else:
        print('w4: already present')

    io.open(FILE, 'w', newline='').write(text)
    print('execute-loop watches ok')


if __name__ == '__main__':
    sys.exit(main())
