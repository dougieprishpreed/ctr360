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

static int NativeHD_FindPreviousPose(struct Instance *instance, struct Model *model)
{
    int probes;
    u32 slot = (((u32)instance >> 4) * 2654435761u) & (NATIVE_HD_POSE_HASH_SIZE - 1);
    for (probes = 0; probes < NATIVE_HD_POSE_HASH_SIZE; probes++)
    {
        int index = (int)s_hdPoseHash[slot] - 1;
        if (index < 0) return -1;
        if (s_hdPrevious[index].instance == instance && s_hdPrevious[index].model == model) return index;
        slot = (slot + 1) & (NATIVE_HD_POSE_HASH_SIZE - 1);
    }
    return -1;
}
static struct Level *s_hdLevel;
static SVec3 s_hdCameraPosition;
static SVec3 s_hdCameraRotation;
static u32 s_hdOTBackup[0x406];
int g_nativeHDIntermediate;
int g_nativeHDEnableInterpolation = 1;

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
     * in the HUD replay, so a midpoint would show alternate frames without it. */
    if (!g_nativeHDEnableInterpolation || sdata->Loading.stage != LOAD_IDLE || level == NULL || level->ptr_mesh_info == NULL ||
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
            j = NativeHD_FindPreviousPose(s_hdCurrent[i].instance, s_hdCurrent[i].model);
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
        PushBuffer_UpdateFrustum(&gGT->pushBuffer[0]);
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
        RenderAllLevelGeometry(gGT, level, level->ptr_mesh_info);
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
