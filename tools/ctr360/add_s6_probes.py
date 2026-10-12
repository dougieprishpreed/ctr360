#!/usr/bin/env python3
"""Session-6 probes: ModelHeader scale + BuildM3x3 internals.

Adds, to the compiled tree only (HANDOFF section 6: the tree is what runs):

  mhs  - in QueueDraw right after mh selection (after the qd2 probe): the
         selected ModelHeader pointer, its decoded name, its scale bytes as
         BOTH a host u32 read and the little-endian read the game performs,
         and the instance scale/flags. Gated to the title models 0x60..0x70
         so the output stays focused on MM_Title's instances.
  b3s  - at the end of RenderBucket_BuildM3x3: packedScaleXY, the shift
         values, the lcv0 scaled triple and the final m3x3 tuple, same gate.

Rules honoured (HANDOFF section 5): insertions are always complete top-level
statements placed directly after an existing statement, never between an
if(...) and its '{'; both probes guard on the title model ids; both are
idempotent (re-running finds the marker and skips).
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TREE = os.path.join(ROOT, 'build-360', 'gen', 'game', 'RenderBucket',
                    'RenderBucket_QueueExecute.c')

MHS_BODY = (
    '\t{ static int s_mhs = 0; if (inst->model->id >= 0x60 && inst->model->id <= 0x70 && s_mhs < 48) '
    '{ s_mhs++; Platform_Log("[trace] mhs f=%d mid=%d mh=%08x nm=%08x,%08x '
    'scH=%08x scL=%08x zH=%04x zL=%04x isc=%d,%d,%d fl=%08x\\n", '
    '(int)sdata->frameCounter, (int)inst->model->id, (unsigned)(u32)mh, '
    '(unsigned)ModelName_ReadWord(mh->name, 0), (unsigned)ModelName_ReadWord(mh->name, 1), '
    '(unsigned)(*(u32 *)&mh->scale.x), (unsigned)CTR_ReadU32LE((const u8 *)&mh->scale.x), '
    '(unsigned)(u32)(u16)mh->scale.z, (unsigned)(u32)CTR_ReadU16LE((const u8 *)&mh->scale.z), '
    '(int)inst->scale.x, (int)inst->scale.y, (int)inst->scale.z, (unsigned)inst->flags); } }\n'
)

B3S_BODY = (
    '\t{ static int s_b3s = 0; if (inst->model->id >= 0x60 && inst->model->id <= 0x70 && s_b3s < 48) '
    '{ s_b3s++; Platform_Log("[trace] b3s f=%d mid=%d pk=%08x sxy=%d szs=%d ds=%d '
    'sc=%08x,%08x,%08x m3=%08x,%08x,%08x,%08x,%08x\\n", '
    '(int)sdata->frameCounter, (int)inst->model->id, (unsigned)packedScaleXY, '
    '(int)scaleXYShift, (int)scaleZShift, (int)depthShift, '
    '(unsigned)scaledX, (unsigned)scaledY, (unsigned)scaledZ, '
    '(unsigned)m0, (unsigned)m1, (unsigned)m2, (unsigned)m3, (unsigned)m4); } }\n'
)


def main():
    text = io.open(TREE, 'r', newline='').read()
    nl = '\r\n' if '\r\n' in text else '\n'          # keep the tree's line endings
    mhs_body = MHS_BODY.replace('\n', nl)
    b3s_body = B3S_BODY.replace('\n', nl)
    changed = 0

    if 'trace] mhs' in text:
        print('mhs: already present, skipped')
    else:
        anchor = '\t{ static int s_qd2 = 0; if (s_qd2 < 24) { s_qd2++; Platform_Log("[trace] qd2'
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit('mhs: qd2 anchor not found')
        eol = text.find('\n', idx)
        text = text[:eol + 1] + mhs_body + text[eol + 1:]
        changed += 1
        print('mhs: inserted after qd2')

    if 'trace] b3s' in text:
        print('b3s: already present, skipped')
    else:
        # line-ending agnostic: anchor on the statement, insert after its EOL
        anchor = '\tmatrixState->m4 = m4;'
        idx = text.find(anchor)
        if idx < 0 or text.find(anchor, idx + 1) >= 0:
            raise SystemExit('b3s: end-of-BuildM3x3 anchor not unique')
        eol = text.find('\n', idx)
        text = text[:eol + 1] + b3s_body + text[eol + 1:]
        changed += 1
        print('b3s: inserted at end of BuildM3x3')

    if changed:
        io.open(TREE, 'w', newline='').write(text)
    print('probes ok (%d change(s))' % changed)


if __name__ == '__main__':
    sys.exit(main())
