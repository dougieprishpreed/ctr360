#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>
#include "platform/native_disc_cook.h"

#ifndef O_BINARY
#define O_BINARY 0
#endif

/* The player's .bin holds raw 2352-byte sectors, each with 2048 data bytes
 * after a 24-byte header; the recipe counts in those data bytes, the disc's
 * sectors end to end (tools/xsdk/make_cook_recipe.py has its format). The
 * copy keeps every byte but the fields the recipe reverses, and the CRC-32 of
 * the whole copy must be the one the recipe carries: the PC converter's image
 * of the USA disc. */
enum
{
    DISC_COOK_SECTOR = 2352,
    DISC_COOK_DATA_OFFSET = 24,
    DISC_COOK_DATA_BYTES = 2048,
    DISC_COOK_CHUNK_SECTORS = 448, /* about 1 MB a read and a write */
    DISC_COOK_HEADER_BYTES = 20,
    DISC_COOK_VERSION = 1,
};

struct DiscCookCursor
{
    const unsigned char *at, *end;
    uint32_t dataEnd;
    /* A repeat being expanded: its pattern, and where in it. */
    const unsigned char *repeat, *patternAt;
    uint32_t firstGap, patternRuns, times, time, index;
    /* The run being applied: its next element, the element's bytes, how many are left. */
    uint32_t next, element, left;
    uint32_t runs;
};

static uint32_t DiscCook_Read32(const unsigned char *at)
{
    return (uint32_t)at[0] | (uint32_t)at[1] << 8 | (uint32_t)at[2] << 16 | (uint32_t)at[3] << 24;
}

int NativeDiscCook_OpenRecipe(struct NativeDiscCookRecipe *recipe, const void *bytes, size_t length)
{
    const unsigned char *at = bytes;
    if (length < DISC_COOK_HEADER_BYTES || memcmp(at, "CTRC", 4) != 0 || DiscCook_Read32(at + 4) != DISC_COOK_VERSION)
        return 0;
    recipe->bytes = at;
    recipe->end = at + length;
    recipe->imageBytes = DiscCook_Read32(at + 8);
    recipe->crc = DiscCook_Read32(at + 12);
    recipe->runs = DiscCook_Read32(at + 16);
    return recipe->imageBytes != 0 && recipe->imageBytes % DISC_COOK_SECTOR == 0;
}

static int DiscCook_Number(const unsigned char **at, const unsigned char *end, uint32_t *value)
{
    uint32_t result = 0;
    unsigned shift;
    for (shift = 0; shift <= 28 && *at < end; shift += 7)
    {
        unsigned char byte = *(*at)++;
        result |= (uint32_t)(byte & 0x7f) << shift;
        if ((byte & 0x80) == 0)
        {
            *value = result;
            return 1;
        }
    }
    return 0;
}

/* The next run into the cursor: 1, or 0 at the recipe's end, or -1 when it is damaged. */
static int DiscCook_NextRun(struct DiscCookCursor *c)
{
    uint32_t gap, kind, count, skip, i;
    for (;;)
    {
        if (c->repeat != NULL)
        {
            if (c->index == c->patternRuns)
            {
                c->index = 0;
                c->patternAt = c->repeat;
                if (++c->time == c->times)
                {
                    c->repeat = NULL;
                    continue;
                }
            }
            if (!DiscCook_Number(&c->patternAt, c->end, &gap) || c->patternAt == c->end) return -1;
            kind = *c->patternAt++;
            if (!DiscCook_Number(&c->patternAt, c->end, &count)) return -1;
            if (c->time == 0 && c->index == 0) gap = c->firstGap;
            c->index++;
            break;
        }
        if (c->at == c->end) return 0;
        if (!DiscCook_Number(&c->at, c->end, &gap) || c->at == c->end) return -1;
        kind = *c->at++;
        if (kind != 0)
        {
            if (!DiscCook_Number(&c->at, c->end, &count)) return -1;
            break;
        }
        /* A repeat: its pattern of runs follows, then the next instruction. */
        if (!DiscCook_Number(&c->at, c->end, &c->patternRuns) || !DiscCook_Number(&c->at, c->end, &c->times) ||
            c->patternRuns == 0 || c->times == 0)
            return -1;
        c->repeat = c->patternAt = c->at;
        for (i = 0; i < c->patternRuns; i++)
        {
            if (!DiscCook_Number(&c->at, c->end, &skip) || c->at == c->end) return -1;
            c->at++;
            if (!DiscCook_Number(&c->at, c->end, &skip)) return -1;
        }
        c->firstGap = gap;
        c->time = 0;
        c->index = 0;
    }
    if ((kind != 2 && kind != 4) || count == 0 || gap > UINT32_MAX - c->dataEnd ||
        count > (UINT32_MAX - c->dataEnd - gap) / kind)
        return -1;
    c->next = c->dataEnd + gap;
    c->element = kind;
    c->left = count;
    c->dataEnd = c->next + kind * count;
    c->runs++;
    return 1;
}

static unsigned char *DiscCook_Byte(unsigned char *buffer, uint32_t firstSector, uint32_t data)
{
    return buffer + (data / DISC_COOK_DATA_BYTES - firstSector) * DISC_COOK_SECTOR + DISC_COOK_DATA_OFFSET +
           data % DISC_COOK_DATA_BYTES;
}

/* Reverses each element that ends inside the data of the buffer's sectors, which start at firstSector: 1 when
 * the next element runs past them (it starts in the last sector, which the next call holds again), 0 when the
 * recipe is done, -1 when it is damaged. */
static int DiscCook_Apply(struct DiscCookCursor *c, unsigned char *buffer, uint32_t firstSector, uint32_t sectors)
{
    const uint32_t dataStart = firstSector * DISC_COOK_DATA_BYTES;
    const uint32_t dataEnd = (firstSector + sectors) * DISC_COOK_DATA_BYTES;
    for (;;)
    {
        uint32_t within, fit, n, i;
        unsigned char *p, t;
        if (c->left == 0)
        {
            int next = DiscCook_NextRun(c);
            if (next <= 0) return next;
        }
        if (c->next < dataStart) return -1;
        if (c->next + c->element > dataEnd) return 1;
        within = c->next % DISC_COOK_DATA_BYTES;
        p = DiscCook_Byte(buffer, firstSector, c->next);
        if (within + c->element <= DISC_COOK_DATA_BYTES)
        {
            /* As many of the run's elements as this sector holds. */
            fit = (DISC_COOK_DATA_BYTES - within) / c->element;
            n = c->left < fit ? c->left : fit;
            if (c->element == 2)
            {
                for (i = 0; i < n; i++, p += 2)
                {
                    t = p[0]; p[0] = p[1]; p[1] = t;
                }
            }
            else
            {
                for (i = 0; i < n; i++, p += 4)
                {
                    t = p[0]; p[0] = p[3]; p[3] = t;
                    t = p[1]; p[1] = p[2]; p[2] = t;
                }
            }
            c->next += n * c->element;
            c->left -= n;
        }
        else
        {
            /* Across the sector's end: its other bytes start the next sector's data. */
            unsigned char *at[4];
            for (i = 0; i < c->element; i++) at[i] = DiscCook_Byte(buffer, firstSector, c->next + i);
            for (i = 0; i < c->element / 2; i++)
            {
                t = *at[i]; *at[i] = *at[c->element - 1 - i]; *at[c->element - 1 - i] = t;
            }
            c->next += c->element;
            c->left--;
        }
    }
}

static uint32_t DiscCook_Crc32(uint32_t crc, const unsigned char *bytes, size_t length)
{
    static uint32_t table[256];
    size_t i;
    if (table[1] == 0)
    {
        uint32_t n, k, value;
        for (n = 0; n < 256; n++)
        {
            value = n;
            for (k = 0; k < 8; k++) value = (value & 1) ? 0xedb88320u ^ (value >> 1) : value >> 1;
            table[n] = value;
        }
    }
    crc = ~crc;
    for (i = 0; i < length; i++) crc = table[(crc ^ bytes[i]) & 0xff] ^ (crc >> 8);
    return ~crc;
}

/* Reverses each element of the runs in bytes, whose first byte is offset 0;
 * with bytes NULL only checks they stay inside length. 0 if they don't, or
 * the instructions are damaged, or they aren't runs runs. */
static int DiscCook_PatchRuns(const unsigned char *at, const unsigned char *end, uint32_t runs, unsigned char *bytes,
                              uint32_t length)
{
    struct DiscCookCursor c;
    int got;
    memset(&c, 0, sizeof(c));
    c.at = at;
    c.end = end;
    while ((got = DiscCook_NextRun(&c)) == 1)
    {
        if (c.dataEnd > length) return 0;
        if (bytes == NULL) continue;
        for (; c.left; c.left--, c.next += c.element)
        {
            unsigned char *e = bytes + c.next, t = e[0];
            if (c.element == 2)
            {
                e[0] = e[1];
                e[1] = t;
            }
            else
            {
                e[0] = e[3];
                e[3] = t;
                t = e[1];
                e[1] = e[2];
                e[2] = t;
            }
        }
    }
    return got == 0 && c.runs == runs;
}

int NativeDiscCook_PatchEntry(const void *patches, size_t patchBytes, uint32_t entry, unsigned char *bytes,
                              size_t length)
{
    const unsigned char *at = patches, *end = at + patchBytes;
    uint32_t records, r, i;
    if (patchBytes < 12 || memcmp(at, "CTRP", 4) != 0 || DiscCook_Read32(at + 4) != DISC_COOK_VERSION) return -1;
    records = DiscCook_Read32(at + 8);
    at += 12;
    for (r = 0; r < records; r++)
    {
        uint32_t count, size, before, after, runs, body;
        int mine = 0;
        if (end - at < 4) return -1;
        count = DiscCook_Read32(at);
        at += 4;
        if (count > (size_t)(end - at) / 4) return -1;
        for (i = 0; i < count; i++) mine |= DiscCook_Read32(at + 4 * i) == entry;
        at += 4 * count;
        if (end - at < 20) return -1;
        size = DiscCook_Read32(at);
        before = DiscCook_Read32(at + 4);
        after = DiscCook_Read32(at + 8);
        runs = DiscCook_Read32(at + 12);
        body = DiscCook_Read32(at + 16);
        at += 20;
        if (body > (size_t)(end - at)) return -1;
        if (mine)
        {
            if (length < size || DiscCook_Crc32(0, bytes, size) != before) return 0;
            if (!DiscCook_PatchRuns(at, at + body, runs, NULL, size)) return -1;
            DiscCook_PatchRuns(at, at + body, runs, bytes, size);
            if (DiscCook_Crc32(0, bytes, size) == after) return 1;
            /* Each reversal is its own inverse: put the bytes back. */
            DiscCook_PatchRuns(at, at + body, runs, bytes, size);
            return -1;
        }
        at += body;
    }
    return 0;
}

static int DiscCook_ReadAll(int file, unsigned char *at, size_t length)
{
    while (length > 0)
    {
        ssize_t got = read(file, at, length);
        if (got <= 0) return 0;
        at += got;
        length -= (size_t)got;
    }
    return 1;
}

static int DiscCook_WriteAll(int file, const unsigned char *at, size_t length)
{
    while (length > 0)
    {
        ssize_t put = write(file, at, length);
        if (put <= 0) return 0;
        at += put;
        length -= (size_t)put;
    }
    return 1;
}

int NativeDiscCook_Convert(const struct NativeDiscCookRecipe *recipe, const char *source, const char *destination,
                           NativeDiscCookProgress progress, void *context)
{
    struct DiscCookCursor cursor;
    struct stat info;
    const uint32_t sectors = recipe->imageBytes / DISC_COOK_SECTOR;
    uint32_t done = 0, readSectors = 0, carried = 0, crc = 0;
    unsigned char *buffer;
    int in, out, result = NATIVE_DISC_COOK_OK;

    if (stat(source, &info) != 0) return NATIVE_DISC_COOK_READ_FAILED;
    if ((uint64_t)info.st_size != recipe->imageBytes) return NATIVE_DISC_COOK_WRONG_SIZE;
    in = open(source, O_RDONLY | O_BINARY);
    if (in < 0) return NATIVE_DISC_COOK_READ_FAILED;
    out = open(destination, O_WRONLY | O_CREAT | O_TRUNC | O_BINARY, 0644);
    if (out < 0)
    {
        close(in);
        return NATIVE_DISC_COOK_WRITE_FAILED;
    }
    buffer = malloc((size_t)(DISC_COOK_CHUNK_SECTORS + 1) * DISC_COOK_SECTOR);
    memset(&cursor, 0, sizeof(cursor));
    cursor.at = recipe->bytes + DISC_COOK_HEADER_BYTES;
    cursor.end = recipe->end;
    if (buffer == NULL) result = NATIVE_DISC_COOK_READ_FAILED;
    while (result == NATIVE_DISC_COOK_OK && done < sectors)
    {
        uint32_t want = sectors - readSectors < DISC_COOK_CHUNK_SECTORS ? sectors - readSectors : DISC_COOK_CHUNK_SECTORS;
        uint32_t held, writeSectors;
        int state, last;
        if (!DiscCook_ReadAll(in, buffer + (size_t)carried * DISC_COOK_SECTOR, (size_t)want * DISC_COOK_SECTOR))
        {
            result = NATIVE_DISC_COOK_READ_FAILED;
            break;
        }
        readSectors += want;
        held = carried + want;
        last = readSectors == sectors;
        state = DiscCook_Apply(&cursor, buffer, readSectors - held, held);
        if (state < 0 || (last && state != 0))
        {
            result = NATIVE_DISC_COOK_BAD_RECIPE;
            break;
        }
        /* Hold the last sector back: an element may run on into the next. */
        writeSectors = last ? held : held - 1;
        crc = DiscCook_Crc32(crc, buffer, (size_t)writeSectors * DISC_COOK_SECTOR);
        if (!DiscCook_WriteAll(out, buffer, (size_t)writeSectors * DISC_COOK_SECTOR))
        {
            result = NATIVE_DISC_COOK_WRITE_FAILED;
            break;
        }
        done += writeSectors;
        if (!last)
        {
            memmove(buffer, buffer + (size_t)writeSectors * DISC_COOK_SECTOR, DISC_COOK_SECTOR);
            carried = 1;
        }
        if (progress != NULL) progress(context, done, sectors);
    }
    free(buffer);
    close(in);
    if (result == NATIVE_DISC_COOK_OK && fsync(out) != 0) result = NATIVE_DISC_COOK_WRITE_FAILED;
    if (close(out) != 0 && result == NATIVE_DISC_COOK_OK) result = NATIVE_DISC_COOK_WRITE_FAILED;
    if (result == NATIVE_DISC_COOK_OK && cursor.runs != recipe->runs) result = NATIVE_DISC_COOK_BAD_RECIPE;
    if (result == NATIVE_DISC_COOK_OK && crc != recipe->crc) result = NATIVE_DISC_COOK_MISMATCH;
    if (result != NATIVE_DISC_COOK_OK) unlink(destination);
    return result;
}

int NativeDiscCook_FindImage(const char *folder, uint64_t imageBytes, char *out, size_t outBytes, uint64_t *bytes)
{
    DIR *dir;
    struct dirent *entry;
    struct stat info;
    char path[512];
    int found = 0;
    dir = opendir(folder);
    if (dir == NULL) return 0;
    while ((entry = readdir(dir)) != NULL)
    {
        size_t length = strlen(entry->d_name);
        if (length < 5 || strcasecmp(entry->d_name + length - 4, ".bin") != 0) continue;
        if ((size_t)snprintf(path, sizeof(path), "%s%s", folder, entry->d_name) >= sizeof(path)) continue;
        if (stat(path, &info) != 0 || !S_ISREG(info.st_mode)) continue;
        /* The USA image's size wins; otherwise the first .bin, so the player hears why it can't be used. */
        if (found && (uint64_t)info.st_size != imageBytes) continue;
        if (strlen(path) >= outBytes) continue;
        strcpy(out, path);
        *bytes = (uint64_t)info.st_size;
        found = 1;
        if (*bytes == imageBytes) break;
    }
    closedir(dir);
    return found;
}
