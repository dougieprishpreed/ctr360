/* Renderer-owned device state. Every setter, including VRAM bridge/present
 * passes, must go through the cache. Reset when the device is created/replaced.
 * No D3D headers here so overlap and invalidation can be checked on a host. */
#ifndef CTR360_STATE_CACHE_H
#define CTR360_STATE_CACHE_H
#include <string.h>
#define CTR360_CONSTANT_REGISTERS 256
#define CTR360_RENDER_STATES 512
typedef struct Ctr360ConstantCache
{
    float values[CTR360_CONSTANT_REGISTERS][4];
    unsigned char valid[CTR360_CONSTANT_REGISTERS];
} Ctr360ConstantCache;
typedef struct Ctr360RenderStateCache
{
    unsigned int values[CTR360_RENDER_STATES];
    unsigned char valid[CTR360_RENDER_STATES];
} Ctr360RenderStateCache;
static int Ctr360ConstantsEqual(const Ctr360ConstantCache *cache,
    unsigned int first, const float *values, unsigned int count)
{
    unsigned int i;
    if (first >= CTR360_CONSTANT_REGISTERS || count > CTR360_CONSTANT_REGISTERS - first)
        return 0;
    for (i = 0; i < count; ++i)
        if (!cache->valid[first + i]) return 0;
    return memcmp(cache->values[first], values, count * 4 * sizeof(float)) == 0;
}
static void Ctr360ConstantsRemember(Ctr360ConstantCache *cache,
    unsigned int first, const float *values, unsigned int count)
{
    if (first >= CTR360_CONSTANT_REGISTERS || count > CTR360_CONSTANT_REGISTERS - first)
        return;
    memcpy(cache->values[first], values, count * 4 * sizeof(float));
    memset(cache->valid + first, 1, count);
}
#endif
