"""Execute the shipped parser, graphics callback and XInput mapping functions."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/native-config'
out.mkdir(parents=True, exist_ok=True)


def function(path, name):
    source = (root / path).read_text()
    match = re.search(r'^.*\b' + name + r'\([^;]*?\)\s*\n\{', source, re.M)
    assert match, name
    start = source.index('{', match.start())
    end, depth = start + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end] + '\n'


input_path = 'platform/xbox360/native_xbox360_input.c'
source = (root / input_path).read_text()
c = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define internal static
#define X360_MAP_AXIS 0x100
#define X360_MAP_INVERSE 0x200
#define NATIVE_INPUT_AXIS_DEADZONE 500
typedef int32_t s32;typedef uint16_t WORD;
typedef struct {WORD wButtons;unsigned char bLeftTrigger,bRightTrigger;
 int16_t sThumbLX,sThumbLY,sThumbRX,sThumbRY;} XINPUT_GAMEPAD;
static int g_nativeHDEnableInterpolation=1,g_cfg_bilinearFiltering=1,s_hdEdgeAA=1;
'''
c += '\n'.join(re.findall(r'enum\s*\{.*?\};', source, re.S))
buttons = ['DPAD_UP', 'DPAD_DOWN', 'DPAD_LEFT', 'DPAD_RIGHT', 'START', 'BACK',
           'LEFT_THUMB', 'RIGHT_THUMB', 'LEFT_SHOULDER', 'RIGHT_SHOULDER', 'A', 'B', 'X', 'Y']
# These are the actual XInput masks, rather than the backend's button indices.
masks = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 4096, 8192, 16384, 32768]
for name, mask in zip(buttons, masks):
    c += f'\n#define XINPUT_GAMEPAD_{name} {mask}\n'
c += re.search(r'internal const WORD s_buttonMasks.*?\};', source, re.S).group() + '\n'
c += re.search(r'struct NativeInputControllerMapping\s*\{.*?\};', source, re.S).group() + '\n'
c += 'static struct NativeInputControllerMapping s_controllerMapping;\n'
c += '#define NativeConfig_Read NativeConfig_ReadFile\n'
c += (root / 'platform/native_config.c').read_text() + '\n'
c += r'''
#undef NativeConfig_Read
static const char *configPath;
static int NativeConfig_Read(const char *path,NativeConfigSetting callback,void *context){
 assert(!strcmp(path,"game:\\ctr360.ini"));return NativeConfig_ReadFile(configPath,callback,context);
}
'''
for name in ('NativeInput_ConfigSetting', 'NativeInput_DefaultMappings',
             'NativeInput_ReadAxis', 'NativeInput_ControllerButtonState'):
    c += function(input_path, name)
c += function('platform/xbox360/native_xbox360_video.c', 'NativeRenderer_ConfigSetting')
c += r'''
int main(int argc,char **argv){
 XINPUT_GAMEPAD pad={0};assert(argc==3);configPath=argv[1];
 NativeInput_DefaultMappings();
 assert(s_controllerMapping.gc_cross==X360_BTN_A&&s_controllerMapping.gc_l2==(X360_MAP_AXIS|X360_AXIS_LEFT_TRIGGER));
 assert(s_controllerMapping.gc_axis_left_y==(X360_MAP_AXIS|X360_AXIS_LEFT_Y|X360_MAP_INVERSE));
 configPath=argv[2];NativeInput_DefaultMappings();
 NativeConfig_Read(configPath?"game:\\ctr360.ini":"",NativeRenderer_ConfigSetting,NULL);
 assert(!g_nativeHDEnableInterpolation&&g_cfg_bilinearFiltering&&!s_hdEdgeAA);
 assert(s_controllerMapping.gc_cross==(X360_MAP_AXIS|X360_AXIS_RIGHT_TRIGGER));
 assert(s_controllerMapping.gc_r2==X360_BTN_A&&s_controllerMapping.gc_square==-1);
 assert(s_controllerMapping.gc_circle==X360_BTN_B&&s_controllerMapping.gc_start==X360_BTN_START);
 assert(s_controllerMapping.gc_triangle==X360_BTN_Y);
 pad.bRightTrigger=255;assert(NativeInput_ControllerButtonState(&pad,s_controllerMapping.gc_cross)==32767);
 assert(!NativeInput_ControllerButtonState(&pad,s_controllerMapping.gc_r2));
 pad.wButtons=XINPUT_GAMEPAD_A;assert(NativeInput_ControllerButtonState(&pad,s_controllerMapping.gc_r2)>16384);
 assert(!NativeInput_ControllerButtonState(&pad,s_controllerMapping.gc_square));
 pad.sThumbRY=20000;assert(NativeInput_ControllerButtonState(&pad,s_controllerMapping.gc_axis_left_x)==-20000);
 pad.sThumbLY=16000;assert(NativeInput_ControllerButtonState(&pad,s_controllerMapping.gc_axis_left_y)==-16000);
 puts("PASS actual INI parser, defaults, remapping, XInput masks/triggers/axes, invalid keys/values, BOM/CRLF, long-line isolation and graphics precedence");
 return 0;
}
'''
(out / 'fixture.c').write_text(c)
fixture = ('\ufeff; comment\r\n[graphics]\r\ninterpolation = 0 ; comment\r\n'
           'texture_filter=2\r\nedge_aa=0\r\n[controls]\r\ncross=RT\r\nr2=A\r\n'
           'square=NONE\r\nleft_x=-RIGHT_Y\r\ncircle=BAD\r\ntriangle=-A\r\n'
           + 'x' * 280 + 'start=NONE\r\n'
           + '[' + 'x' * 280 + '\r\ntriangle=NONE\r\n'
           + '[graphics]junk\r\ntexture_filter=0\r\n[other]\r\nedge_aa=1\r\n')
(out / 'settings.ini').write_bytes(fixture.encode('utf-8'))
subprocess.run(['clang', '-std=c89', '-pedantic-errors', '-Wno-long-long', '-I', str(root / 'include'),
                str(out / 'fixture.c'), '-o', str(out / 'fixture.exe')], check=True)
run = subprocess.run([str(out / 'fixture.exe'), str(out / 'missing.ini'), str(out / 'settings.ini')],
                     text=True, capture_output=True, check=True)
(out / 'fixture.log').write_text(run.stdout)
print(run.stdout, end='')
