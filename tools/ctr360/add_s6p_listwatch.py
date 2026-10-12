#!/usr/bin/env python3
"""Session-6p: remember the PVS list address in the walk, watch it at phases.

cDC->visInstSrc is NULL outside the walk, so the phase watches could not see the
list. This patch: (1) the walk probe stores the list address in a global,
(2) five phase probes print that global's target words, gated to f>=199.
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

GLOBAL_DECL = 'u32 g_ctr360VwList = 0;' + NL

WALK_BODY = (TAB + '{ static int s_vw3 = 0; if (sdata->frameCounter >= 199 && s_vw3 < 400) { s_vw3++; '
             'g_ctr360VwList = (u32)visInstSrc; '
             'Platform_Log("[trace] vw3 f=%s pl=%d vs=%08x w0=%08x w1=%08x w2=%08x' + ESCN + '", '
             '(int)sdata->frameCounter, player, (unsigned)(u32)visInstSrc, '
             '(unsigned)visInstSrc[0], (unsigned)visInstSrc[1], (unsigned)visInstSrc[2]); } }' + NL)

PHASE_BODY = (TAB + '{ extern u32 g_ctr360VwList; static int s_pw = 0; u32 *pv; '
              'if (sdata->frameCounter >= 199 && s_pw < 400) { s_pw++; pv = (u32 *)g_ctr360VwList; '
              'Platform_Log("[trace] pw %s f=%%d lst=%%08x w0=%%08x w1=%%08x w2=%%08x' + ESCN + '", '
              '(int)sdata->frameCounter, (unsigned)(u32)pv, '
              '(unsigned)(pv ? pv[0] : 0), (unsigned)(pv ? pv[1] : 0), (unsigned)(pv ? pv[2] : 0)); } }' + NL)


def insert_after(path, anchor, body, present_tag):
    text = io.open(path, 'r', newline='').read()
    if present_tag in text:
        print('%s: present' % present_tag)
        return text
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit('anchor not found: %s' % anchor)
    if 'continue;' in anchor:
        idx = text.find('}', text.find('continue;', idx))
    eol = text.find(nl, idx)
    text = text[:eol + len(nl)] + body.replace(NL, nl) + text[eol + len(nl):]
    io.open(path, 'w', newline='').write(text)
    print('%s: inserted' % present_tag)
    return text


def main():
    text = io.open(RB, 'r', newline='').read()
    if 'g_ctr360VwList = 0;' not in text:
        marker = 'void RenderBucket_QueueAllInstances('
        idx = text.find(marker)
        if idx < 0:
            raise SystemExit('QueueAllInstances not found')
        # put the definition just before the function (a file-scope global)
        nl = '\r\n' if '\r\n' in text else NL
        text = text[:idx] + (GLOBAL_DECL).replace(NL, nl) + text[idx:]
        io.open(RB, 'w', newline='').write(text)
        print('global: added')
    insert_after(RB, 'if (visInstSrc == 0)', WALK_BODY, 'trace] vw3 ')
    insert_after(MF, 'Platform_Log("[trace] frame: pre-Hub_Main f=%d', PHASE_BODY % 'pre', 'trace] pw pre')
    insert_after(RF, 'Platform_Log("[trace] rf10 f=%d', PHASE_BODY % 'rf10', 'trace] pw rf10')
    insert_after(RF, 'Platform_Log("[trace] rf11 f=%d', PHASE_BODY % 'rf11', 'trace] pw rf11')
    insert_after(RF, 'Platform_Log("[trace] rf14 f=%d', PHASE_BODY % 'rf14', 'trace] pw rf14')
    insert_after(RF, 'Platform_Log("[trace] rf19 f=%d', PHASE_BODY % 'rf19', 'trace] pw rf19')
    print('session-6p ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
