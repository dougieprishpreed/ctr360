#ifndef CTR_NATIVE_CONFIG_H
#define CTR_NATIVE_CONFIG_H

/* Read only at startup. Callbacks accept keys they recognise; unknown or
 * malformed settings leave the caller's defaults intact. */
typedef void (*NativeConfigSetting)(const char *section, const char *key,
                                    const char *value, void *context);
int NativeConfig_Read(const char *path, NativeConfigSetting setting, void *context);

#endif
