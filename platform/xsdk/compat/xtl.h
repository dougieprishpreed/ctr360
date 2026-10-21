/* Small source-level bridge for the existing controller/clock code.
 * Implemented using public xSDK APIs; no Microsoft headers or libraries. */
#ifndef CTR_XSDK_COMPAT_H
#define CTR_XSDK_COMPAT_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdio.h>
#include <errno.h>
#define _snprintf snprintf
static inline unsigned int GetLastError(void) { return (unsigned int)errno; }
#include <xsdk/kernel.h>
#include <xsdk/thread.h>
typedef uint32_t DWORD;
typedef uint16_t WORD;
typedef struct { int64_t QuadPart; } LARGE_INTEGER;
typedef struct { WORD wButtons; uint8_t bLeftTrigger,bRightTrigger; int16_t sThumbLX,sThumbLY,sThumbRX,sThumbRY; } XINPUT_GAMEPAD;
typedef struct { DWORD dwPacketNumber; XINPUT_GAMEPAD Gamepad; } XINPUT_STATE;
typedef struct { WORD wLeftMotorSpeed,wRightMotorSpeed; } XINPUT_VIBRATION;
#define XINPUT_GAMEPAD_DPAD_UP 0x0001
#define XINPUT_GAMEPAD_DPAD_DOWN 0x0002
#define XINPUT_GAMEPAD_DPAD_LEFT 0x0004
#define XINPUT_GAMEPAD_DPAD_RIGHT 0x0008
#define XINPUT_GAMEPAD_START 0x0010
#define XINPUT_GAMEPAD_BACK 0x0020
#define XINPUT_GAMEPAD_LEFT_THUMB 0x0040
#define XINPUT_GAMEPAD_RIGHT_THUMB 0x0080
#define XINPUT_GAMEPAD_LEFT_SHOULDER 0x0100
#define XINPUT_GAMEPAD_RIGHT_SHOULDER 0x0200
#define XINPUT_GAMEPAD_A 0x1000
#define XINPUT_GAMEPAD_B 0x2000
#define XINPUT_GAMEPAD_X 0x4000
#define XINPUT_GAMEPAD_Y 0x8000
static inline DWORD XInputGetState(DWORD user, XINPUT_STATE *out)
{
    INPUT_STATE state = {0};
    DWORD result = XamInputGetState(user, 0, &state);
    /* Named copies avoid depending on either SDK's struct padding. */
    out->dwPacketNumber=state.packet_number;
    out->Gamepad.wButtons=state.gamepad.buttons;
    out->Gamepad.bLeftTrigger=state.gamepad.left_trigger;
    out->Gamepad.bRightTrigger=state.gamepad.right_trigger;
    out->Gamepad.sThumbLX=state.gamepad.thumb_lx;
    out->Gamepad.sThumbLY=state.gamepad.thumb_ly;
    out->Gamepad.sThumbRX=state.gamepad.thumb_rx;
    out->Gamepad.sThumbRY=state.gamepad.thumb_ry;
    return result;
}
static inline DWORD XInputSetState(DWORD user, const XINPUT_VIBRATION *in)
{
    INPUT_VIBRATION vibration = {in->wLeftMotorSpeed,in->wRightMotorSpeed};
    return XamInputSetState(user,0,&vibration);
}
static inline void QueryPerformanceCounter(LARGE_INTEGER *out)
{
    struct timespec now; clock_gettime(CLOCK_MONOTONIC,&now);
    out->QuadPart=(int64_t)now.tv_sec*1000000000+now.tv_nsec;
}
static inline void QueryPerformanceFrequency(LARGE_INTEGER *out) { out->QuadPart=1000000000; }
static inline DWORD GetTickCount(void) { LARGE_INTEGER now; QueryPerformanceCounter(&now); return (DWORD)(now.QuadPart/1000000); }
static inline void Sleep(DWORD ms) { xsdk_thread_sleep(ms); }
static inline void XLaunchNewImage(const char *image, void *data) { (void)image; (void)data; exit(0); }
#endif
