"""[graphics] smooth_camera: the actual course shift code (game/MAIN/MainHD.c) on whole-unit cameras.

Cameras stand on whole units, so a slow camera (the race flyby, or one following a
kart at low speed) moves the course in uneven steps: 3, 4, 3, 3, 4 units an update.
The course is drawn shifted by the camera's sub-unit place: while it follows a kart,
the kart's own sub-unit position; otherwise what an alpha-beta filter of the
whole-unit positions finds. Checks, through the GTE translation fraction the shift
becomes: a flyby at an uneven speed draws the course at even steps (to a fifth of a
unit, from a whole unit) after a second, a cut starts over without a shift, a followed kart's
fraction is used exactly, pausing keeps the last shift, 0 turns it off, and the
fraction comes back to its value after each course draw. Negative control: the
whole-unit steps the course moved in before.
"""
import argparse, subprocess
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); p.add_argument('--cc', default='cc')
a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
hd = (root / 'game/MAIN/MainHD.c').read_text()
begin = hd.index('int g_nativeHDSmoothCamera = 1;')
end = hd.index('/* Widescreen draws the world across the screen', begin)
code = hd[begin:end]
c = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int16_t s16; typedef uint16_t u16; typedef int32_t s32; typedef int64_t s64;
typedef struct { s16 m[3][3]; s32 t[3]; } MATRIX;
typedef struct { s16 x, y, z; } SVec3;
typedef struct { s32 x, y, z; } Vec3;
#define PAUSE_ALL 0xf
struct Level { int unused; };
struct Driver { Vec3 posCurr; };
struct CameraDC { int unused; };
struct PushBuffer { SVec3 pos; MATRIX matrix_ViewProj; };
struct GameTracker { int numPlyrCurrGame; unsigned gameMode1; struct Level *level1; struct PushBuffer pushBuffer[1]; struct CameraDC cameraDC[1]; };
static struct GameTracker tracker; static struct Level course;
static struct { struct GameTracker *gGT; } state = {&tracker}, *sdata = &state;
static u16 CTR_ReadU16LE(const void *p) { u16 v; memcpy(&v, p, 2); return v; }
static int g_nativeGteTranslationFraction[3];
static s16 NativeHD_VecAxis(const SVec3 *v, int axis) { return axis == 0 ? v->x : (axis == 1 ? v->y : v->z); }
CODE
/* Identity rotation: view space = world space, so the shift is -16 * delta (1/4096 units). */
static void View(void) { memset(&tracker.pushBuffer[0].matrix_ViewProj, 0, sizeof(MATRIX)); for (int i = 0; i < 3; i++) tracker.pushBuffer[0].matrix_ViewProj.m[i][i] = 4096; }
/* One update: the camera at its whole-unit place; returns where the course is drawn
 * from (camera minus the shift), in units. */
static void Update(const double *camera, double *drawnFrom)
{
    SVec3 *pos = &tracker.pushBuffer[0].pos;
    pos->x = (s16)floor(camera[0]); pos->y = (s16)floor(camera[1]); pos->z = (s16)floor(camera[2]);
    NativeHD_PrepareCourseShift(&tracker);
    int before[3]; memcpy(before, g_nativeGteTranslationFraction, sizeof(before));
    NativeHD_CourseShift(1);
    for (int i = 0; i < 3; i++) drawnFrom[i] = NativeHD_VecAxis(pos, i) - g_nativeGteTranslationFraction[i] / 4096.0;
    NativeHD_CourseShift(0);
    assert(!memcmp(before, g_nativeGteTranslationFraction, sizeof(before)));
}
int main(void)
{
    tracker.numPlyrCurrGame = 1; tracker.level1 = &course; View();
    const double speed[3] = {3.37, -0.61, 1.13};
    double camera[3] = {1000.2, 40.7, -2000.5}, drawn[3], previous[3];
    double worst = 0, wholeUnitWorst = 0;
    for (int update = 0; update < 120; update++)
    {
        double whole[3] = {floor(camera[0]), floor(camera[1]), floor(camera[2])};
        double nextWhole[3];
        Update(camera, drawn);
        for (int i = 0; i < 3; i++)
        {
            nextWhole[i] = floor(camera[i] + speed[i]);
            if (update >= 30 && update < 119)
            {
                double step = (update > 30) ? drawn[i] - previous[i] : speed[i];
                if (fabs(step - speed[i]) > worst) worst = fabs(step - speed[i]);
                if (fabs(nextWhole[i] - whole[i] - speed[i]) > wholeUnitWorst) wholeUnitWorst = fabs(nextWhole[i] - whole[i] - speed[i]);
            }
            previous[i] = drawn[i];
            camera[i] += speed[i];
        }
    }
    assert(worst < 0.2);            /* even steps to a fifth of a unit */
    assert(wholeUnitWorst > 0.5);   /* negative control: the whole-unit steps */
    /* A cut (a new shot) starts over: no shift that update. */
    camera[0] += 300; Update(camera, drawn);
    for (int i = 0; i < 3; i++) assert(drawn[i] == floor(camera[i]));
    /* Following a kart: its own sub-unit position, exactly. */
    struct Driver kart = {{1234 * 256 + 77, -50 * 256 + 200, 9 * 256 + 3}};
    NativeHD_NoteFollowCamera(&tracker.cameraDC[0], &kart);
    double followed[3] = {1234, -50, 9};
    Update(followed, drawn);
    assert(fabs(drawn[0] - (1234 + 77 / 256.0)) < 1e-9 && fabs(drawn[1] - (-50 + 200 / 256.0)) < 1e-9 && fabs(drawn[2] - (9 + 3 / 256.0)) < 1e-9);
    /* Paused: the last shift stays, so the still picture does not move. */
    tracker.gameMode1 = PAUSE_ALL; Update(followed, drawn);
    assert(fabs(drawn[0] - (1234 + 77 / 256.0)) < 1e-9);
    tracker.gameMode1 = 0;
    /* Two or more players and smooth_camera = 0 draw the whole-unit steps. */
    tracker.numPlyrCurrGame = 2; NativeHD_NoteFollowCamera(&tracker.cameraDC[0], &kart); Update(followed, drawn);
    for (int i = 0; i < 3; i++) assert(drawn[i] == followed[i]);
    tracker.numPlyrCurrGame = 1; g_nativeHDSmoothCamera = 0; NativeHD_NoteFollowCamera(&tracker.cameraDC[0], &kart); Update(followed, drawn);
    for (int i = 0; i < 3; i++) assert(drawn[i] == followed[i]);
    printf("PASS: flyby course steps even to %.3f units (whole-unit steps were up to %.2f off); cut, kart follow, pause, split-screen and smooth_camera=0 checked\n", worst, wholeUnitWorst);
    return 0;
}
'''.replace('CODE', code)
source = a.out / 'course-shift.c'; source.write_text(c); exe = a.out / 'course-shift'
subprocess.run([a.cc, '-std=gnu17', '-w', '-O1', str(source), '-o', str(exe), '-lm'], check=True)
r = subprocess.run([str(exe.resolve())], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
print(r.stdout.strip())
