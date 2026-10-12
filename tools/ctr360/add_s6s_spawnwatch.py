#!/usr/bin/env python3
"""Session-6s: dump the spawn instance's (model id 0xC0) projection state.

The taken-list corruption happens inside ExecuteAllInstances at f=204, the
frame the `spawn` instance (model id 192) is born and drawn. The f=14 clobber
had the same shape and was cured by fixing the m3x3 z column, so dump this
instance's matrix/m3x3/mvp in QueueDraw and its draw-side prim cursor.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'
RB = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

SPAWN_QD = (TAB + '{ static int s_spw = 0; if (inst->model->id == 0xC0 && sdata->frameCounter >= 199 && s_spw < 200) '
            '{ u32 *mm = (u32 *)&inst->matrix; s_spw++; '
            'Platform_Log("[trace] spw f=%%d im=%%08x,%%08x,%%08x,%%08x,%%08x,%%08x,%%08x,%%08x' + ESCN + '", '
            '(int)sdata->frameCounter, mm[0], mm[1], mm[2], mm[3], mm[4], mm[5], mm[6], mm[7]); } }' + NL)

SPAWN_DRAW = (TAB + '{ static int s_spr = 0; if (((struct Instance *)ctx->inst)->model->id == 0xC0 '
              '&& sdata->frameCounter >= 199 && s_spr < 200) { s_spr++; '
              'Platform_Log("[trace] spr f=%%d cur=%%08x cmd=%%08x mh=%%08x' + ESCN + '", '
              '(int)sdata->frameCounter, (unsigned)(u32)ctx->primMem->cursor, '
              '(unsigned)(u32)ctx->idpp->ptrCommandList, (unsigned)(u32)ctx->mh); } }' + NL)


def main():
    text = io.open(RB, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    # 1. QueueDraw: after the qd4 probe (end of QueueDraw's projection work)
    if 'trace] spw ' not in text:
        anchor = 'Platform_Log("[trace] qd4 f=%d m='
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('qd4 anchor not found')
        eol = text.find(nl, idx)
        text = text[:eol + len(nl)] + SPAWN_QD.replace(NL, nl) + text[eol + len(nl):]
        io.open(RB, 'w', newline='').write(text)
        print('spw: inserted after qd4')
    # 2. draw side: inside RenderBucket_DrawFunc_Normal, after the uncompress call
    if 'trace] spr ' not in text:
        anchor = 'RenderBucket_DispatchUncompressAnimationFrame(ctx, command, stackIndex);'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('uncompress anchor not found')
        eol = text.find(nl, idx)
        text = text[:eol + len(nl)] + SPAWN_DRAW.replace(NL, nl) + text[eol + len(nl):]
        io.open(RB, 'w', newline='').write(text)
        print('spr: inserted in DrawFunc_Normal')
    print('session-6s ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
