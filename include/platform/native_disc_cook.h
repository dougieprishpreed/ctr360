#ifndef NATIVE_DISC_COOK_H
#define NATIVE_DISC_COOK_H

#include <stddef.h>
#include <stdint.h>

/* The PC converter's work on the console: the player's own .bin, through the
 * cook recipe tools/xsdk/make_cook_recipe.py records, into assets\ctr-u.bin. */

enum NativeDiscCookResult
{
    NATIVE_DISC_COOK_OK = 0,
    NATIVE_DISC_COOK_BAD_RECIPE,
    NATIVE_DISC_COOK_WRONG_SIZE, /* not the size of the USA disc's image */
    NATIVE_DISC_COOK_READ_FAILED,
    NATIVE_DISC_COOK_WRITE_FAILED,
    NATIVE_DISC_COOK_MISMATCH, /* converted, but not into the image the recipe makes */
};

struct NativeDiscCookRecipe
{
    const unsigned char *bytes, *end;
    uint32_t imageBytes, crc, runs;
};

/* Called after each stretch of sectors is written. */
typedef void (*NativeDiscCookProgress)(void *context, uint32_t sectorsDone, uint32_t sectors);

int NativeDiscCook_OpenRecipe(struct NativeDiscCookRecipe *recipe, const void *bytes, size_t length);
/* Writes destination from source, then checks it whole; removes it unless the result is OK. */
int NativeDiscCook_Convert(const struct NativeDiscCookRecipe *recipe, const char *source, const char *destination,
                           NativeDiscCookProgress progress, void *context);
/* A file in folder (ending in a separator) named *.bin in any case, preferring one of imageBytes: folder + name
 * in out, and its size. 0 if there is none. */
int NativeDiscCook_FindImage(const char *folder, uint64_t imageBytes, char *out, size_t outBytes, uint64_t *bytes);
/* Images converted before 1.0.4.0 kept Pinstripe's boss heads (BIGFILE entries 454, 455, 464, 465) as on the
 * disc. With patches from tools/xsdk/make_cook_recipe.py --entry-patches, reverses an entry's fields in memory
 * as the cooker now does, when its bytes are the old ones by CRC-32: 1 patched, 0 nothing to do, -1 damaged
 * patches or a result that isn't the cooker's, the bytes then left as they were. */
int NativeDiscCook_PatchEntry(const void *patches, size_t patchBytes, uint32_t entry, unsigned char *bytes,
                              size_t length);

#endif
