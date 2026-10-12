"""QueueDraw stage traces (tree only): find the step that hangs once an
instance actually proceeds through the full draw-prep path."""
import io

P = r"F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\gen\game\RenderBucket\RenderBucket_QueueExecute.c"
t = io.open(P, encoding="utf-8", newline="").read()

NL = chr(92) + "n"
CRLF = "\r\n"

def tr(tag, extra_fmt, extra_args, cap=24):
    return ('\t{ static int s_%s = 0; if (s_%s < %d) { s_%s++; Platform_Log("[trace] %s f=%%d %s' % (tag, tag, cap, tag, tag, extra_fmt)
            + NL + '", (int)sdata->frameCounter' + extra_args + '); } }' + CRLF)

PAIRS = [
    # before AdjustViewPositionForMvp  -> stage 1 (alpha scale passed)
    ("\tRenderBucket_AdjustViewPositionForMvp(inst, &viewPos);" + CRLF,
     tr("qd1", "", "") + "\tRenderBucket_AdjustViewPositionForMvp(inst, &viewPos);" + CRLF),
    # before normalDepthBias  -> stage 2 (header selected)
    ("\tnormalDepthBias = RenderBucket_SignExtendByte(inst->depthBiasNormal);" + CRLF,
     tr("qd2", "mh=%08x lod=%d", ", (unsigned)(u32)mh, (int)lodIndex") + "\tnormalDepthBias = RenderBucket_SignExtendByte(inst->depthBiasNormal);" + CRLF),
    # after ptrDeltaArray store -> stage 3 (frame selected)
    ("\tidpp->ptrDeltaArray = deltaArray;" + CRLF,
     "\tidpp->ptrDeltaArray = deltaArray;" + CRLF + tr("qd3", "frame=%08x next=%08x delta=%d adv=%d", ", (unsigned)(u32)frame, (unsigned)(u32)nextFrame, (int)deltaArray, (int)lastFrameAdvance")),
    # after BuildSplitState -> stage 4
    ("\tsplit = RenderBucket_BuildSplitState(inst, mh, frame, nextFrame, pb, idpp, viewDepth, &queuedFlags, &matrixState, &projectionMvp);" + CRLF,
     "\tsplit = RenderBucket_BuildSplitState(inst, mh, frame, nextFrame, pb, idpp, viewDepth, &queuedFlags, &matrixState, &projectionMvp);" + CRLF + tr("qd4", "", "")),
    # after SelectRetailHandlers -> stage 5
    ("\tRenderBucket_SelectRetailHandlers(&queuedFlags, &split, &drawFunc, &uncompressFunc);" + CRLF,
     "\tRenderBucket_SelectRetailHandlers(&queuedFlags, &split, &drawFunc, &uncompressFunc);" + CRLF + tr("qd5", "drawFunc=%08x uncompress=%08x", ", (unsigned)(u32)drawFunc, (unsigned)(u32)uncompressFunc")),
]

for o, n in PAIRS:
    c = t.count(o)
    if c != 1:
        raise SystemExit("anchor x%d: %s" % (c, o.strip()[:60]))
    t = t.replace(o, n)

io.open(P, "w", encoding="utf-8", newline="").write(t)
print("queue stage traces inserted")
