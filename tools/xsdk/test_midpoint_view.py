"""The actual in-between view (NativeHD_AverageView in game/MAIN/MainHD.c) against the two views it averages.

Views are built as the game builds them: 4.12 rotation elements and an
integer translation of minus the rotated camera, the camera a few units and
angle steps apart between updates, at world coordinates up to 20000 as in
the adventure hubs. A point near the camera must land halfway between its
places in the two views, in view space, to a part of its distance from the
camera, and on screen to a fifth of a PlayStation pixel. Negative controls:
without the rounding taken back at the midpoint camera, and translations
averaged to whole units as before (the ground's half unit in every second
frame).
"""
import argparse, re, subprocess
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
hd = (root / 'game/MAIN/MainHD.c').read_text()
start = hd.index('static void NativeHD_AverageView(')
body = hd[start:hd.index('\n}\n', start) + 3]
c = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int16_t s16; typedef uint16_t u16; typedef int32_t s32; typedef uint32_t u32; typedef int64_t s64;
typedef struct { s16 m[3][3]; s32 t[3]; } MATRIX;
typedef struct { s16 x, y, z; } SVec3;
/* The host is little-endian, as ViewProj's layout. */
static u16 CTR_ReadU16LE(const void *p) { u16 v; memcpy(&v, p, 2); return v; }
static u32 CTR_ReadU32LE(const void *p) { u32 v; memcpy(&v, p, 4); return v; }
static void CTR_WriteU16LE(void *p, u16 v) { memcpy(p, &v, 2); }
static void CTR_WriteU32LE(void *p, u32 v) { memcpy(p, &v, 4); }
static int g_nativeGteTranslationFraction[3];
static s16 NativeHD_VecAxis(const SVec3 *v, int axis) { return axis == 0 ? v->x : (axis == 1 ? v->y : v->z); }
''' + body + r'''
/* A view as PushBuffer_SetMatrixVP makes one: rotation elements in 4.12, the
 * Y row squeezed by 0x360/0x600 and X by 3/4 (widescreen), t = rows . -camera. */
static void BuildView(MATRIX *v, const SVec3 *cam, double yaw, double pitch)
{
    double R[3][3] = {{cos(yaw), 0, -sin(yaw)}, {sin(yaw) * sin(pitch), cos(pitch), cos(yaw) * sin(pitch)},
                      {sin(yaw) * cos(pitch), -sin(pitch), cos(yaw) * cos(pitch)}};
    double scale[3] = {0.75, 0x360 / (double)0x600, 1};
    for (int r = 0; r < 3; r++) {
        s64 t = 0;
        for (int c = 0; c < 3; c++) {
            v->m[r][c] = (s16)lround(R[r][c] * scale[r] * 4096);
            t -= (s64)v->m[r][c] * NativeHD_VecAxis(cam, c);
        }
        v->t[r] = (s32)(t >> 12);
    }
}
/* MAC as the GTE forms it, in 1/4096 world units. */
static double View(const MATRIX *v, const int *fraction, const s32 *p, int r)
{
    return (double)v->t[r] * 4096 + (fraction ? fraction[r] : 0) + (double)v->m[r][0] * p[0] + (double)v->m[r][1] * p[1] +
           (double)v->m[r][2] * p[2];
}
int main(void)
{
    srand(360);
    double worst = 0, worstScreen = 0;
    for (int trial = 0; trial < 20000; trial++) {
        SVec3 c1 = {(s16)(rand() % 40000 - 20000), (s16)(rand() % 4000 - 2000), (s16)(rand() % 40000 - 20000)};
        SVec3 c2 = {(s16)(c1.x + rand() % 81 - 40), (s16)(c1.y + rand() % 21 - 10), (s16)(c1.z + rand() % 81 - 40)};
        double yaw = (rand() % 4096) * 2 * M_PI / 4096, pitch = (rand() % 200 - 100) * 2 * M_PI / 4096;
        double turn = (rand() % 61 - 30) * 2 * M_PI / 4096;
        MATRIX v1, v2, mid;
        BuildView(&v1, &c1, yaw, pitch);
        BuildView(&v2, &c2, yaw + turn, pitch);
        NativeHD_AverageView(&mid, &v1, &v2, &c1, &c2);
        for (int k = 0; k < 8; k++) {
            s32 p[3];
            double away = 0;
            for (int i = 0; i < 3; i++) {
                int offset = rand() % 6001 - 3000;
                p[i] = NativeHD_VecAxis(&c1, i) + offset;
                away += fabs(p[i] - (NativeHD_VecAxis(&c1, i) + NativeHD_VecAxis(&c2, i)) / 2.0);
            }
            double error = 0, ideal[3], ours[3];
            for (int r = 0; r < 3; r++) {
                ideal[r] = (View(&v1, NULL, p, r) + View(&v2, NULL, p, r)) / 2;
                ours[r] = View(&mid, g_nativeGteTranslationFraction, p, r);
                error = fmax(error, fabs(ours[r] - ideal[r]) / 4096);
            }
            double allowed = away / 8192.0 + 0.002;
            if (error / allowed > worst) worst = error / allowed;
            /* On screen: 256 across a 512-wide view, its height a little less. */
            if (ideal[2] > 100 * 4096 && fabs(256 * ideal[0] / ideal[2]) < 256 && fabs(256 * ideal[1] / ideal[2]) < 128) {
                double screen = fmax(fabs(256 * ours[0] / ours[2] - 256 * ideal[0] / ideal[2]),
                                     fabs(256 * ours[1] / ours[2] - 256 * ideal[1] / ideal[2]));
                if (screen > worstScreen) worstScreen = screen;
            }
        }
    }
    printf("worst view error %.3f of the allowed; worst on screen %.4f PlayStation pixels\n", worst, worstScreen);
    fflush(stdout);
    assert(worst <= 1.0 && worstScreen < 0.2);
    puts("PASS: actual in-between view puts points near the camera halfway between the two views, at hub-sized world coordinates");
    return 0;
}
'''
def run(source, name):
    path = a.out / (name + '.c'); path.write_text(source); exe = a.out / name
    subprocess.run(['cc', '-std=gnu17', '-O1', '-w', str(path), '-o', str(exe), '-lm'], check=True)
    return subprocess.run([str(exe.resolve())], capture_output=True, text=True)
r = run(c, 'midpoint-view'); assert r.returncode == 0, r.stdout + r.stderr; print(r.stdout.strip())
taken = '                translation += ((s64)NativeHD_VecAxis(previousCamera, c) + NativeHD_VecAxis(currentCamera, c)) / 4;\n'
assert c.count(taken) == 1
r = run(c.replace(taken, '                ;\n'), 'midpoint-view-no-camera'); assert r.returncode != 0, r.stdout
print('PASS: without the rounding taken back at the midpoint camera rejected:', r.stdout.strip().splitlines()[0])
whole = 'g_nativeGteTranslationFraction[r] = (int)(translation & 0xfff);'
assert c.count(whole) == 1
r = run(c.replace(whole, 'g_nativeGteTranslationFraction[r] = 0;'), 'midpoint-view-whole'); assert r.returncode != 0, r.stdout
print('PASS: translations to whole units, as before, rejected:', r.stdout.strip().splitlines()[0])
