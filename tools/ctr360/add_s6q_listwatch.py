#!/usr/bin/env python3
"""Session-6q: list watch, corrected anchors.

Fixes the failed session-6p attempt:
  * `RenderBucket_QueueAllInstances` is DEFINED in MainFrame_RenderFrame.c:713,
    not in RenderBucket_QueueExecute.c — put the global there.
  * the session-6o vw2 probe had `f=%s` (an int arg read as a string pointer);
    fix it to `f=%d` and have it store the list address in the global.
Then add the five phase probes (pw ...) that read the global's target words.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')
MF = os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame.c')
RF = os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainFrame_RenderFrame.c')

PHASE_BODY = (TAB + '{ extern u32 g_ctr360VwList; static int s_pw = 0; u32 *pv; '
              'if (sdata->frameCounter >= 199 && s_pw < 400) { s_pw++; pv = (u32 *)g_ctr360VwList; '
              'Platform_Log("[trace] pw %s f=%%d lst=%%08x w0=%%08x w1=%%08x w2=%%08x' + ESCN + '", '
              '(int)sdata->frameCounter, (unsigned)(u32)pv, '
              '(unsigned)(pv ? pv[0] : 0), (unsigned)(pv ? pv[1] : 0), (unsigned)(pv ? pv[2] : 0)); } }' + NL)


def insert_after(path, anchor, body, present_tag, skip_block=False):
    text = io.open(path, 'r', newline='').read()
    if present_tag in text:
        print('%s: present' % present_tag)
        return
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit('anchor not found: %s' % anchor)
    if skip_block:
        idx = text.find('}', text.find('continue;', idx))
    eol = text.find(nl, idx)
    text = text[:eol + len(nl)] + body.replace(NL, nl) + text[eol + len(nl):]
    io.open(path, 'w', newline='').write(text)
    print('%s: inserted' % present_tag)


def main():
    # 1. the walk probe: fix f=%s -> f=%d, add the global store + extern decl
    text = io.open(RB, 'r', newline='').read()
    if 'g_ctr360VwList = (u32)visInstSrc;' not in text:
        old = 'Platform_Log("[trace] vw2 f=%s pl=%d'
        if old not in text:
            raise SystemExit('vw2 probe not found')
        text = text.replace(old, 'Platform_Log("[trace] vw2 f=%d pl=%d')
        old2 = '{ static int s_vw2 = 0; if (sdata->frameCounter >= 199 && s_vw2 < 400) { s_vw2++; '
        if old2 not in text:
            raise SystemExit('vw2 prologue not found')
        text = text.replace(old2, '{ extern u32 g_ctr360VwList; static int s_vw2 = 0; '
                                  'if (sdata->frameCounter >= 199 && s_vw2 < 400) { s_vw2++; '
                                  'g_ctr360VwList = (u32)visInstSrc; ')
        io.open(RB, 'w', newline='').write(text)
        print('vw2: fixed + global store added')

    # 2. the global definition (file scope, before QueueAllInstances)
    text = io.open(RF, 'r', newline='').read()
    if 'u32 g_ctr360VwList = 0;' not in text:
        nl = '\r\n' if '\r\n' in text else NL
        marker = 'void RenderBucket_QueueAllInstances(struct GameTracker *gGT)'
        idx = text.find(marker)
        if idx < 0:
            raise SystemExit('QueueAllInstances definition not found')
        text = text[:idx] + ('u32 g_ctr360VwList = 0;' + NL).replace(NL, nl) + text[idx:]
        io.open(RF, 'w', newline='').write(text)
        print('global: defined in MainFrame_RenderFrame.c')

    # 3. phase probes
    insert_after(MF, 'Platform_Log("[trace] frame: pre-Hub_Main f=%d', PHASE_BODY % 'pre', 'trace] pw pre')
    insert_after(RF, 'Platform_Log("[trace] rf10 f=%d', PHASE_BODY % 'rf10', 'trace] pw rf10')
    insert_after(RF, 'Platform_Log("[trace] rf11 f=%d', PHASE_BODY % 'rf11', 'trace] pw rf11')
    insert_after(RF, 'Platform_Log("[trace] rf14 f=%d', PHASE_BODY % 'rf14', 'trace] pw rf14')
    insert_after(RF, 'Platform_Log("[trace] rf19 f=%d', PHASE_BODY % 'rf19', 'trace] pw rf19')
    print('session-6q ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
