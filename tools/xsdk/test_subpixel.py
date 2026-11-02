"""[graphics] subpixel: the actual GTE (platform/native_gte_core.c, 360 build) against exact projections.

The GTE keeps view space in whole units (IR = MAC >> 12) and the screen in whole
PlayStation pixels, so at low speed the ground moved in uneven steps: 2.5-3.3
pixels each at 720p. This drives the real RotTransPers with a camera following a
kart at 1.37 units an update along a course, the camera on whole units as the
game's is, and measures a ground point's place on screen against the exact
projection of the camera's true path:
  whole pixels, as before             - off by up to 1.3 pixels
  exact projections, whole-unit camera - the camera's whole-unit steps remain (0.5)
  exact projections + the course shift - even (the translation fraction MainHD
                                         gives the course, which the GTE's whole-
                                         unit view space used to drop)
Also: one point projected twice keeps its offset; two different points at one
pixel with different offsets give none (the whole pixel); offsets stay within
the frame they were projected in; subpixel = 0 gives none.
"""
import argparse, subprocess
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); p.add_argument('--cc', default='cc')
a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
c = r'''
#include "platform/native_gte_core.c"
#include <assert.h>
#include <stdio.h>
#define H 256
/* Identity rotation: view = world - camera. Whole-unit camera in TR; the
 * course shift's sub-unit part, if any, as the translation fraction. */
static double Project(double camera, int shift, int vy, int vz, double *exact, int *whole)
{
    int ci = (int)floor(camera);
    C2_R11 = 4096; C2_R12 = 0; C2_R13 = 0; C2_R21 = 0; C2_R22 = 4096; C2_R23 = 0; C2_R31 = 0; C2_R32 = 0; C2_R33 = 4096;
    C2_TRX = 0; C2_TRY = 0; C2_TRZ = -ci;
    C2_OFX = 256 << 16; C2_OFY = 108 << 16; C2_H = H;
    g_nativeGteTranslationFraction[0] = g_nativeGteTranslationFraction[1] = 0;
    g_nativeGteTranslationFraction[2] = shift ? -(int)floor((camera - ci) * 4096.0 + 0.5) : 0;
    C2_VX0 = 0; C2_VY0 = (s16)vy; C2_VZ0 = (s16)vz;
    m_sf = 1;   /* RTPS/RTPT as the game issues them */
    GTE_RotTransPers(0, 0);
    s8 dx = 0, dy = 0;
    NativeGte_SubpixelOffset(C2_SX2, C2_SY2, &dx, &dy);
    *exact = 108.0 + H * vy / (vz - camera);
    *whole = C2_SY2;
    return C2_SY2 + dy / 64.0;
}
int main(void)
{
    double worst[3] = {0, 0, 0};
    for (int mode = 0; mode < 3; mode++)
        for (int update = 0; update < 90; update++)
        {
            double camera = -40.25 + 1.37 * update, exact;
            int whole;
            NativeGte_SubpixelNextFrame();
            double drawn = Project(camera, mode == 2, 100, 300, &exact, &whole);
            double error = fabs((mode == 0 ? whole : drawn) - exact);
            if (error > worst[mode]) worst[mode] = error;
        }
    assert(worst[0] > 0.5);      /* whole pixels */
    assert(worst[1] > 0.1);      /* the camera's whole-unit steps */
    assert(worst[2] < 0.05);     /* even: within 1/20 of a PlayStation pixel */
    /* One point twice keeps its offset; a different point at the same pixel
     * with another offset makes it ambiguous: the whole pixel. */
    double exact; int whole; s8 dx, dy;
    NativeGte_SubpixelNextFrame();
    Project(0.3, 1, 100, 300, &exact, &whole);
    s16 sx = C2_SX2, sy = C2_SY2;
    Project(0.3, 1, 100, 300, &exact, &whole);
    assert(NativeGte_SubpixelOffset(sx, sy, &dx, &dy) == 1);
    int found = 0;
    for (int vz = 290; vz < 320 && !found; vz++)
        for (int vy = 90; vy < 110 && !found; vy++)
        {
            s8 before = dy;
            Project(0.3, 1, vy, vz, &exact, &whole);
            if (C2_SX2 == sx && C2_SY2 == sy && !(vy == 100 && vz == 300))
            {
                s8 ex, ey;
                found = 1;
                if (NativeGte_SubpixelOffset(sx, sy, &ex, &ey)) assert(ex == dx && ey == before);
            }
        }
    assert(found);
    /* Offsets belong to their frame. */
    NativeGte_SubpixelNextFrame();
    assert(NativeGte_SubpixelOffset(sx, sy, &dx, &dy) == 0);
    /* subpixel = 0 */
    g_nativeGteSubpixel = 0;
    Project(0.3, 1, 100, 300, &exact, &whole);
    assert(NativeGte_SubpixelOffset(C2_SX2, C2_SY2, &dx, &dy) == 0);
    printf("PASS: a ground point at low speed is off its exact place by %.3f pixels in whole pixels, %.3f with exact projections, %.4f with the course shift; offsets kept per point, ambiguous pixels and old frames give none, subpixel=0 none\n",
           worst[0], worst[1], worst[2]);
    return 0;
}
'''
source = a.out / 'subpixel.c'; source.write_text(c); exe = a.out / 'subpixel'
subprocess.run([a.cc, '-std=gnu17', '-w', '-O1', '-D_XBOX', '-DCTR_NATIVE', '-DCTR_GTE_BIG_ENDIAN=0', '-D_Static_assert(x,y)=', '-I', str(root / 'include'), '-I', str(root),
                str(source), '-o', str(exe), '-lm'], check=True)
r = subprocess.run([str(exe.resolve())], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
print(r.stdout.strip())
