"""Probe the render-bucket base contents right after the queue and right
before the execute (tree + repo)."""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REL = os.path.join("game", "MAIN", "MainFrame_RenderFrame.c")

NL = chr(92) + "n"

Q_OLD = "\t// null terminator at end of list\r\n\t*RBI = 0;\r\n"
Q_NEW = ("\t// null terminator at end of list\r\n\t*RBI = 0;\r\n"
         "\t{ static int s_qb = 0; if ((s_qb++ % 30) == 0) { Platform_Log(\"[probe] qb base=%08x end=%08x n=%d first=%08x first2=%08x' + NL + '\", "
         "(unsigned)(u32)gGT->ptrRenderBucketInstance, (unsigned)(u32)RBI, "
         "(int)(((u32 *)RBI - (u32 *)gGT->ptrRenderBucketInstance) / 2), "
         "(unsigned)((u32 *)gGT->ptrRenderBucketInstance)[0], (unsigned)((u32 *)gGT->ptrRenderBucketInstance)[1]); } }\r\n")

E_OLD = "\tRenderBucket_Execute(gGT->ptrRenderBucketInstance, &gGT->backBuffer->primMem);\r\n"
E_NEW = ("\t{ static int s_eb = 0; if ((s_eb++ % 30) == 0) { Platform_Log(\"[probe] eb base=%08x first=%08x first2=%08x primcur=%08x' + NL + '\", "
         "(unsigned)(u32)gGT->ptrRenderBucketInstance, "
         "(unsigned)((u32 *)gGT->ptrRenderBucketInstance)[0], (unsigned)((u32 *)gGT->ptrRenderBucketInstance)[1], "
         "(unsigned)(u32)gGT->backBuffer->primMem.cursor); } }\r\n"
         + E_OLD)

for label, base in (("repo", ROOT), ("tree", os.path.join(ROOT, "build-360", "gen"))):
    P = os.path.join(base, REL)
    t = io.open(P, encoding="utf-8", newline="").read()
    for o, n in ((Q_OLD, Q_NEW), (E_OLD, E_NEW)):
        if t.count(n) >= 1 and t.count(o) == 0:
            continue
        assert t.count(o) == 1, "%s: anchor x%d: %r" % (label, t.count(o), o[:40])
        t = t.replace(o, n)
    io.open(P, "w", encoding="utf-8", newline="").write(t)
    print("%s patched" % label)
