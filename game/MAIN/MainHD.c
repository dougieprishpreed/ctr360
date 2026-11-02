#include <common.h>

#ifdef _XBOX
#include <math.h>

/* Render-only midpoint frames. The retail simulation, input sampling, audio,
 * race timers and animation ticks retain their existing cadence. Never call
 * MainFrame_GameLogic, UI/menu updates, particle ticks or pickups here. */
void NativeGpu_BeginHUDCapture(void);
void NativeGpu_ReplayHUD(void);
void NativeGpu_SetHUDCapture(int enabled);
int NativeGpu_HasHUDCapture(void);
/* 0 while the GPU can't draw an update's two frames in time ([graphics] steady). */
int NativeRenderer_MidpointsFit(void);
void NativeRenderer_SubmitScene(void);

#define NATIVE_HD_INSTANCE_LIMIT 512
struct NativeHDPose
{
    struct Instance *instance;
    struct Model *model;
    struct Thread *thread;
    MATRIX matrix;
    u32 flags;
};
static struct NativeHDPose s_hdPrevious[NATIVE_HD_INSTANCE_LIMIT];
static struct NativeHDPose s_hdCurrent[NATIVE_HD_INSTANCE_LIMIT];
static int s_hdPoseCount;
#define NATIVE_HD_POSE_HASH_SIZE 1024
static u16 s_hdPoseHash[NATIVE_HD_POSE_HASH_SIZE];

static void NativeHD_IndexPreviousPoses(void)
{
    int i;
    memset(s_hdPoseHash, 0, sizeof(s_hdPoseHash));
    for (i = 0; i < s_hdPoseCount; i++)
    {
        u32 slot = (((u32)s_hdPrevious[i].instance >> 4) * 2654435761u) & (NATIVE_HD_POSE_HASH_SIZE - 1);
        while (s_hdPoseHash[slot] != 0) slot = (slot + 1) & (NATIVE_HD_POSE_HASH_SIZE - 1);
        s_hdPoseHash[slot] = (u16)(i + 1);
    }
}

/* The same object as last update: the same instance and, while a thread owns
 * it, the same thread. Threaded effects change model as they animate (the
 * turbo flames cycle eight models, one per update); matching their model as
 * well left them at the update's end on midpoints, half a frame ahead of the
 * kart, so at speed the flames showed twice and too high. A pooled instance
 * reused for a new object comes with a new thread; threadless level
 * instances still need their model to match. */
static int NativeHD_FindPreviousPose(struct Instance *instance, struct Model *model, struct Thread *thread)
{
    int probes;
    u32 slot = (((u32)instance >> 4) * 2654435761u) & (NATIVE_HD_POSE_HASH_SIZE - 1);
    for (probes = 0; probes < NATIVE_HD_POSE_HASH_SIZE; probes++)
    {
        int index = (int)s_hdPoseHash[slot] - 1;
        if (index < 0) return -1;
        if (s_hdPrevious[index].instance == instance &&
            (thread != NULL ? s_hdPrevious[index].thread == thread : s_hdPrevious[index].model == model)) return index;
        slot = (slot + 1) & (NATIVE_HD_POSE_HASH_SIZE - 1);
    }
    return -1;
}
static struct Level *s_hdLevel;
static SVec3 s_hdCameraPosition;
static SVec3 s_hdCameraRotation;
extern int g_nativeGteTranslationFraction[3];
static s16 NativeHD_VecAxis(const SVec3 *v, int axis);

/* The in-between view as the average of the update before's view and this
 * one's (NativeHD_RenderIntermediate builds it): a static point lands exactly halfway
 * between its places in the two frames. Rebuilt from the camera's midpoint
 * in whole world units and angle steps, the view stood half a unit short on
 * odd steps; with vertices snapped to whole pixels, at low speed the ground
 * jumped back in every second frame. A view is M * V + t with t about
 * -M * camera, the two large terms cancelling near the camera; a rotation
 * element whose sum is odd rounds down half a step, so the translation takes
 * that step back at the midpoint camera, and what is left grows with the
 * distance from the camera, not with the world's coordinates. The
 * translation, in TR << 12 units, keeps its part below a world unit for the
 * GTE's perspective transforms. The rotations' average is a hair short of a
 * rotation across a turn; at the camera-jump gate's limit it scales the view
 * by 2%, between ordinary updates far less. ViewProj keeps the retail
 * little-endian layout (PushBuffer_SetMatrixVP). */
static void NativeHD_AverageView(MATRIX *view, const MATRIX *previous, const MATRIX *current, const SVec3 *previousCamera,
                                 const SVec3 *currentCamera)
{
    int r, c, odd[3][3];
    for (r = 0; r < 3; r++)
        for (c = 0; c < 3; c++)
        {
            int sum = (s16)CTR_ReadU16LE(&previous->m[r][c]) + (s16)CTR_ReadU16LE(&current->m[r][c]);
            CTR_WriteU16LE(&view->m[r][c], (u16)(s16)(sum >> 1));
            odd[r][c] = sum & 1;
        }
    for (r = 0; r < 3; r++)
    {
        s64 translation = ((s64)(s32)CTR_ReadU32LE(&previous->t[r]) + (s32)CTR_ReadU32LE(&current->t[r])) * 0x800;
        for (c = 0; c < 3; c++)
            if (odd[r][c])
                translation += ((s64)NativeHD_VecAxis(previousCamera, c) + NativeHD_VecAxis(currentCamera, c)) / 4;
        CTR_WriteU32LE(&view->t[r], (u32)(s32)(translation >> 12));
        g_nativeGteTranslationFraction[r] = (int)(translation & 0xfff);
    }
}
static u32 s_hdOTBackup[0x406];
int g_nativeHDIntermediate;
int g_nativeHDEnableInterpolation = 1;
/* [graphics] widescreen: 1 shows more of the world in 16:9 with the authored
 * HUD in a centred 4:3 area; 0 keeps the original 4:3 view. Boot-time only. */
int g_nativeHDWidescreen = 1;

/* [graphics] smooth_camera: the follow camera and the karts stand on whole
 * units, so at low speed the course passed in uneven steps (5, 4, 6 units an
 * update) and the ground juddered; at speed the same unit is lost in the
 * motion. With 1, the course (level geometry and course instances, queued
 * before the others) is drawn shifted by the camera's sub-unit place, as if
 * it rode its exact path: while it follows the kart, the kart's own sub-unit
 * position; for every other view (the race flyby, end-of-race shots), what a
 * steady-motion filter of its whole-unit positions finds. Karts and what
 * they carry keep their whole-unit place in the view, as before. One player
 * only; 0 draws the original steps. */
int g_nativeHDSmoothCamera = 1;
void *g_nativeHDCourseEntriesEnd;
static int s_hdFollowDelta[3], s_hdFollowValid;
static int s_hdDelta[3], s_hdDeltaValid, s_hdDeltaDone;
static int s_hdPreviousDelta[3], s_hdPreviousValid;
static int s_hdCourseShift[3], s_hdCourseShiftReady, s_hdCourseShiftOn;
/* The filter, in 1/256 units: position estimate and step per update. */
static int s_hdCamEstimate[3], s_hdCamStep[3], s_hdCamEstimateValid;
static const struct Level *s_hdCamLevel;
#define NATIVE_HD_CAMERA_CUT (64 * 256)
#define NATIVE_HD_CAMERA_DELTA_LIMIT 384

/* CAM_FollowDriver_Normal: camera 0 follows d this update. */
void NativeHD_NoteFollowCamera(const struct CameraDC *cDC, const struct Driver *d)
{
    struct GameTracker *gGT = sdata->gGT;
    if (cDC != &gGT->cameraDC[0] || gGT->numPlyrCurrGame != 1) return;
    s_hdFollowDelta[0] = d->posCurr.x & 0xff;
    s_hdFollowDelta[1] = d->posCurr.y & 0xff;
    s_hdFollowDelta[2] = d->posCurr.z & 0xff;
    s_hdFollowValid = 1;
}

/* The course moves by minus the sub-unit offset, in view space: -R * delta,
 * delta in 1/(256 * scale) units, as a GTE translation fraction (1/4096). */
static void NativeHD_SetCourseShift(const MATRIX *view, const int *delta, int scale)
{
    int r, c;
    for (r = 0; r < 3; r++)
    {
        s64 sum = 0;
        for (c = 0; c < 3; c++) sum += (s64)(s16)CTR_ReadU16LE(&view->m[r][c]) * delta[c];
        s_hdCourseShift[r] = (int)(-sum / (256 * scale));
    }
    s_hdCourseShiftReady = 1;
}

/* Turn the course shift on around course draws and off after them. */
void NativeHD_CourseShift(int on)
{
    int r;
    on = on && s_hdCourseShiftReady;
    if (on == s_hdCourseShiftOn) return;
    for (r = 0; r < 3; r++) g_nativeGteTranslationFraction[r] += on ? s_hdCourseShift[r] : -s_hdCourseShift[r];
    s_hdCourseShiftOn = on;
}

/* Any other view: an alpha-beta filter (1/4, 1/16) of the whole-unit
 * positions keeps the sub-unit place of steady motion, even to about an
 * eighth of a unit where whole units were a unit off, with no lag at a
 * constant speed. A jump of more than 64 units is a cut and starts it again. */
static void NativeHD_FilterCamera(struct GameTracker *gGT, const SVec3 *camera)
{
    int axis, cut = !s_hdCamEstimateValid || s_hdCamLevel != gGT->level1;
    int position[3];
    for (axis = 0; axis < 3; axis++)
    {
        position[axis] = NativeHD_VecAxis(camera, axis) * 256;
        if (!cut)
        {
            int residual = position[axis] - (s_hdCamEstimate[axis] + s_hdCamStep[axis]);
            if (residual > NATIVE_HD_CAMERA_CUT || residual < -NATIVE_HD_CAMERA_CUT) cut = 1;
        }
    }
    s_hdCamLevel = gGT->level1;
    s_hdCamEstimateValid = 1;
    for (axis = 0; axis < 3; axis++)
    {
        int predicted, residual, delta;
        if (cut)
        {
            s_hdCamEstimate[axis] = position[axis];
            s_hdCamStep[axis] = 0;
            s_hdDelta[axis] = 0;
            continue;
        }
        predicted = s_hdCamEstimate[axis] + s_hdCamStep[axis];
        residual = position[axis] - predicted;
        s_hdCamEstimate[axis] = predicted + residual / 4;
        s_hdCamStep[axis] += residual / 16;
        delta = s_hdCamEstimate[axis] - position[axis];
        if (delta > NATIVE_HD_CAMERA_DELTA_LIMIT) delta = NATIVE_HD_CAMERA_DELTA_LIMIT;
        if (delta < -NATIVE_HD_CAMERA_DELTA_LIMIT) delta = -NATIVE_HD_CAMERA_DELTA_LIMIT;
        s_hdDelta[axis] = delta;
    }
}

/* This update's sub-unit camera offset, once: from its midpoint, which runs
 * first, or its own frame. camera is the update's whole-unit camera. */
static void NativeHD_UpdateCameraDelta(struct GameTracker *gGT, const SVec3 *camera)
{
    if (s_hdDeltaDone) return;
    s_hdDeltaDone = 1;
    if (!g_nativeHDSmoothCamera || gGT->numPlyrCurrGame != 1 || gGT->level1 == NULL)
    {
        s_hdDeltaValid = 0;
        s_hdCamEstimateValid = 0;
    }
    else if (s_hdFollowValid)
    {
        memcpy(s_hdDelta, s_hdFollowDelta, sizeof(s_hdDelta));
        s_hdDeltaValid = 1;
        s_hdCamEstimateValid = 0;
    }
    else if ((gGT->gameMode1 & PAUSE_ALL) == 0)
    {
        NativeHD_FilterCamera(gGT, camera);
        s_hdDeltaValid = 1;
    }
    s_hdFollowValid = 0;
}

/* Before an update's own instances and geometry draw: its camera offset,
 * which the next update's midpoint averages with its own. */
void NativeHD_PrepareCourseShift(struct GameTracker *gGT)
{
    NativeHD_CourseShift(0);
    s_hdCourseShiftReady = 0;
    NativeHD_UpdateCameraDelta(gGT, &gGT->pushBuffer[0].pos);
    if (s_hdDeltaValid) NativeHD_SetCourseShift(&gGT->pushBuffer[0].matrix_ViewProj, s_hdDelta, 1);
    memcpy(s_hdPreviousDelta, s_hdDelta, sizeof(s_hdPreviousDelta));
    s_hdPreviousValid = s_hdDeltaValid;
    s_hdDeltaDone = 0;
}

/* Widescreen draws the world across the screen and squeezes the authored
 * 4:3 UI to its middle. A world view in a menu's window (character and track
 * selection) sits inside UI frames: it is squeezed with them and keeps its
 * 4:3 projection (PushBuffer.c), else it spills past its frame. */
int NativeHD_IsMenuWindow(const struct PushBuffer *pb)
{
    const struct GameTracker *gGT = sdata->gGT;
    return g_nativeHDWidescreen && pb != &gGT->pushBuffer_UI && (gGT->gameMode1 & MAIN_MENU) != 0 && (s16)pb->rect.w < 0x200;
}

/* The HUD squeeze centres the authored 512-wide layout on the screen: PSX x
 * 0 lands 85 of its 1.875-pixel units in from the edge. Outer elements move
 * out by 55 of them: the 4:3 layout's edge elements (x 10, the weapon and
 * place number) land 75 pixels (5.9%) in, inside a TV's title-safe 90%. The
 * full 85 put them 19 pixels in, where overscan hid the weapon. */
#define NATIVE_HD_SPLIT_HUD_MARGIN 55

static int NativeHD_DivRound3(int value)
{
    return value >= 0 ? (value + 1) / 3 : -((1 - value) / 3);
}

/* Three and four players: each viewport is a 16:9 quarter of the screen,
 * but the squeeze keeps the 4:3 layout around the screen's centre, which
 * pulled every player's outer elements (place number, weapon, meters) in
 * over the kart. Anchor each element to the nearer side of its viewport:
 * outer-half elements move out by NATIVE_HD_SPLIT_HUD_MARGIN, to the
 * screen's title-safe edge; inner ones already keep their 4:3 distance
 * from the centre. Groups (a place number and its suffix; the fruit, its count and
 * shine) lie in one half and keep their spacing. The shines draw in their
 * player's viewport, relative to its origin. Widescreen only, once. */
void NativeHD_WidenSplitScreenHud(void)
{
    static int widened;
    struct UiElement2D *tables[4] = {data.hud_4P_P1, data.hud_4P_P2, data.hud_4P_P3, data.hud_4P_P4};
    int player, slot;
    if (widened || !g_nativeHDWidescreen) return;
    widened = 1;
    for (player = 0; player < 4; player++)
    {
        /* PushBuffer_Init: right-hand viewports start at 0x103; all are 0xfd wide. */
        int right = player & 1, left = right ? 0x103 : 0, middle = left + 0xfd / 2;
        for (slot = 0; slot < UI_HUD_SLOT_COUNT; slot++)
        {
            struct UiElement2D *element = &tables[player][slot];
            int x = element->x;
            if (slot == UI_HUD_SLOT_BATTLE_WEAPON_BG || slot == UI_HUD_SLOT_RACING_WEAPON_BG) x += left;
            if (right ? x > middle : x < middle)
                element->x = (s16)(element->x + (right ? NATIVE_HD_SPLIT_HUD_MARGIN : -NATIVE_HD_SPLIT_HUD_MARGIN));
        }
    }
}

/* Where HUD text centred on a viewport goes. Centred on a 3/4-player
 * viewport, the squeeze put it 81 pixels towards the screen's middle; aim
 * it at the viewport's own centre instead. */
int NativeHD_ViewportMidX(const struct PushBuffer *pb)
{
    int mid = pb->rect.x + (pb->rect.w >> 1);
    if (g_nativeHDWidescreen && sdata->gGT->numPlyrCurrGame >= 3) mid = NativeHD_DivRound3(4 * mid - 256);
    return mid;
}

/* Draw-only copies of the authored frame's other layers, from the current
 * simulation state. Confetti draws with its update paused; window fades and
 * the FINAL LAP text draw, then their steps are undone. The UI window's fade
 * belongs to the HUD replay. */
static void NativeHD_DrawConfetti(struct GameTracker *gGT)
{
    int i;
    if ((gGT->renderFlags & RENDER_FLAG_CONFETTI) == 0) return;
    for (i = 0; i < gGT->numWinners; i++)
        DrawConfetti(&gGT->pushBuffer[gGT->winnerIndex[i]], &gGT->backBuffer->primMem, &gGT->confetti, gGT->frameTimer_Confetti, PAUSE_ALL);
}

static void NativeHD_DrawFades(struct GameTracker *gGT)
{
    int i;
    for (i = 0; i < gGT->numPlyrCurrGame; i++)
    {
        struct PushBuffer *pb = &gGT->pushBuffer[i];
        s16 value = pb->fadeFromBlack_currentValue;
        PushBuffer_FadeOneWindow(pb);
        pb->fadeFromBlack_currentValue = value;
    }
}

static void NativeHD_DrawFinalLap(struct GameTracker *gGT)
{
    u16 timers[4];
    memcpy(timers, sdata->finalLapTextTimer, sizeof(timers));
    DrawFinalLap(gGT);
    memcpy(sdata->finalLapTextTimer, timers, sizeof(timers));
}

static s16 NativeHD_VecAxis(const SVec3 *v, int axis)
{
    return axis == 0 ? v->x : (axis == 1 ? v->y : v->z);
}

static void NativeHD_SetVecAxis(SVec3 *v, int axis, s16 value)
{
    if (axis == 0) v->x = value;
    else if (axis == 1) v->y = value;
    else v->z = value;
}

static s16 NativeHD_AngleMidpoint(s16 previous, s16 current)
{
    int delta = ((current - previous + 0x800) & 0xfff) - 0x800;
    return (s16)((current - delta / 2) & 0xfff);
}

/* Match DotLights' visual state without its sound trigger or previous-timer
 * store. Countdown lights use the world OT rather than the cached UI OT. */
static void NativeHD_DrawCountdown(struct GameTracker *gGT)
{
    s32 timer = gGT->trafficLightsTimer;
    s32 posY = 0x1000;
    if (timer < -0x3bf) return;
    if (timer <= 0 || timer > 0xb40)
    {
        s32 value = (timer <= 0 ? timer + 0x3c0 : 0xf00 - timer) * 0x1000;
        s32 quotient = (s32)(((s64)value * -0x77777777) >> 32);
        posY = ((quotient + value) >> 9) - (value >> 31);
    }
    DotLights_Video(gGT, timer <= 0xb40, timer <= 0x780, timer <= 0x3c0, timer <= 0, posY);
}

static void NativeHD_InterpolateMatrix(MATRIX *out, const MATRIX *previous, const MATRIX *current)
{
    int row, col;
    float mid[3][3];
    *out = *current;
    /* Instance translations are native; rotation halfwords remain LE. */
    for (row = 0; row < 3; row++)
        out->t[row] = current->t[row] + (previous->t[row] - current->t[row]) / 2;
    /* Halving the sum of two rotations shortens each axis by the cosine of
     * half the turn between them: the hub warp pad's beam, which jumps 45 to
     * 270 degrees every other update, collapsed on midpoints and flickered.
     * Keep each axis at its average length; past a quarter turn there is no
     * pose to blend, so the midpoint keeps the current rotation. */
    for (col = 0; col < 3; col++)
    {
        float previousLength = 0, currentLength = 0, midLength = 0, length;
        for (row = 0; row < 3; row++)
        {
            float a = (s16)CTR_ReadU16LE(&previous->m[row][col]);
            float b = (s16)CTR_ReadU16LE(&current->m[row][col]);
            mid[row][col] = (a + b) * 0.5f;
            previousLength += a * a;
            currentLength += b * b;
            midLength += mid[row][col] * mid[row][col];
        }
        length = (sqrtf(previousLength) + sqrtf(currentLength)) * 0.5f;
        if (midLength < length * length * 0.5f) return;
        if (midLength > 0)
        {
            float scale = length / sqrtf(midLength);
            for (row = 0; row < 3; row++) mid[row][col] *= scale;
        }
    }
    for (row = 0; row < 3; row++)
        for (col = 0; col < 3; col++)
        {
            float value = mid[row][col];
            CTR_WriteU16LE(&out->m[row][col], (u16)(s16)(value < 0 ? value - 0.5f : value + 0.5f));
        }
}

void NativeHD_RenderIntermediate(struct GameTracker *gGT)
{
    struct Instance *inst;
    struct PushBuffer savedCamera;
    struct DB savedDB;
    MATRIX previousView, currentView;
    SVec3 currentPosition, currentRotation;
    int count, i, j, canInterpolate;
    u32 *ot, rootChain;
    struct Level *level = gGT->level1;
    /* Every mode flips each second VBlank (RenderSubmit), so a midpoint fits
     * menus, the hub, cutscenes and results as well as races. Setting 2 keeps
     * those on the original route, as earlier builds did. */
    u32 originalRouteModes = LOADING | PAUSE_ALL;
    if (g_nativeHDEnableInterpolation == 2) originalRouteModes |= MAIN_MENU | GAME_CUTSCENE | ADVENTURE_ARENA | END_OF_RACE;

    /* Loading, split-screen and pause remain on the original route.
     * Reset history across transitions and camera cuts to avoid blending
     * unrelated scenes or interpolating a respawn across the course.
     * The checkered flag also stays there while it slides off over the race
     * intro: RaceFlag_GetOT advances its slide when drawn and the flag is not
     * in the HUD replay, so a midpoint would show alternate frames without it.
     * While the GPU can't draw two frames an update in time ([graphics]
     * steady), each update draws only its own, so the updates stay even. */
    if (!g_nativeHDEnableInterpolation || !NativeRenderer_MidpointsFit() || sdata->Loading.stage != LOAD_IDLE || level == NULL || level->ptr_mesh_info == NULL ||
        gGT->numPlyrCurrGame != 1 || (gGT->gameMode1 & originalRouteModes) != 0 ||
        (gGT->renderFlags & (RENDER_FLAG_DRAW_LEVEL | RENDER_FLAG_RENDER_BUCKET | RENDER_FLAG_CHECKERED_FLAG)) != (RENDER_FLAG_DRAW_LEVEL | RENDER_FLAG_RENDER_BUCKET))
    {
        s_hdLevel = NULL;
        s_hdPoseCount = 0;
        NativeGpu_BeginHUDCapture();
        return;
    }

    savedCamera = gGT->pushBuffer[0];
    currentPosition = savedCamera.pos;
    currentRotation = savedCamera.rot;
    count = 0;
    for (inst = (struct Instance *)gGT->JitPools.instance.taken.first;
         inst != NULL && count < NATIVE_HD_INSTANCE_LIMIT; inst = inst->next)
    {
        s_hdCurrent[count].instance = inst;
        s_hdCurrent[count].model = inst->model;
        s_hdCurrent[count].thread = inst->thread;
        s_hdCurrent[count].matrix = inst->matrix;
        s_hdCurrent[count].flags = inst->flags;
        count++;
    }

    canInterpolate = inst == NULL && s_hdLevel == level && s_hdPoseCount > 0 && NativeGpu_HasHUDCapture();
    for (i = 0; i < 3; i++)
    {
        int delta = (int)NativeHD_VecAxis(&currentPosition, i) - NativeHD_VecAxis(&s_hdCameraPosition, i);
        int angleDelta = ((NativeHD_VecAxis(&currentRotation, i) - NativeHD_VecAxis(&s_hdCameraRotation, i) + 0x800) & 0xfff) - 0x800;
        if (delta > 1024 || delta < -1024 || angleDelta > 256 || angleDelta < -256) canInterpolate = 0;
    }
    if (canInterpolate)
    {
        Platform_WatchStage("midpoint-draw");
        NativeHD_IndexPreviousPoses();
        savedDB = *gGT->backBuffer;
        ot = gGT->otSwapchainDB[gGT->swapchainIndex];
        memcpy(s_hdOTBackup, ot, sizeof(s_hdOTBackup));
        /* A private render interval uses the already-reset DB and rewinds its
         * primitive/OT cursors afterwards. GPU uploads copy these packets.
         * Keep what game logic already linked into the world slots and the
         * root slot (clock blur, lens flare, rescue dust): those draw only
         * there. The UI slots come from the HUD replay instead, and the root
         * slot draws after it, as on authored frames. */
        rootChain = ot[0];
        ClearOTagR(ot, 6);
        /* The push buffer still holds the last frame's view: the frame's own
         * render builds this update's later (RainLogic). Build it now, from
         * this update's camera, to average the two. */
        previousView = savedCamera.matrix_ViewProj;
        PushBuffer_UpdateFrustum(&gGT->pushBuffer[0]);
        currentView = gGT->pushBuffer[0].matrix_ViewProj;
        /* Append after any packets created earlier in MainMain. Rewinding
         * their bytes would corrupt the restored OT (notably demo text). */
        for (i = 0; i < 3; i++)
        {
            int current = NativeHD_VecAxis(&currentPosition, i);
            NativeHD_SetVecAxis(&gGT->pushBuffer[0].pos, i, (s16)(current + (NativeHD_VecAxis(&s_hdCameraPosition, i) - current) / 2));
            NativeHD_SetVecAxis(&gGT->pushBuffer[0].rot, i, NativeHD_AngleMidpoint(NativeHD_VecAxis(&s_hdCameraRotation, i), NativeHD_VecAxis(&currentRotation, i)));
        }
        for (i = 0; i < count; i++)
        {
            /* Screenspace models (rank digit, fruit and rewards) and other
             * UI-camera models (hint and pause menus) already belong to the
             * decoded HUD replay. Their OT lies at the tail of the world
             * chain; queueing them here draws a second copy before the
             * normal UI draw environment has been installed. */
            if ((s_hdCurrent[i].flags & SCREENSPACE_INSTANCE) != 0 ||
                INST_GETIDPP(s_hdCurrent[i].instance)[0].pushBuffer == &gGT->pushBuffer_UI)
            {
                s_hdCurrent[i].instance->flags |= HIDE_MODEL;
                continue;
            }
            j = NativeHD_FindPreviousPose(s_hdCurrent[i].instance, s_hdCurrent[i].model, s_hdCurrent[i].thread);
            if (j >= 0)
            {
                    int axis, continuous = 1;
                    for (axis = 0; axis < 3; axis++)
                    {
                        int delta = s_hdCurrent[i].matrix.t[axis] - s_hdPrevious[j].matrix.t[axis];
                        if (delta > 1024 || delta < -1024) continuous = 0;
                    }
                    if (continuous) NativeHD_InterpolateMatrix(&s_hdCurrent[i].instance->matrix, &s_hdPrevious[j].matrix, &s_hdCurrent[i].matrix);
            }
        }
        /* The frustum from the midpoint camera culls; the view draws. */
        PushBuffer_UpdateFrustum(&gGT->pushBuffer[0]);
        NativeHD_AverageView(&gGT->pushBuffer[0].matrix_ViewProj, &previousView, &currentView, &s_hdCameraPosition, &currentPosition);
        /* The course shift halfway: the mean of both updates' offsets, as
         * the view is the mean of their whole-unit cameras. */
        s_hdCourseShiftReady = 0;
        NativeHD_UpdateCameraDelta(gGT, &currentPosition);
        if (s_hdDeltaValid && s_hdPreviousValid)
        {
            int sum[3];
            for (i = 0; i < 3; i++) sum[i] = s_hdDelta[i] + s_hdPreviousDelta[i];
            NativeHD_SetCourseShift(&gGT->pushBuffer[0].matrix_ViewProj, sum, 2);
        }
        MainFrame_VisMemFullFrame(gGT, level);
        /* Texture selection is an idempotent function of the current timer;
         * use the same selected frames in both renders of this update. */
        if (gGT->visMem1 != NULL) CTR_CycleTex_LEV(level->ptr_anim_tex, gGT->timer);
        g_nativeHDIntermediate = 1;
        NativeGpu_SetHUDCapture(0);
        /* These draw paths use the pause argument to suppress scroll/count
         * updates. The main frame remains their only simulation update. */
        if ((gGT->renderFlags & RENDER_FLAG_RAIN) != 0)
            RenderWeather(&gGT->pushBuffer[0], &gGT->backBuffer->primMem, &gGT->rainBuffer[0], 1, PAUSE_ALL);
        if ((gGT->renderFlags & RENDER_FLAG_BEAKER_RAIN) != 0)
            RedBeaker_RenderRain(&gGT->pushBuffer[0], &gGT->backBuffer->primMem, &gGT->JitPools.rain, 1, PAUSE_ALL);
        if ((gGT->renderFlags & RENDER_FLAG_STARS) != 0 && gGT->stars.numStars != 0)
            RenderStars(&gGT->pushBuffer[0], &gGT->backBuffer->primMem, &gGT->stars, 1);
        NativeHD_DrawConfetti(gGT);
        NativeHD_DrawFinalLap(gGT);
        RenderBucket_QueueAllInstances(gGT);
        RenderAllNormalParticles(gGT);
        /* After every queue, including the midpoint: inherited effect depth
         * ranges (a newly spawned boost flame has none from a previous
         * render), per-view visibility, warp pad digits, skids, spider webs,
         * and the title trophy's binding. None of these keep state. */
        RenderAllFlag0x40(gGT);
        RenderAllTitleDPP(gGT);
        RenderBucket_ExecuteAllInstances(gGT);
        RenderAllTires(gGT);
        RenderAllShadows(gGT);
        RenderAllHeatParticles(gGT);
        NativeHD_DrawFades(gGT);
        NativeHD_CourseShift(1);
        RenderAllLevelGeometry(gGT, level, level->ptr_mesh_info);
        NativeHD_CourseShift(0);
        s_hdCourseShiftReady = 0;
        if ((gGT->gameMode1 & (GAME_CUTSCENE | ADVENTURE_ARENA | MAIN_MENU)) == 0) NativeHD_DrawCountdown(gGT);
        if ((gGT->renderFlags & RENDER_FLAG_CLEAR_BACK_BUFFER) != 0) CAM_ClearScreen(gGT);
        RenderDispEnv_World(gGT);
        PutDrawEnv(&gGT->backBuffer->drawEnv);
        PutDispEnv(&gGT->db[1 - gGT->swapchainIndex].dispEnv);
        DrawOTag(&gGT->pushBuffer[0].ptrOT[0x3ff]);
        NativeGpu_ReplayHUD();
        if (rootChain != ot[0])
        {
            ot[0] = rootChain;
            DrawOTag(ot);
        }
        memset(g_nativeGteTranslationFraction, 0, sizeof(g_nativeGteTranslationFraction));
        /* Consume only the first of the retail frame's two VBlanks. The
         * regular RenderVSYNC handles the remainder before the current pose. */
        Platform_WatchStage("midpoint-present");
#if defined(CTR_XSDK)
        /* The GPU draws the scene while the CPU waits for the VBlank. */
        DrawSync(0);
        NativeRenderer_SubmitScene();
#endif
        Platform_WaitUntilVBlank(Platform_GetVBlankCount() + 1);
        DrawSync(0);
        Platform_EndFrame();
        g_nativeHDIntermediate = 0;
        for (i = 0; i < count; i++)
        {
            s_hdCurrent[i].instance->matrix = s_hdCurrent[i].matrix;
            s_hdCurrent[i].instance->flags = s_hdCurrent[i].flags;
        }
        gGT->pushBuffer[0] = savedCamera;
        *gGT->backBuffer = savedDB;
        memcpy(ot, s_hdOTBackup, sizeof(s_hdOTBackup));
        MainFrame_VisMemFullFrame(gGT, level);
    }
    memcpy(s_hdPrevious, s_hdCurrent, count * sizeof(s_hdPrevious[0]));
    s_hdPoseCount = count;
    s_hdLevel = level;
    s_hdCameraPosition = currentPosition;
    s_hdCameraRotation = currentRotation;
    NativeGpu_BeginHUDCapture();
}
#endif
