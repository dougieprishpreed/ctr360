#include <stdio.h>
#include <string.h>
#include "platform/native_config.h"

static char *NativeConfig_Trim(char *text)
{
    char *end;
    while (*text == ' ' || *text == '\t' || *text == '\r' || *text == '\n') text++;
    end = text + strlen(text);
    while (end > text && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\r' || end[-1] == '\n')) --end;
    *end = 0;
    return text;
}

int NativeConfig_Read(const char *path, NativeConfigSetting setting, void *context)
{
    FILE *file;
    char line[256], section[32];
    int firstLine = 1;
    file = fopen(path, "r");
    if (file == NULL) return 0;
    section[0] = 0;
    while (fgets(line, sizeof(line), file) != NULL)
    {
        char *text, *end, *equals, *comment;
        int ch;
        /* Ignore the whole oversized line, including anything resembling a
         * setting in its tail. Clear the section on malformed headers. */
        if (strchr(line, '\n') == NULL && !feof(file))
        {
            if (*NativeConfig_Trim(line) == '[') section[0] = 0;
            do { ch = fgetc(file); } while (ch != '\n' && ch != EOF);
            firstLine = 0;
            continue;
        }
        text = line;
        if (firstLine && strlen(text) >= 3 && (unsigned char)text[0] == 0xef &&
            (unsigned char)text[1] == 0xbb && (unsigned char)text[2] == 0xbf) text += 3;
        firstLine = 0;
        comment = strpbrk(text, "#;");
        if (comment != NULL) *comment = 0;
        text = NativeConfig_Trim(text);
        if (*text == '[')
        {
            section[0] = 0;
            end = strchr(text + 1, ']');
            if (end == NULL || *NativeConfig_Trim(end + 1) != 0) continue;
            *end = 0;
            text = NativeConfig_Trim(text + 1);
            if (strlen(text) >= sizeof(section)) continue;
            strcpy(section, text);
            continue;
        }
        if (section[0] == 0) continue;
        equals = strchr(text, '=');
        if (equals == NULL) continue;
        *equals = 0;
        text = NativeConfig_Trim(text);
        end = NativeConfig_Trim(equals + 1);
        if (*text != 0 && *end != 0) setting(section, text, end, context);
    }
    fclose(file);
    return 1;
}

/* Make the settings file from the example beside it when it is missing, so
 * the player has one to edit. Store updates replace only the files they
 * install, so a file the game made stays. Returns 1 when it made one. */
int NativeConfig_CreateDefault(const char *path, const char *examplePath)
{
    FILE *file, *example;
    char buffer[4096];
    size_t bytes;
    int ok = 1;
    file = fopen(path, "rb");
    if (file != NULL)
    {
        fclose(file);
        return 0;
    }
    example = fopen(examplePath, "rb");
    if (example == NULL) return 0;
    file = fopen(path, "wb");
    if (file == NULL)
    {
        fclose(example);
        return 0;
    }
    while ((bytes = fread(buffer, 1, sizeof(buffer), example)) > 0)
    {
        if (fwrite(buffer, 1, bytes, file) != bytes)
        {
            ok = 0;
            break;
        }
    }
    if (ferror(example)) ok = 0;
    fclose(example);
    if (fclose(file) != 0) ok = 0;
    if (!ok) remove(path);
    return ok;
}
