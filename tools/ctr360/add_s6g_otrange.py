#!/usr/bin/env python3
"""Session-6g: compare the OT range pointer with the model pack address.

No otfull/otrange/otnull guard traces fired, so RenderBucket_AllocateOTRange
succeeded and handed the instance a range inside its OT pool. The clobbered
address (ptrMPK + 0x168, inside the loaded model pack) then IS that range
pointer - i.e. the OT pool overlaps the model pack. Two probes:

  ota - RenderBucket_AllocateOTRange success path: rangeStart/range/end
  otd - RenderBucket_DrawFunc_Normal entry: idpp->otRangeNormal + ptrMPK

so one run shows both values and whether the pool really is inside the pack.
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket', 'RenderBucket_QueueExecute.c')

NL = chr(10)
TAB = chr(9)
ESCN = chr(92) + 'n'

OTA = (TAB + '{ static int s_ota = 0; if (s_ota < 40) { s_ota++; '
       'Platform_Log("[trace] ota f=%d start=%08x range=%d new=%08x end1=%08x' + ESCN + '", '
       '(int)sdata->frameCounter, (unsigned)(u32)rangeStart, (int)range, (unsigned)(u32)newCurr, '
       '(unsigned)(u32)queueState->otEndMinusOne); } }' + NL)

OTD = (TAB + '{ static int s_otd = 0; if (s_otd < 40) { s_otd++; '
       'Platform_Log("[trace] otd f=%d rng=%08x sec=%08x mpk=%08x d0=%d d1=%d' + ESCN + '", '
       '(int)sdata->frameCounter, (unsigned)ctx->idpp->otRangeNormal, (unsigned)ctx->idpp->otRangeSecondary, '
       '(unsigned)(u32)sdata->ptrMPK, (int)ctx->idpp->depthOffset[0], (int)ctx->idpp->depthOffset[1]); } }' + NL)


def main():
    text = io.open(FILE, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else NL
    changed = 0

    if 'trace] ota ' not in text:
        anchor = '\tqueueState->otCurr = newCurr;'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('ota: anchor not found')
        eol = text.find(nl, idx)
        text = text[:eol + len(nl)] + OTA.replace(NL, nl) + text[eol + len(nl):]
        changed += 1
        print('ota: inserted')
    else:
        print('ota: present')

    if 'trace] otd ' not in text:
        anchor = '\tpCmd = (u32 *)ctx->idpp->ptrCommandList;\n'
        idx = text.find(anchor)
        if idx < 0:
            # allow CRLF files
            anchor = anchor.replace('\n', nl)
            idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('otd: anchor not found')
        # insert after the following `pCmd++;` statement (NEVER before the
        # declaration block or between a while(...) and its '{')
        idx2 = text.find('pCmd++;', idx)
        eol = text.find(nl, idx2)
        text = text[:eol + len(nl)] + OTD.replace(NL, nl) + text[eol + len(nl):]
        changed += 1
        print('otd: inserted after pCmd++')
    else:
        # move an earlier (mis-placed) probe out of the declaration block
        lines = text.split(nl)
        keep = [ln for ln in lines if 'trace] otd ' not in ln]
        if len(keep) != len(lines):
            text = nl.join(keep)
            print('otd: removed misplaced probe, reinserting')
            anchor = '\tpCmd = (u32 *)ctx->idpp->ptrCommandList;\n'
            idx = text.find(anchor)
            if idx < 0:
                anchor = anchor.replace('\n', nl)
                idx = text.find(anchor)
            if idx < 0:
                raise SystemExit('otd: anchor not found after cleanup')
            idx2 = text.find('pCmd++;', idx)
            eol = text.find(nl, idx2)
            text = text[:eol + len(nl)] + OTD.replace(NL, nl) + text[eol + len(nl):]
            changed += 1
            print('otd: reinserted after pCmd++')
        else:
            print('otd: present')

    io.open(FILE, 'w', newline='').write(text)
    print('ot range probes ok (%d change(s))' % changed)


if __name__ == '__main__':
    sys.exit(main())
