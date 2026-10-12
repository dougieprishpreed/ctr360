r"""Exercise the actual path/disc/asset code with strict Xbox device paths.

The host fixture rejects forward slashes and bare device roots before mapping
game:\ to the staged XEX directory. Xenia's permissive path handling cannot
mask these failures. No player saves or staged files are changed.
"""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/xbox-asset-path-contract'
out.mkdir(parents=True, exist_ok=True)
stubs = out / 'include'
(stubs / 'platform').mkdir(parents=True, exist_ok=True)
(stubs / 'macros.h').write_text('''
#pragma once
#include <stdint.h>
#include <stddef.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef uint64_t u64; typedef int32_t s32;
#define internal static
#define global_variable static
#define local_persist static
#define CTR_PRINTF_FORMAT(a,b)
''', encoding='utf-8')
(stubs / 'platform/native_win32.h').write_text('''
#pragma once
typedef unsigned long DWORD;
typedef void *HANDLE;
typedef struct {char cFileName[260]; DWORD dwFileAttributes;} WIN32_FIND_DATAA;
#define INVALID_FILE_ATTRIBUTES ((DWORD)-1)
#define INVALID_HANDLE_VALUE ((HANDLE)-1)
#define FILE_ATTRIBUTE_DIRECTORY 16
static DWORD GetFileAttributesA(const char *);
static HANDLE FindFirstFileA(const char *, WIN32_FIND_DATAA *);
static int FindNextFileA(HANDLE, WIN32_FIND_DATAA *);
static int FindClose(HANDLE);
static unsigned long GetLastError(void);
''', encoding='utf-8')

paths = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <platform/native_path.h>
static void expect(const char *got, const char *want) {
 if(strcmp(got,want)!=0){fprintf(stderr,"got '%s', want '%s'\n",got,want);assert(0);}
}
int main(void) {
 char b[256], small[3];
 NativeStr8 s;
 s=NativePath_TrimTrailingSeparators(NativeStr8_FromCString("game:\\\\"));
 assert(s.len==6 && s.ptr[5]=='\\');
 s=NativePath_TrimTrailingSeparators(NativeStr8_FromCString("usb0:\\"));
 assert(s.len==6);
 s=NativePath_TrimTrailingSeparators(NativeStr8_FromCString("C:\\"));
 assert(s.len==3);
 assert(NativePath_Parent(b,sizeof b,NativeStr8_FromCString("game:\\assets")));
#ifdef _XBOX
 expect(b,"game:\\");
 assert(NativePath_Join(b,sizeof b,NativeStr8_FromCString("game:\\"),
                       NativeStr8_FromCString("/assets\\XA/ENG.XNF")));
 expect(b,"game:\\assets\\XA\\ENG.XNF");
 assert(NativePath_Parent(b,sizeof b,NativeStr8_FromCString("game:\\assets\\XA")));
 expect(b,"game:\\assets");
 assert(NativePath_NormalizeSlashes(b,sizeof b,NativeStr8_FromCString("hdd1:/CTR/assets")));
 expect(b,"hdd1:\\CTR\\assets");
#else
 expect(b,"game:/");
 assert(NativePath_Join(b,sizeof b,NativeStr8_FromCString("C:\\CTR\\"),
                       NativeStr8_FromCString("/assets\\XA/ENG.XNF")));
 expect(b,"C:/CTR/assets/XA/ENG.XNF");
 assert(NativePath_Parent(b,sizeof b,NativeStr8_FromCString("/tmp/assets")));
 expect(b,"/tmp");
 assert(NativePath_Parent(b,sizeof b,NativeStr8_FromCString("/tmp")));
 expect(b,"/");
#endif
 assert(!NativePath_Join(small,sizeof small,NativeStr8_FromCString("game:\\"),
                        NativeStr8_FromCString("assets")));
 puts("PASS actual path helpers: device roots, parents, mixed slashes, bounds");
 return 0;
}
'''
(out / 'paths.c').write_text(paths, encoding='utf-8')
for name, flags in [('host', []), ('xbox', ['-D_XBOX'])]:
    exe = out / (name + '.exe')
    subprocess.run(['clang', '-std=c99', *flags, '-I', str(stubs), '-I',
                    str(root / 'include'), str(out / 'paths.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

assets = r'''
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <platform/native_win32.h>
static const char *base;
static int badPaths, errors;
static char lastError[4096];
static int map(const char *path,char *host) {
 if(strchr(path,'/') || strncmp(path,"game:\\",6)!=0) {
  badPaths++; fprintf(stderr,"REJECT device path '%s'\n",path); errno=EINVAL;return 0;
 }
 snprintf(host,2048,"%s/%s",base,path+6);
 for(char *p=host;*p;p++)if(*p=='\\')*p='/';
 return 1;
}
static FILE *device_fopen(const char *path,const char *mode) {
 char host[2048]; return map(path,host)?fopen(host,mode):NULL;
}
static DWORD GetFileAttributesA(const char *path) {
 char host[2048];struct stat st;
 if(!map(path,host) || stat(host,&st)!=0)return INVALID_FILE_ATTRIBUTES;
 return (st.st_mode&S_IFDIR)?FILE_ATTRIBUTE_DIRECTORY:0;
}
/* The staged package uses exact names on a case-insensitive Xbox volume.
 * No extracted-file override is present, so absent host files fall back to ISO. */
static HANDLE FindFirstFileA(const char *path,WIN32_FIND_DATAA *d) {
 char host[2048];(void)d;map(path,host);return INVALID_HANDLE_VALUE;
}
static int FindNextFileA(HANDLE h,WIN32_FIND_DATAA *d){(void)h;(void)d;return 0;}
static int FindClose(HANDLE h){(void)h;return 1;}
static unsigned long GetLastError(void){return 2;}
void Platform_Log(const char *fmt,...) {(void)fmt;}
void Platform_LogError(const char *fmt,...) {
 va_list args;va_start(args,fmt);vsnprintf(lastError,sizeof lastError,fmt,args);va_end(args);errors++;
}
#define fopen device_fopen
#define fprintf forbidden_direct_stderr
#include "platform/native_disc_image.c"
#include "platform/native_assets.c"
#undef fprintf
int main(int argc,char **argv) {
 char p[1024]; (void)argc;base=argv[1];
 assert(NativeAssets_Init("game:\\"));
 assert(strcmp(NativeAssets_GetBaseDir(),"game:\\")==0);
 assert(strcmp(NativeAssets_GetAssetDir(),"game:\\assets")==0);
 assert(s_nativeDiscImageAvailable && NativeAssets_Validate());
 assert(errors==0 && badPaths==0);
 assert(NativeAssets_BuildPath("SOUNDS/KART.HWL",p,sizeof p));
 assert(strcmp(p,"game:\\assets\\SOUNDS\\KART.HWL")==0);
 /* Force an absent image: diagnostics must reach Platform_LogError and
  * validation must fail instead of writing the XDK's unsupported stderr. */
 fclose(s_nativeDiscImageFile);s_nativeDiscImageFile=NULL;
 base=argv[2];errors=0;
 assert(NativeAssets_Init("game:\\"));
 assert(!s_nativeDiscImageAvailable && !NativeAssets_Validate());
 assert(errors>=4 && strstr(lastError,"For complete audio/video"));
 assert(badPaths==0);
 puts("PASS actual Xbox asset/disc code: staged cooked ISO validates; no bare roots/forward slashes; missing image reports through logger");
 return 0;
}
'''
(out / 'assets.c').write_text(assets, encoding='utf-8')
exe = out / 'assets.exe'
subprocess.run(['clang', '-std=c99', '-D_XBOX', '-D_WIN32', '-D_CRT_SECURE_NO_WARNINGS', '-Werror=implicit-function-declaration',
                '-I', str(stubs), '-I', str(root / 'include'), '-I', str(root),
                str(out / 'assets.c'), '-o', str(exe)], check=True)
subprocess.run([str(exe), str(root / 'build-360/xex/dist'), str(out / 'absent')],
               check=True)
