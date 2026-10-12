#!/usr/bin/env python3
"""Session-6y: bracket the self-clobber inside the dispatch.

cnr showed the drawn instance's OWN `next` becomes 0x00ef0458 during its
dispatch (dsp case0 -> cnr). The dispatch runs CopyScratchColorCache, then
RenderBucket_RunInstanceSetupCallback, then the draw func. Two probes (cb1
after the color-cache copy, cb2 after the setup-callback block) print the
instance's next so the flip names the writer.
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
    return (TAB + '{ static int s_' + tag + ' = 0; if (sdata->frameCounter >= 199 && s_' + tag + ' < 400) '
            '{ s_' + tag + '++; Platform_Log("[trace] ' + tag + ' f=%d inst=%08x next=%08x\n", '
            '(int)sdata->frameCounter, (unsigned)(u32)ctx->inst, '
            '(unsigned)(u32)((struct Instance *)ctx->inst)->next); } }' + NL)


def insert_after(path, anchor, probe_body, tag, skip_block=False):
    text = io.open(path, 'r', newline='').read()
    if ('trace] ' + tag + ' ') in text:
        print('%s: present' % tag)
        return
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit('anchor not found: %s' % anchor)
    if skip_block:
        idx = text.find('}', text.find('return;', idx))
    eol = text.find(nl, idx)
    text = text[:eol + len(nl)] + probe_body.replace(NL, nl) + text[eol + len(nl):]
    io.open(path, 'w', newline='').write(text)
    print('%s: inserted' % tag)


def main():
    insert_after(RB, 'RenderBucket_CopyScratchColorCache(ctx);', body('cb1'), 'cb1')
    insert_after(RB, 'if (RenderBucket_RunInstanceSetupCallback(ctx) == 0)', body('cb2'), 'cb2', skip_block=True)
    print('session-6y ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
