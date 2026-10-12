#ifndef CTR360_STDBOOL_H
#define CTR360_STDBOOL_H

/* ctr360: the Xbox 360 XDK ships no stdbool.h and its C89 compiler has no
 * _Bool, but the project's headers (macros.h under CTR_NATIVE) include
 * <stdbool.h>. Provide the C89 equivalent so the mirrored sources stay
 * byte-identical to upstream. */

#ifndef __cplusplus
#define bool int
#define true 1
#define false 0
#endif

#define __bool_true_false_are_defined 1

#endif
