"""Projection probes: dump the GTE projection inputs/outputs for the first
instances processed by RenderBucket_ProjectFrameBounds (tree + repo)."""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REL = os.path.join("game", "RenderBucket", "RenderBucket_QueueExecute.c")
NL = chr(92) + "n"

A1 = "\tRenderBucket_BoundsInit(bounds, MFC2(12), MFC2(17));\r\n"
N1 = ("\t{ static int s_pj = 0; if (s_pj < 12) { s_pj++; Platform_Log(\"[trace] pj f=%d minXY=%08x minZ=%08x sxy=%08x sz=%d mvp=%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x" + NL + "\", "
      "(int)sdata->frameCounter, (unsigned)minXY, (unsigned)minZ, (unsigned)MFC2(12), (int)MFC2(17), "
      "(unsigned)((const u32 *)projectionMvp)[0], (unsigned)((const u32 *)projectionMvp)[1], (unsigned)((const u32 *)projectionMvp)[2], "
      "(unsigned)((const u32 *)projectionMvp)[3], (unsigned)((const u32 *)projectionMvp)[4], (unsigned)((const u32 *)projectionMvp)[5], "
      "(unsigned)((const u32 *)projectionMvp)[6], (unsigned)((const u32 *)projectionMvp)[7]); } }\r\n" + A1)

A2 = "\t*geomScreenHalf = (int)CFC2(26) >> 1;\r\n"
N2 = ("\t{ static int s_pk = 0; if (s_pk < 12) { s_pk++; Platform_Log(\"[trace] pk f=%d x=%d..%d y=%d..%d z=%d..%d h=%d" + NL + "\", "
      "(int)sdata->frameCounter, (int)bounds->minX, (int)bounds->maxX, (int)bounds->minY, (int)bounds->maxY, "
      "(int)bounds->minZ, (int)bounds->maxZ, (int)CFC2(26)); } }\r\n" + A2)

for label, base in (("repo", ROOT), ("tree", os.path.join(ROOT, "build-360", "gen"))):
    P = os.path.join(base, REL)
    t = io.open(P, encoding="utf-8", newline="").read()
    for o, n in ((A1, N1), (A2, N2)):
        if t.count(o) == 0 and t.count(n) >= 1:
            continue
        assert t.count(o) == 1, "%s: anchor x%d: %r" % (label, t.count(o), o[:60])
        t = t.replace(o, n)
    io.open(P, "w", encoding="utf-8", newline="").write(t)
    print("%s patched" % label)
print("ok")
