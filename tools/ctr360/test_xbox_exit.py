"""Actual Xbox exit, quit chord, startup failures and loader fatal routing.

Launch/input/device APIs are host stubs. Assert that title exits launch the
dashboard after cleanup, including a failed launch that must never reach CRT.
"""
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[2]
out=root/'build-360/results/xbox-exit-contract'
out.mkdir(parents=True,exist_ok=True)


def function(path,name):
    text=(root/path).read_text()
    m=re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{',text,re.M)
    assert m,name
    opening=text.index('{',m.start());end=opening+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[m.start():end]+'\n'


c=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
#include <setjmp.h>
#include <platform.h>
typedef unsigned long DWORD;typedef unsigned short WORD;
typedef struct {struct {WORD wButtons;} Gamepad;} XINPUT_STATE;
enum {ERROR_SUCCESS=0,XINPUT_GAMEPAD_BACK=0x20,XINPUT_GAMEPAD_START=0x10,NATIVE_MEMCARD_OK=0};
#define CTR_NATIVE_VERSION "fixture"
#define CTR_NATIVE_BUILD_ID "fixture"
static int s_platformInitialized,launches,flushes,closed,shutdowns,polls,sleeps,fixups;
static int exitStatus,failStage,failLaunch,ctrResult,buttons;
static jmp_buf leave;
static void Platform_Log(const char*fmt,...){
 if(strstr(fmt,"status=%d")){va_list a;va_start(a,fmt);exitStatus=va_arg(a,int);va_end(a);}
}
static void Platform_LogError(const char*fmt,...){(void)fmt;}
static void Platform_LogInit(const char*title){(void)title;closed=0;}
static void Platform_LogFlush(void){flushes++;}
static void Platform_LogShutdown(void){closed=1;}
static void Platform_InputShutdown(void){shutdowns++;}
static void NativeAudio_Shutdown(void){shutdowns++;}
static void NativeRenderer_Shutdown(void){shutdowns++;}
static DWORD XInputGetState(int pad,XINPUT_STATE*s){assert(pad==0);polls++;s->Gamepad.wButtons=(WORD)buttons;return ERROR_SUCCESS;}
static void XLaunchNewImage(const char*path,void*data){
 assert(!path&&!data&&closed&&!s_platformInitialized&&flushes);
 launches++;if(!failLaunch)longjmp(leave,1);
}
static void Sleep(unsigned ms){assert(ms==1000&&launches==1);if(++sleeps==2)longjmp(leave,2);}
static void Platform_InstallFaultHandler(void){}
static void Ctr360_ApplyStaticFixups(void){assert(!fixups);fixups++;}
static int NativeAssets_Init(const char*path){assert(fixups==1&&!strcmp(path,"game:\\"));return failStage!=1;}
static const char*NativeAssets_GetBaseDir(void){return "game:\\";}
static const char*NativeAssets_GetAssetDir(void){return "game:\\assets";}
static int NativeAssets_Validate(void){return failStage!=2;}
static int NativeMemcard_SetRoot(const char*path){assert(!strcmp(path,"game:\\memcards"));return failStage==3?-1:NATIVE_MEMCARD_OK;}
void Platform_Init(const char*t,int w,int h){(void)t;assert(w==1280&&h==720);s_platformInitialized=failStage!=4;}
void Platform_InitScratchpad(void){}
static void Platform_RepairResidentPointers(int pack){assert(pack==0);}
static int CTR_Main(void){return ctrResult;}
'''
for name in ('Platform_Exit','Platform_Shutdown','Platform_PollHostEvents'):
    c+=function('platform/xbox360/native_xbox360_platform.c',name)
c+=function('game/LOAD/LOAD_File.c','LOAD_NativeReadFailure')
c+=function('platform/xbox360/main_xbox360.c','main').replace('int main(void)','static int xboxMain(void)')
c+=r'''
static void reset(void){
 s_platformInitialized=launches=flushes=closed=shutdowns=polls=sleeps=fixups=0;
 exitStatus=-100;failStage=failLaunch=ctrResult=buttons=0;
}
int main(void){
 for(int stage=0;stage<=4;stage++){
  reset();failStage=stage;
  if(!setjmp(leave)){xboxMain();assert(0);}
  assert(launches==1&&exitStatus==(stage?1:0));
  assert(shutdowns==(stage?0:3));
 }
 reset();ctrResult=7;if(!setjmp(leave)){xboxMain();assert(0);}assert(exitStatus==7&&shutdowns==3);
 reset();s_platformInitialized=1;
 if(!setjmp(leave)){LOAD_NativeReadFailure(438,"fixture allocator error");assert(0);}
 assert(launches==1&&exitStatus==EXIT_FAILURE&&shutdowns==3);
 reset();s_platformInitialized=1;buttons=XINPUT_GAMEPAD_START;
 Platform_PollHostEvents();assert(!launches&&polls==1);
 buttons|=XINPUT_GAMEPAD_BACK;if(!setjmp(leave)){Platform_PollHostEvents();assert(0);}
 assert(launches==1&&exitStatus==0&&shutdowns==3);
 reset();s_platformInitialized=1;failLaunch=1;
 int reason=setjmp(leave);if(!reason){Platform_Exit(1);assert(0);}
 assert(reason==2&&launches==1&&sleeps==2&&exitStatus==1&&shutdowns==3);
 puts("PASS actual Xbox exits: four startup failures, normal/nonzero game return, loader fatal, quit chord, cleanup/flush before dashboard launch, launch failure waits without CRT exit");
}
'''
(out/'fixture.c').write_text(c,encoding='utf-8')
subprocess.run(['clang','-O2','-I'+str(root/'include'),str(out/'fixture.c'),'-o',str(out/'fixture.exe')],check=True)
subprocess.run([str(out/'fixture.exe')],check=True)
