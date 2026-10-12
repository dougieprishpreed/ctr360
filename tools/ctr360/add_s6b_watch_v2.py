#!/usr/bin/env python3
"""Session-6b watch probe v2 (fixed): offset-based, dumps three header fields.

Fixes the v2 attempt, which wrote a literal newline into the C string literal
(the generator's escape handling collapsed `\n`); that broke MainFrame.c and
failed the build. This version builds every escape from chr() codes:

    NL    = chr(10)            - line separator in the generated C file
    ESCN  = chr(92) + 'n'      - the two characters backslash+n for the C string

It first removes any broken wch probe block (the probe line plus a stray
continuation line starting with `", (`), then inserts a clean probe after the
original anchor line at each site:

    preamble   - MainFrame.c, after the `frame: pre-Hub_Main` probe
    render-in  - MainFrame_RenderFrame.c, after the `rf10` probe
    render-out - MainFrame_RenderFrame.c, after the `rf19` probe

The watched slot is `ModelHeader.animtex` of the big1 model's header[3], at a
fixed offset inside the current model pack (allocation-independent):

    big1 model = sdata->ptrMPK + 0x54
    header[3]  = model + 0x18 + 3*0x40  ->  fields at +0x34/+0x38/+0x3C
    watched    = ptrMPK + 0x160/0x164/0x168 (plus header[0].animtex at +0x54+0x3C)
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'


def body(tag):
    # C89: declare `w` first in the block, statements after. The arena guard
    # keeps the probe from faulting before the model pack is allocated (the
    # unguarded read wedged the guest at f=1).
    return (TAB + '{ static int s_wch = 0; u8 *w; if (s_wch < 300 && ((u32)sdata->ptrMPK >> 24) == 0x82) '
            '{ s_wch++; w = (u8 *)sdata->ptrMPK; '
            'Platform_Log("[trace] wch ' + tag + ' f=%d mpk=%08x h0=%08x h3a=%08x h3b=%08x h3c=%08x' + ESCN + '", '
            '(int)sdata->frameCounter, (unsigned)(u32)sdata->ptrMPK, (unsigned)(*(u32 *)(w + 0x54 + 0x3c)), '
            '(unsigned)(*(u32 *)(w + 0x54 + 0x10c)), (unsigned)(*(u32 *)(w + 0x54 + 0x110)), '
            '(unsigned)(*(u32 *)(w + 0x54 + 0x114))); } }' + NL)


SITES = [
    ('preamble', os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame.c'),
     'Platform_Log("[trace] frame: pre-Hub_Main f=%d'),
    ('render-in', os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf10 f=%d'),
    ('render-out', os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf19 f=%d'),
]


def main():
    for tag, path, anchor in SITES:
        text = io.open(path, 'r', newline='').read()
        nl = '\r\n' if '\r\n' in text else NL
        clean = body(tag).replace(NL, nl)

        # 1. drop any previous (possibly broken) wch probe for this tag
        lines = text.split(nl)
        keep = []
        i = 0
        dropped = 0
        while i < len(lines):
            if ('static int s_wch' in lines[i]) and ('trace] wch ' + tag in lines[i]):
                dropped += 1
                # drop the probe line, and a stray continuation line if the
                # previous generation split the C string across lines
                if i + 1 < len(lines) and lines[i + 1].lstrip().startswith('", '):
                    i += 2
                    continue
                i += 1
                continue
            keep.append(lines[i])
            i += 1
        text = nl.join(keep)

        # 2. insert the clean probe right after the anchor's line
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('%s: anchor not found in %s' % (tag, path))
        eol = text.find(nl, idx)
        text = text[:eol + len(nl)] + clean + text[eol + len(nl):]
        io.open(path, 'w', newline='').write(text)
        print('%s: cleaned %d, inserted clean probe' % (tag, dropped))

    print('watch probes v2-fixed ok')


if __name__ == '__main__':
    sys.exit(main())
