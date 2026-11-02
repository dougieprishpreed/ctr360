"""[graphics] close_seams: the actual NativeGpu_CloseSeams (platform/native_gpu.c) on track polygons.

The level drawer splits nearby ground blocks and clips them at the near plane, so
neighbours meet at corners one side has and the other does not (T-junctions); each
corner snaps to whole PlayStation pixels on its own, and hairline gaps open. Opaque
on-screen polygons the level drawer wrote this frame grow by half a pixel along
every edge, in the corner-offset lanes (1/64 pixel) the shader adds. Checks: every
edge of a square, a split quad's 45-degree triangle, a slanted triangle and a quad
with a repeated corner moves out by half a pixel in either winding; a sliver's tip
moves at most two pixels; a one-pixel T-junction gap between a whole block and its
split neighbour is covered after and open before; polygons under 8 by 8 pixels
(distant track), translucent, UI, off-screen, non-level, far-flung and degenerate
polygons keep their corners.
"""
import argparse, subprocess
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); p.add_argument('--cc', default='cc')
a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
gpu = (root / 'platform/native_gpu.c').read_text().replace('\r\n', '\n')
begin = gpu.index('int g_nativeCloseSeams = 1;')
end = gpu.index('\n#endif\n', begin)
code = gpu[begin:end]
c = r'''
#include <assert.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int8_t s8; typedef int16_t s16; typedef uint8_t u8;
typedef s16 VERTTYPE;
typedef struct { s16 x, y, page, clut; u8 u, v, bright, dither; u8 r, g, b, a; s8 tcx, tcy, _p0, _p1; } GrVertex;
static int s_nativeUIPass;
static struct { int dfe; } activeDrawEnv = {1};
CODE
static VERTTYPE prims[64];
/* A polygon from integer corners, grown as the level drawer's would be. */
static int Make(GrVertex *v, const int (*xy)[2], int n)
{
    memset(v, 0, sizeof(GrVertex) * n);
    for (int i = 0; i < n; i++) { v[i].x = (s16)xy[i][0]; v[i].y = (s16)xy[i][1]; }
    NativeGpu_CloseSeams(v, n, &prims[0]);
    int moved = 0;
    for (int i = 0; i < n; i++) moved |= v[i]._p0 | v[i]._p1;
    return moved;
}
static double X(const GrVertex *v) { return v->x + v->_p0 / 64.0; }
static double Y(const GrVertex *v) { return v->y + v->_p1 / 64.0; }
/* Distance from the line through a and b to point (px, py), signed. */
static double Side(const GrVertex *a, const GrVertex *b, double px, double py)
{
    double dx = X(b) - X(a), dy = Y(b) - Y(a);
    return ((px - X(a)) * dy - (py - Y(a)) * dx) / sqrt(dx * dx + dy * dy);
}
static int Inside(const GrVertex *v, int n, double px, double py)
{
    int pos = 0, neg = 0;
    for (int i = 0; i < n; i++)
    {
        double s = Side(&v[i], &v[(i + 1) % n], px, py);
        pos |= s > 1e-9; neg |= s < -1e-9;
    }
    return !(pos && neg);
}
/* Each grown edge lies `growth` outside the original edge (parallel). */
static void CheckGrowth(const int (*xy)[2], int n)
{
    GrVertex v[4], o[4];
    memset(o, 0, sizeof(o));
    for (int i = 0; i < n; i++) { o[i].x = (s16)xy[i][0]; o[i].y = (s16)xy[i][1]; }
    assert(Make(v, xy, n));
    double cx = 0, cy = 0;
    for (int i = 0; i < n; i++) { cx += o[i].x; cy += o[i].y; }
    cx /= n; cy /= n;
    for (int i = 0; i < n; i++)
    {
        const GrVertex *a = &o[i], *b = &o[(i + 1) % n];
        if (a->x == b->x && a->y == b->y) continue; /* a repeated corner's empty edge */
        double inward = Side(a, b, cx, cy) > 0 ? 1 : -1;
        double d0 = -inward * Side(a, b, X(&v[i]), Y(&v[i]));
        double d1 = -inward * Side(a, b, X(&v[(i + 1) % n]), Y(&v[(i + 1) % n]));
        assert(fabs(d0 - 0.5) < 0.03 && fabs(d1 - 0.5) < 0.03);
    }
}
int main(void)
{
    g_nativeLevelPrimStart = (const u8 *)&prims[0];
    g_nativeLevelPrimEnd = (const u8 *)&prims[64];
    static const int square[4][2] = {{0, 0}, {20, 0}, {20, 20}, {0, 20}};
    static const int squareCW[4][2] = {{0, 0}, {0, 20}, {20, 20}, {20, 0}};
    static const int slant[3][2] = {{3, 1}, {40, 9}, {11, 30}};
    static const int half[3][2] = {{0, 0}, {16, 0}, {16, 16}};
    CheckGrowth(square, 4); CheckGrowth(squareCW, 4); CheckGrowth(slant, 3); CheckGrowth(half, 3);
    /* A quad with a repeated corner (a triangle drawn as a quad): its three
     * edges still move out by half a pixel, the empty one bevelled. */
    static const int repeated[4][2] = {{0, 0}, {16, 0}, {16, 16}, {16, 16}};
    CheckGrowth(repeated, 4);
    /* A sliver's tip moves at most two pixels. */
    static const int sharp[3][2] = {{0, 0}, {200, 3}, {0, 6}};
    GrVertex v[4];
    Make(v, sharp, 3);
    for (int i = 0; i < 3; i++) assert(sqrt(v[i]._p0 * v[i]._p0 + v[i]._p1 * v[i]._p1) / 64.0 <= 2.01);
    /* T-junction: a whole block above y = 0 and its split neighbour below, whose
     * extra corner on the shared edge snapped a pixel down. The gap between
     * them at x = 10, y = 0.5 is open before and covered after. */
    static const int whole[4][2] = {{0, -20}, {20, -20}, {20, 0}, {0, 0}};
    static const int left[4][2] = {{0, 0}, {10, 1}, {10, 20}, {0, 20}};
    static const int right[4][2] = {{10, 1}, {20, 0}, {20, 20}, {10, 20}};
    GrVertex w[4], l[4], r[4];
    g_nativeCloseSeams = 0;
    Make(w, whole, 4); Make(l, left, 4); Make(r, right, 4);
    assert(!Inside(w, 4, 10, 0.5) && !Inside(l, 4, 10, 0.5) && !Inside(r, 4, 10, 0.5));
    g_nativeCloseSeams = 1;
    Make(w, whole, 4); Make(l, left, 4); Make(r, right, 4);
    for (double x = 0.5; x < 19.6; x += 0.25)
    {
        double gapBottom = x < 10 ? x * 0.1 : (20 - x) * 0.1;
        for (double y = 0.02; y < gapBottom; y += 0.05)
            assert(Inside(w, 4, x, y) || Inside(l, 4, x, y) || Inside(r, 4, x, y));
    }
    /* Distant track: under 8 by 8 pixels keeps its corners, 8 by 8 grows. */
    static const int small[4][2] = {{0, 0}, {7, 0}, {7, 9}, {0, 9}};
    static const int least[4][2] = {{0, 0}, {8, 0}, {8, 8}, {0, 8}};
    assert(!Make(v, small, 4));
    CheckGrowth(least, 4);
    /* Kept as drawn: translucent, the UI pass, off-screen, outside the level
     * drawer's prims, corners far out of range, and null polygons. */
    s_gpuPolySemiTrans = true; assert(!Make(v, square, 4)); s_gpuPolySemiTrans = false;
    s_nativeUIPass = 1; assert(!Make(v, square, 4)); s_nativeUIPass = 0;
    activeDrawEnv.dfe = 0; assert(!Make(v, square, 4)); activeDrawEnv.dfe = 1;
    g_nativeLevelPrimEnd = (const u8 *)&prims[0]; assert(!Make(v, square, 4)); g_nativeLevelPrimEnd = (const u8 *)&prims[64];
    static const int far[3][2] = {{0, 0}, {5000, 0}, {0, 40}};
    assert(!Make(v, far, 3));
    static const int line[3][2] = {{0, 0}, {10, 0}, {20, 0}};
    assert(!Make(v, line, 3));
    g_nativeCloseSeams = 0; assert(!Make(v, square, 4));
    puts("PASS: actual seam closing grows track polygons half a pixel along every edge in either winding, 45-degree and repeated corners included, a sliver's tip at most two pixels, and covers a one-pixel T-junction gap that was open; polygons under 8 by 8, translucent, UI, off-screen, non-level, far-flung and null polygons and close_seams=0 kept");
    return 0;
}
'''.replace('CODE', code)
source = a.out / 'close-seams.c'; source.write_text(c); exe = a.out / 'close-seams'
subprocess.run([a.cc, '-std=gnu17', '-w', '-O1', str(source), '-o', str(exe), '-lm'], check=True)
r = subprocess.run([str(exe.resolve())], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
print(r.stdout.strip())
