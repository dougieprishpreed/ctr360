#!/usr/bin/env python3
"""Session-6b watch probe: bracket the write that clobbers a model header.

After the GTE `PAIR` endianness fix the guest wedges at f=14 inside
CTR_CycleTex_AllModels: `big1`'s header 3 (`hdr=82705f24`, the field
`ModelHeader.animtex` at +0x3C = `0x82705f60`) reads 0 at f=13 and a garbage
runtime pointer (0x00ed71e0) at f=14. The value does not exist anywhere in the
cooked image, so something writes it during f=13's render or the f=14 preamble.

This script drops a `wch` probe at three per-frame points (tree only, HANDOFF
section 6) so one 60 s run brackets the writer to a phase:

  preamble   - MainFrame.c, before Hub_Main runs
  render-in  - MainFrame_RenderFrame.c, at the rf10 render start
  render-out - MainFrame_RenderFrame.c, at the rf19 render end

Each line prints the frame counter and the raw u32 at 0x82705f60. The address
is the allocation the last three runs produced (big1 model at 0x82705e4c,
headers at 0x82705e64 + 3*0x40); the port's allocation order is deterministic,
so a fixed address is fine for this diagnostic. Remove the probes once the
writer is identified.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BODY = ('\t{ static int s_wch = 0; if ((s_wch++ %% 60) == 0) { Platform_Log("[trace] wch %s f=%%d v=%%08x\\n", '
        '(int)sdata->frameCounter, (unsigned)(*(volatile u32 *)0x82705f60)); } }\n')

SITES = [
    ('preamble', os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame.c'),
     'Platform_Log("[trace] frame: pre-Hub_Main f=%d\\n"'),
    ('render-in', os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf10 f=%d\\n"'),
    ('render-out', os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c'),
     'Platform_Log("[trace] rf19 f=%d\\n"'),
]


def main():
    changed = 0
    for tag, path, anchor in SITES:
        text = io.open(path, 'r', newline='').read()
        if 'trace] wch ' + tag in text:
            print('%s: already present, skipped' % tag)
            continue
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('%s: anchor not found in %s' % (tag, path))
        # the anchors all sit on a complete one-line probe statement: insert
        # directly after that line (HANDOFF section 5 rule)
        eol = text.find('\n', idx)
        nl = '\r\n' if '\r\n' in text else '\n'
        text = text[:eol + 1] + (BODY % tag).replace('\n', nl) + text[eol + 1:]
        io.open(path, 'w', newline='').write(text)
        changed += 1
        print('%s: inserted after %s' % (tag, os.path.basename(path)))
    print('watch probes ok (%d change(s))' % changed)


if __name__ == '__main__':
    sys.exit(main())
