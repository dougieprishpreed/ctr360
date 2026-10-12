/* ctr360 XDK smoke translation unit.
 *
 * Compiles the WHOLE mirrored game corpus as a single translation unit with
 * the Xbox 360 SDK's cl.exe (C89 mode) as a language-level probe of the
 * build-360/gen mirror. Platform backend files are intentionally absent -
 * this checks game code only, mirroring main.c's include order.
 *
 * Compile (from build-360/gen):
 *   cl.exe -nologo -c -TC -DCTR_NATIVE -I. -Iinclude \
 *          ..\..\tools\ctr360\xdk_smoke_360.c
 */
#include <common.h>

#include "game/game_unity.h"

#include "game/zGlobal_RDATA.c"
#include "game/zGlobal_DATA.c"
#include "game/zGlobal_SDATA.c"

#undef RECT
