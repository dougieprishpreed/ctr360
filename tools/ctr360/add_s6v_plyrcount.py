#!/usr/bin/env python3
"""Session-6v: dump the instance-pool stride vs the walk's player count.

RenderBucket_InstancePlayerBase strides the per-player view by
sizeof(InstDrawPerPlayer) (0x88) and the pool item is
sizeof(Instance) + 0x88 * numPlyrCurrGame, so the walk's player count MUST
match the count used at JitPool_Init. If the cutscene raises numPlyrCurrGame
after a 1-player init, player index 1 writes at inst+0xFC = the next pool
item's offset 0 (the observed clobber).
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')
MI = os.path.join(ROOT, 'build-360', 'gen', 'game', 'MAIN', 'MainInit.c')

WALK_BODY = (TAB + '{ static int s_pz = 0; if (sdata->frameCounter >= 199 && s_pz < 60) { s_pz++; '
             'Platform_Log("[trace] pz f=%s numPlyr=%d itemSize=%d maxItems=%d pool=%08x first=%08x' + ESCN + '", '
             '(int)sdata->frameCounter, (int)numPlyr, (int)GAME_TRACKER->JitPools.instance.itemSize, '
             '(int)GAME_TRACKER->JitPools.instance.maxItems, '
             '(unsigned)(u32)GAME_TRACKER->JitPools.instance.ptrPoolData, '
             '(unsigned)(u32)GAME_TRACKER->JitPools.instance.taken.first); } }' + NL)

INIT_BODY = (TAB + '{ static int s_pi = 0; if (s_pi < 8) { s_pi++; '
             'Platform_Log("[trace] pi f=%s numPlyr=%d itemSize=%d maxItems=%d' + ESCN + '", '
             '(int)sdata->frameCounter, (int)GAME_TRACKER->numPlyrCurrGame, '
             '(int)GAME_TRACKER->JitPools.instance.itemSize, '
             '(int)GAME_TRACKER->JitPools.instance.maxItems); } }' + NL)


def insert_after(path, anchor, body, tag):
    text = io.open(path, 'r', newline='').read()
    if tag in text:
        print('%s: present' % tag)
        return
    nl = '\r\n' if '\r\n' in text else NL
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit('anchor not found: %s' % anchor)
    eol = text.find(nl, idx)
    text = text[:eol + len(nl)] + body.replace(NL, nl) + text[eol + len(nl):]
    io.open(path, 'w', newline='').write(text)
    print('%s: inserted' % tag)


def main():
    # in the NonLev walk: right after the q8 probe's log call line
    insert_after(RB, 'Platform_Log("[trace] q8 f=%d curr=%08x next=%08x model=%08x',
                 WALK_BODY, 'trace] pz ')
    # in MainInit: after the JitPool_Init call for the instance pool
    insert_after(MI, 'JitPool_Init(&gGT->JitPools.instance,', INIT_BODY, 'trace] pi ')
    print('session-6v ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
