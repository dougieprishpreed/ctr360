#include <common.h>

#ifdef _XBOX
/* Render-only midpoint frames. The retail simulation, input sampling, audio,
 * race timers and animation ticks retain their existing cadence. Never call
 * MainFrame_GameLogic, UI/menu updates, particle ticks or pickups here. */
void NativeGpu_BeginHUDCapture(void);
void NativeGpu_ReplayHUD(void);
void NativeGpu_SetHUDCapture(int enabled);
int NativeGpu_HasHUDCapture(void);

#define NATIVE_HD_INSTANCE_LIMIT 512
struct NativeHDPose
{
    struct Instance *instance;
    struct Model *model;
    MATRIX matrix;
    u32 flags;
};
static struct NativeHDPose s_hdPrevious[NATIVE_HD_INSTANCE_LIMIT];
static struct NativeHDPose s_hdCurrent[NATIVE_HD_INSTANCE_LIMIT];
static int s_hdPoseCount;
static struct Level *s_hdLevel;
static SVec3 s_hdCameraPosition;
static SVec3 s_hdCameraRotation;
static u32 s_hdOTBackup[0x406];
int g_nativeHDIntermediate;
int g_nativeHDEnableInterpolation = 1;

static void NativeHD_BindInheritedDepthRanges(struct GameTracker *gGT)
{
    if ((gGT->renderFlags & RENDER_FLAG_EFFECT_BUCKETS) == 0) return;
    /* These visuals skip their own OT allocation and inherit the queued
     * owner's depth range. Rebind after every queue, including the midpoint;
     * a newly spawned boost flame has no valid range from a previous render.
     * Keep only the render bindings from RenderAllFlag0x40 here. */
    if (LOAD_IsOpen_RacingOrBattle())
    {
        RB_Burst_ProcessBucket(gGT->threadBuckets[BURST].thread);
        RB_Blowup_ProcessBucket(gGT->threadBuckets[BLOWUP].thread);
    }
    VehTurbo_ProcessBucket(gGT->threadBuckets[TURBO].thread);
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
    *out = *current;
    for (row = 0; row < 3; row++)
    {
        /* Instance translations are native; rotation halfwords remain LE. */
        out->t[row] = current->t[row] + (previous->t[row] - current->t[row]) / 2;
        for (col = 0; col < 3; col++)
        {
            int a = (s16)CTR_ReadU16LE(&previous->m[row][col]);
            int b = (s16)CTR_ReadU16LE(&current->m[row][col]);
            CTR_WriteU16LE(&out->m[row][col], (u16)(b + (a - b) / 2));
        }
    }
}

void NativeHD_RenderIntermediate(struct GameTracker *gGT)
{
    struct Instance *inst;
    struct PushBuffer savedCamera;
    struct DB savedDB;
    SVec3 currentPosition, currentRotation;
    int count, i, j, canInterpolate;
    u32 *ot;
    struct Level *level = gGT->level1;

    /* Loading, menus, split-screen and pause remain on the original route.
     * Reset history across transitions and camera cuts to avoid blending
     * unrelated scenes or interpolating a respawn across the course. */
    if (!g_nativeHDEnableInterpolation || sdata->Loading.stage != LOAD_IDLE || level == NULL || level->ptr_mesh_info == NULL ||
        gGT->numPlyrCurrGame != 1 || (gGT->gameMode1 & (LOADING | MAIN_MENU | GAME_CUTSCENE | ADVENTURE_ARENA | PAUSE_ALL | END_OF_RACE)) != 0 ||
        (gGT->renderFlags & (RENDER_FLAG_DRAW_LEVEL | RENDER_FLAG_RENDER_BUCKET)) != (RENDER_FLAG_DRAW_LEVEL | RENDER_FLAG_RENDER_BUCKET))
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
        savedDB = *gGT->backBuffer;
        ot = gGT->otSwapchainDB[gGT->swapchainIndex];
        memcpy(s_hdOTBackup, ot, sizeof(s_hdOTBackup));
        /* A private render interval uses the already-reset DB and rewinds its
         * primitive/OT cursors afterwards. GPU uploads copy these packets. */
        ClearOTagR(ot, 0x406);
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
            /* Screenspace models (rank digit, fruit and rewards) already
             * belong to the decoded HUD replay. Their OT lies at the tail
             * of the world chain; queueing them here draws a second copy
             * before the normal UI draw environment has been installed. */
            if ((s_hdCurrent[i].flags & SCREENSPACE_INSTANCE) != 0)
            {
                s_hdCurrent[i].instance->flags |= HIDE_MODEL;
                continue;
            }
            for (j = 0; j < s_hdPoseCount; j++)
            {
                if (s_hdCurrent[i].instance == s_hdPrevious[j].instance && s_hdCurrent[i].model == s_hdPrevious[j].model)
                {
                    int axis, continuous = 1;
                    for (axis = 0; axis < 3; axis++)
                    {
                        int delta = s_hdCurrent[i].matrix.t[axis] - s_hdPrevious[j].matrix.t[axis];
                        if (delta > 1024 || delta < -1024) continuous = 0;
                    }
                    if (continuous) NativeHD_InterpolateMatrix(&s_hdCurrent[i].instance->matrix, &s_hdPrevious[j].matrix, &s_hdCurrent[i].matrix);
                    break;
                }
            }
        }
        PushBuffer_UpdateFrustum(&gGT->pushBuffer[0]);
        MainFrame_VisMemFullFrame(gGT, level);
        /* Texture selection is an idempotent function of the current timer;
         * use the same selected frames in both renders of this update. */
        if (gGT->visMem1 != NULL) CTR_CycleTex_LEV(level->ptr_anim_tex, gGT->timer);
        g_nativeHDIntermediate = 1;
        NativeGpu_SetHUDCapture(0);
        RenderBucket_QueueAllInstances(gGT);
        RenderAllNormalParticles(gGT);
        NativeHD_BindInheritedDepthRanges(gGT);
        RenderBucket_ExecuteAllInstances(gGT);
        RenderAllTires(gGT);
        RenderAllShadows(gGT);
        RenderAllLevelGeometry(gGT, level, level->ptr_mesh_info);
        NativeHD_DrawCountdown(gGT);
        if ((gGT->renderFlags & RENDER_FLAG_CLEAR_BACK_BUFFER) != 0) CAM_ClearScreen(gGT);
        RenderDispEnv_World(gGT);
        PutDrawEnv(&gGT->backBuffer->drawEnv);
        PutDispEnv(&gGT->db[1 - gGT->swapchainIndex].dispEnv);
        DrawOTag(&gGT->pushBuffer[0].ptrOT[0x3ff]);
        NativeGpu_ReplayHUD();
        /* Consume only the first of the retail frame's two VBlanks. The
         * regular RenderVSYNC handles the remainder before the current pose. */
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
