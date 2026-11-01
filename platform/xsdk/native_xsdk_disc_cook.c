/* First start without assets\ctr-u.bin: the player's own .bin beside
 * default.xex becomes it on the console, through the cook recipe built into
 * the XEX (platform/xsdk/cook_recipe.bin, from tools/xsdk/make_cook_recipe.py),
 * behind a screen of the SDK's text with a progress bar. The screen has the
 * GPU before the game's renderer takes it. Once the image is in place the
 * .bin and its .cue are deleted and the game starts again, finding the image
 * as any later start does. */
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <xsdk/gpu.h>
#include <xsdk/present.h>
#include <xsdk/text.h>
#include <xsdk/xam.h>
#include "platform/native_disc_cook.h"

#ifndef CTR360_COOK_RECIPE
#error "build.sh passes CTR360_COOK_RECIPE, the path of platform/xsdk/cook_recipe.bin"
#endif
__asm__(".section .rodata.ctr360_cook_recipe,\"a\"\n"
        "\t.balign 4\n"
        "\t.globl ctr360CookRecipe\n"
        "ctr360CookRecipe:\n"
        "\t.incbin \"" CTR360_COOK_RECIPE "\"\n"
        "\t.globl ctr360CookRecipeEnd\n"
        "ctr360CookRecipeEnd:\n"
        "\t.previous\n");
extern const unsigned char ctr360CookRecipe[], ctr360CookRecipeEnd[];

/* Pinstripe's boss heads, which images converted before 1.0.4.0 kept as on
 * the disc (platform/xsdk/entry_patches.bin, from make_cook_recipe.py
 * --entry-patches): fixed in memory as the game reads them. */
#ifndef CTR360_ENTRY_PATCHES
#error "build.sh passes CTR360_ENTRY_PATCHES, the path of platform/xsdk/entry_patches.bin"
#endif
__asm__(".section .rodata.ctr360_entry_patches,\"a\"\n"
        "\t.balign 4\n"
        "\t.globl ctr360EntryPatches\n"
        "ctr360EntryPatches:\n"
        "\t.incbin \"" CTR360_ENTRY_PATCHES "\"\n"
        "\t.globl ctr360EntryPatchesEnd\n"
        "ctr360EntryPatchesEnd:\n"
        "\t.previous\n");
extern const unsigned char ctr360EntryPatches[], ctr360EntryPatchesEnd[];

void Platform_FixLoadedFile(int entry, void *bytes, int length)
{
    int result;
    if (entry < 0 || bytes == NULL || length <= 0) return;
    result = NativeDiscCook_PatchEntry(ctr360EntryPatches, (size_t)(ctr360EntryPatchesEnd - ctr360EntryPatches),
                                       (uint32_t)entry, bytes, (size_t)length);
    if (result > 0)
        Platform_Log("[disc] entry %d fixed as read: an image converted before 1.0.4.0 kept it as on the disc\n", entry);
    else if (result < 0)
        Platform_LogError("[disc] entry %d: the fix for older images doesn't apply; the XEX may be damaged\n", entry);
}

#define COOK_FOLDER "game:/"
#define COOK_IMAGE "game:/assets/ctr-u.bin"
#define COOK_PART "game:/assets/ctr-u.bin.part"
/* Launch data of the start after a conversion, which logs the rest of it. */
#define COOK_NOTE "ctr360-disc: "
#define COOK_FULL_BLOCK "\xe2\x96\x88"
#define COOK_LIGHT_SHADE "\xe2\x96\x91"
enum
{
    COOK_MARGIN = 80,
    COOK_BAR_CELLS = 40,
    COOK_LINE_GAP = 8,
    COOK_FRAME_MS = 100,
    COOK_BEGIN_TIMEOUT_MS = 5000,
    COOK_TEXT = 0xFFFFFFFF,
    COOK_DIM = 0xFFA0A0A0,
    COOK_BAR = 0xFFF0A020,
};

static uint32_t cookWidth, cookHeight, cookScale;
static int cookScreenOpen;

static int CookScreen_Open(void)
{
    if (!NT_SUCCESS(xsdk_gpu_open())) return 0;
    if (!NT_SUCCESS(xsdk_present_open(XSDK_DISPLAY_720P, 2, 1, &cookWidth, &cookHeight)))
    {
        xsdk_gpu_close();
        return 0;
    }
    if (!NT_SUCCESS(xsdk_text_open()))
    {
        xsdk_present_close();
        xsdk_gpu_close();
        return 0;
    }
    /* 64 columns at 720p; an interlaced output gets 640x480 and half the size. */
    cookScale = cookWidth >= 1280 ? 2 : 1;
    cookScreenOpen = 1;
    return 1;
}

static void CookScreen_Close(void)
{
    if (!cookScreenOpen) return;
    xsdk_text_close();
    xsdk_present_close();
    xsdk_gpu_close();
    cookScreenOpen = 0;
}

/* ASCII text wrapped at spaces to the screen's width; returns the y below it. */
static int CookScreen_Paragraph(int y, uint32_t scale, uint32_t argb, const char *text)
{
    const int columns = ((int)cookWidth - 2 * COOK_MARGIN) / (XSDK_TEXT_CELL_WIDTH * (int)scale);
    char line[160];
    while (*text != 0)
    {
        int length = (int)strlen(text), take = length;
        const char *newline = strchr(text, '\n');
        if (newline != NULL && newline - text < take) take = (int)(newline - text);
        if (take > columns)
        {
            take = columns;
            while (take > 0 && text[take] != ' ') take--;
            if (take == 0) take = columns;
        }
        if (take >= (int)sizeof(line)) take = (int)sizeof(line) - 1;
        memcpy(line, text, (size_t)take);
        line[take] = 0;
        xsdk_text_draw(COOK_MARGIN, y, scale, argb, line);
        y += XSDK_TEXT_CELL_HEIGHT * (int)scale + COOK_LINE_GAP;
        text += take;
        while (*text == ' ' || *text == '\n') text++;
    }
    return y;
}

/* One frame: a title, a paragraph, then a bar (percent 0 to 100, or -1 for none) and a line under it. */
static void CookScreen_Frame(const char *title, const char *body, int percent, const char *footer)
{
    static const char cover[] = COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK
        COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK
        COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK COOK_FULL_BLOCK;
    uint32_t address;
    int y;
    if (!cookScreenOpen || !NT_SUCCESS(xsdk_present_begin(&address, COOK_BEGIN_TIMEOUT_MS))) return;
    xsdk_gpu_set_target(cookWidth, cookHeight);
    /* Black under the text: eDRAM holds anything until the first resolve clears it. */
    for (y = 0; y < (int)cookHeight; y += XSDK_TEXT_CELL_HEIGHT * 8) xsdk_text_draw(0, y, 8, 0xFF000000, cover);
    y = (int)cookHeight / 6;
    y = CookScreen_Paragraph(y, cookScale + 1, COOK_TEXT, title) + COOK_LINE_GAP * 2;
    y = CookScreen_Paragraph(y, cookScale, COOK_DIM, body) + COOK_LINE_GAP * 2;
    if (percent >= 0)
    {
        char bar[COOK_BAR_CELLS * 3 + 1], *at = bar;
        int i, filled = percent * COOK_BAR_CELLS / 100;
        for (i = 0; i < COOK_BAR_CELLS; i++)
        {
            memcpy(at, i < filled ? COOK_FULL_BLOCK : COOK_LIGHT_SHADE, 3);
            at += 3;
        }
        *at = 0;
        xsdk_text_draw(COOK_MARGIN, y, cookScale, COOK_BAR, bar);
        y += XSDK_TEXT_CELL_HEIGHT * (int)cookScale + COOK_LINE_GAP * 2;
    }
    if (footer != NULL) CookScreen_Paragraph(y, cookScale, COOK_TEXT, footer);
    xsdk_gpu_resolve(address, cookWidth, cookHeight, 0xFF000000);
    xsdk_present_end();
}

/* Shows the message until a button is pressed, then leaves for the dashboard. */
static void CookScreen_Fail(const char *title, const char *body)
{
    int released = 0;
    Platform_LogWarn("[disc] %s %s\n", title, body);
    for (;;)
    {
        XINPUT_STATE state;
        WORD buttons = 0;
        if (XInputGetState(0, &state) == ERROR_SUCCESS) buttons = state.Gamepad.wButtons;
        if (buttons == 0) released = 1;
        else if (released) break;
        Platform_WatchBeat();
        CookScreen_Frame(title, body, -1, "Press any button to exit.");
    }
    CookScreen_Close();
    Platform_Exit(1);
}

struct CookProgress
{
    char body[512];
    DWORD startMs, lastMs;
};

static void CookScreen_Progress(void *context, uint32_t done, uint32_t sectors)
{
    struct CookProgress *progress = context;
    const DWORD now = GetTickCount();
    char footer[96];
    Platform_WatchBeat();
    if (done != sectors && now - progress->lastMs < COOK_FRAME_MS) return;
    progress->lastMs = now;
    if (done > sectors / 20 && done < sectors)
    {
        const unsigned seconds = (unsigned)((uint64_t)(now - progress->startMs) * (sectors - done) / done / 1000);
        snprintf(footer, sizeof(footer), "%u%%, about %u minute%s left", (unsigned)((uint64_t)done * 100 / sectors),
                 seconds / 60 + 1, seconds / 60 ? "s" : "");
    }
    else snprintf(footer, sizeof(footer), "%u%%", (unsigned)((uint64_t)done * 100 / sectors));
    CookScreen_Frame("Converting your disc image", progress->body, (int)((uint64_t)done * 100 / sectors), footer);
}

/* 1 when it made the image and the game couldn't start again, so this start
 * has to look for the image anew; 0 when nothing changed. */
int NativeXsdk_PrepareDisc(void)
{
    struct NativeDiscCookRecipe recipe;
    struct CookProgress progress;
    struct stat info;
    char source[400], cue[400], body[512], note[XSDK_LAUNCH_DATA_MAX_BYTES + 1], self[300];
    const char *name;
    uint64_t bytes = 0;
    size_t noteBytes;
    int found, result;

    noteBytes = xsdk_launch_data(note, sizeof(note) - 1);
    note[noteBytes] = '\0';
    if (strncmp(note, COOK_NOTE, strlen(COOK_NOTE)) == 0) Platform_LogWarn("[disc] %s\n", note + strlen(COOK_NOTE));
    if (stat(COOK_IMAGE, &info) == 0 || stat("game:/assets/BIGFILE.BIG", &info) == 0) return 0;
    Platform_WatchStage("disc-convert");
    if (!NativeDiscCook_OpenRecipe(&recipe, ctr360CookRecipe, (size_t)(ctr360CookRecipeEnd - ctr360CookRecipe)))
    {
        Platform_LogError("[disc] the cook recipe in this XEX is damaged\n");
        return 0;
    }
    found = NativeDiscCook_FindImage(COOK_FOLDER, recipe.imageBytes, source, sizeof(source), &bytes);
    name = source + strlen(COOK_FOLDER);
    if (!CookScreen_Open())
    {
        Platform_LogError("[disc] no screen for the disc conversion\n");
        return 0;
    }
    if (!found)
    {
        CookScreen_Fail("CTR360 needs your disc image",
                        "Copy the .bin of your own Crash Team Racing disc (USA, SCUS-94426) into this folder, beside "
                        "default.xex, and start CTR360 again. It is converted here, on the console, once.\n"
                        "A PC can convert it instead, with the converter in the CTR360-Xbox360 zip.");
    }
    if (bytes != recipe.imageBytes)
    {
        snprintf(body, sizeof(body),
                 "%s is %lu bytes, so it isn't an image of the USA disc (SCUS-94426): that is a .bin of %lu bytes, "
                 "dumped with 2352-byte sectors. It was left as it is.",
                 name, (unsigned long)bytes, (unsigned long)recipe.imageBytes);
        CookScreen_Fail("This disc image can't be used", body);
    }
    mkdir("game:/assets", 0777);
    snprintf(progress.body, sizeof(progress.body),
             "%s becomes assets\\ctr-u.bin. This happens once and takes a few minutes: keep the console on. "
             "Then %s is deleted and the game starts.",
             name, name);
    progress.startMs = progress.lastMs = GetTickCount();
    CookScreen_Progress(&progress, 0, recipe.imageBytes / 2352);
    Platform_LogWarn("[disc] converting %s\n", source);
    result = NativeDiscCook_Convert(&recipe, source, COOK_PART, CookScreen_Progress, &progress);
    if (result == NATIVE_DISC_COOK_OK && rename(COOK_PART, COOK_IMAGE) != 0)
    {
        unlink(COOK_PART);
        result = NATIVE_DISC_COOK_WRITE_FAILED;
    }
    Platform_LogWarn("[disc] conversion of %s: result %d in %lu ms\n", source, result,
                     (unsigned long)(GetTickCount() - progress.startMs));
    switch (result)
    {
    case NATIVE_DISC_COOK_OK:
        break;
    case NATIVE_DISC_COOK_MISMATCH:
        snprintf(body, sizeof(body),
                 "%s has the USA disc's size but not its data, so the copy didn't come out as the game needs it. "
                 "%s was left as it is. A clean dump of the disc converts, here or on a PC.",
                 name, name);
        CookScreen_Fail("This disc image can't be used", body);
        break;
    case NATIVE_DISC_COOK_READ_FAILED:
        snprintf(body, sizeof(body), "%s couldn't be read to the end. It was left as it is.", name);
        CookScreen_Fail("The disc image couldn't be read", body);
        break;
    case NATIVE_DISC_COOK_WRITE_FAILED:
        snprintf(body, sizeof(body),
                 "assets\\ctr-u.bin couldn't be written. It needs %u MB free on this drive. %s was left as it is.",
                 (unsigned)(recipe.imageBytes / 1000000 + 1), name);
        CookScreen_Fail("The converted image couldn't be saved", body);
        break;
    default:
        CookScreen_Fail("This copy of CTR360 is damaged", "Its disc conversion data is damaged. Install CTR360 again.");
        break;
    }
    /* The image is in place: the .bin and a .cue of the same name go. */
    unlink(source);
    snprintf(cue, sizeof(cue), "%.*s.cue", (int)(strlen(source) - 4), source);
    unlink(cue);
    snprintf(cue, sizeof(cue), "%.*s.CUE", (int)(strlen(source) - 4), source);
    unlink(cue);
    Platform_LogWarn("[disc] %s converted into %s and deleted\n", source, COOK_IMAGE);
    CookScreen_Frame("Converting your disc image", progress.body, 100, "Done. Starting the game.");
    CookScreen_Close();
    /* A new start, as the player's own would be: the image is found from the
     * outset, and the renderer takes the GPU without the screen before it. */
    snprintf(note, sizeof(note), COOK_NOTE "the previous start converted %s in %lu ms", name,
             (unsigned long)(GetTickCount() - progress.startMs));
    name = ExLoadedImageName != NULL ? strrchr(ExLoadedImageName, '\\') : NULL;
    snprintf(self, sizeof(self), "game:/%s", name != NULL ? name + 1 : "default.xex");
    Platform_LogFlush();
    xsdk_launch(self, note, strlen(note) + 1);
    Platform_LogError("[disc] %s couldn't start again (errno %d); starting without that\n", self, errno);
    return 1;
}
