"""Probe every BuildDepthRange / AllocateOTRange failure path (tree + repo)."""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REL = os.path.join("game", "RenderBucket", "RenderBucket_QueueExecute.c")
NL = chr(92) + "n"


def tr(tag, fmt, args, cap=20):
    return ('\t\t{ static int s_%s = 0; if (s_%s < %d) { s_%s++; Platform_Log("[trace] %s f=%%d %s' % (tag, tag, cap, tag, tag, fmt)
            + NL + '", (int)sdata->frameCounter' + args + '); } }\r\n')


PAIRS = [
    # cull rejects (indent level inside the function body = one tab)
    ('\tif (bounds->maxX < 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (bounds->maxX < 0)\r\n\t{\r\n' + tr("bdx", "maxX=%d", ", (int)bounds->maxX") + '\t\treturn 0;\r\n\t}'),
    ('\tif (bounds->maxY < 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (bounds->maxY < 0)\r\n\t{\r\n' + tr("bdy", "maxY=%d", ", (int)bounds->maxY") + '\t\treturn 0;\r\n\t}'),
    ('\tif (RenderBucket_MipsSub(bounds->maxZ, geomScreenHalf) < 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (RenderBucket_MipsSub(bounds->maxZ, geomScreenHalf) < 0)\r\n\t{\r\n' + tr("bdz", "maxZ=%d half=%d minZ=%d", ", (int)bounds->maxZ, (int)geomScreenHalf, (int)bounds->minZ") + '\t\treturn 0;\r\n\t}'),
    ('\tif (RenderBucket_MipsSub(bounds->minX, (u16)pb->rect.w) > 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (RenderBucket_MipsSub(bounds->minX, (u16)pb->rect.w) > 0)\r\n\t{\r\n' + tr("bdx2", "minX=%d w=%d maxX=%d", ", (int)bounds->minX, (int)(u16)pb->rect.w, (int)bounds->maxX") + '\t\treturn 0;\r\n\t}'),
    ('\tif (RenderBucket_MipsSub(bounds->minY, (u16)pb->rect.h) > 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (RenderBucket_MipsSub(bounds->minY, (u16)pb->rect.h) > 0)\r\n\t{\r\n' + tr("bdy2", "minY=%d h=%d maxY=%d", ", (int)bounds->minY, (int)(u16)pb->rect.h, (int)bounds->maxY") + '\t\treturn 0;\r\n\t}'),
    # allocate: null guards
    ('\tif (queueState->otCurr == 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (queueState->otCurr == 0)\r\n\t{\r\n' + tr("otnull", "otCurr=0", "") + '\t\treturn 0;\r\n\t}'),
    ('\tif (queueState->otEndMinusOne == 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (queueState->otEndMinusOne == 0)\r\n\t{\r\n' + tr("otnull2", "otEnd=0", "") + '\t\treturn 0;\r\n\t}'),
    # allocate: range < 0
    ('\tif (range < 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (range < 0)\r\n\t{\r\n' + tr("otrange", "range=%d minD=%d maxD=%d", ", (int)range, (int)minDepth, (int)maxDepth") + '\t\treturn 0;\r\n\t}'),
    # allocate: exhaustion
    ('\tif (RenderBucket_AddressSub(queueState->otEndMinusOne, newCurr) <= 0)\r\n\t{\r\n\t\treturn 0;\r\n\t}',
     '\tif (RenderBucket_AddressSub(queueState->otEndMinusOne, newCurr) <= 0)\r\n\t{\r\n' + tr("otfull", "cur=%08x new=%08x end=%08x range=%d", ", (unsigned)(u32)queueState->otCurr, (unsigned)(u32)newCurr, (unsigned)(u32)queueState->otEndMinusOne, (int)range") + '\t\treturn 0;\r\n\t}'),
]

for label, base in (("repo", ROOT), ("tree", os.path.join(ROOT, "build-360", "gen"))):
    P = os.path.join(base, REL)
    t = io.open(P, encoding="utf-8", newline="").read()
    for o, n in PAIRS:
        if t.count(n) >= 1 and t.count(o) == 0:
            continue
        assert t.count(o) == 1, "%s: anchor x%d: %r" % (label, t.count(o), o[:50])
        t = t.replace(o, n)
    io.open(P, "w", encoding="utf-8", newline="").write(t)
    print("%s patched" % label)
print("ok")
