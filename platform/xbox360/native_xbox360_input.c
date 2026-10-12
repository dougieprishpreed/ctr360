/* ctr360: Xbox 360 input backend.
 *
 * Ports platform/native_input.c (the SDL host backend) onto XInput. The PSX
 * pad contract is preserved exactly: the same pad packet builder, the same
 * multitap bus behaviour, the same snapshot/save-state surface, and the same
 * Select+Start analog-mode toggle. Only the device layer differs: pads are
 * the four XInput user slots, and the mapping table is expressed in XInput
 * terms (including the Y axes, which invert because XInput's +Y is up while
 * the PSX axes count down from 0).
 *
 * C89-clean on purpose: the XDK compiler builds this directly.
 */

#include <xtl.h>

#include <macros.h>
#include <common.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "platform/native_input.h"
#include "platform/native_log.h"
#include "psx/libpad.h"

#define NATIVE_INPUT_MAX_CONTROLLERS       PLATFORM_INPUT_PAD_COUNT
#define NATIVE_INPUT_PHYSICAL_SLOT_COUNT   2
#define NATIVE_INPUT_PAD_PACKET_BYTES      8
#define NATIVE_INPUT_MULTITAP_HEADER       2
#define NATIVE_INPUT_PAD_DIGITAL           0x41
#define NATIVE_INPUT_PAD_ANALOG            0x73
#define NATIVE_INPUT_PAD_MULTITAP          0x80
#define NATIVE_INPUT_PAD_DISCONNECT        0xff
#define NATIVE_INPUT_AXIS_DEADZONE         500
#define NATIVE_INPUT_DEFAULT_KEYBOARD_SLOT 0
#define NATIVE_INPUT_STATE_MAGIC           0x49525443
#define NATIVE_INPUT_STATE_VERSION         1

/* Mapping encoding: buttons are indices into s_buttonMasks, axes carry
 * X360_MAP_AXIS plus an axis index. XInput's own masks cannot be used
 * directly because 0x4000 (X button) collides with the axis flag. */
#define X360_MAP_AXIS    0x100
#define X360_MAP_INVERSE 0x200

enum
{
	X360_BTN_DPAD_UP = 0,
	X360_BTN_DPAD_DOWN,
	X360_BTN_DPAD_LEFT,
	X360_BTN_DPAD_RIGHT,
	X360_BTN_START,
	X360_BTN_BACK,
	X360_BTN_LEFT_THUMB,
	X360_BTN_RIGHT_THUMB,
	X360_BTN_LEFT_SHOULDER,
	X360_BTN_RIGHT_SHOULDER,
	X360_BTN_A,
	X360_BTN_B,
	X360_BTN_X,
	X360_BTN_Y,
	X360_BTN_COUNT
};

enum
{
	X360_AXIS_LEFT_X = 0,
	X360_AXIS_LEFT_Y,
	X360_AXIS_RIGHT_X,
	X360_AXIS_RIGHT_Y,
	X360_AXIS_LEFT_TRIGGER,
	X360_AXIS_RIGHT_TRIGGER
};

internal const WORD s_buttonMasks[X360_BTN_COUNT] = {
	XINPUT_GAMEPAD_DPAD_UP,
	XINPUT_GAMEPAD_DPAD_DOWN,
	XINPUT_GAMEPAD_DPAD_LEFT,
	XINPUT_GAMEPAD_DPAD_RIGHT,
	XINPUT_GAMEPAD_START,
	XINPUT_GAMEPAD_BACK,
	XINPUT_GAMEPAD_LEFT_THUMB,
	XINPUT_GAMEPAD_RIGHT_THUMB,
	XINPUT_GAMEPAD_LEFT_SHOULDER,
	XINPUT_GAMEPAD_RIGHT_SHOULDER,
	XINPUT_GAMEPAD_A,
	XINPUT_GAMEPAD_B,
	XINPUT_GAMEPAD_X,
	XINPUT_GAMEPAD_Y
};

struct NativeInputControllerMapping
{
	s32 id;

	s32 gc_square, gc_circle, gc_triangle, gc_cross;

	s32 gc_l1, gc_l2, gc_l3;
	s32 gc_r1, gc_r2, gc_r3;

	s32 gc_start, gc_select;

	s32 gc_dpad_left, gc_dpad_right, gc_dpad_up, gc_dpad_down;

	s32 gc_axis_left_x, gc_axis_left_y;
	s32 gc_axis_right_x, gc_axis_right_y;
};

struct NativeInputController
{
	s32 connected;
	XINPUT_STATE state;
	s32 analogEnabled;
	s32 switchingAnalog;
	u32 rumbleStopTick;
	struct PlatformInputPadSnapshot snapshot;
};

struct NativeInputControllerStateSnapshot
{
	struct PlatformInputPadSnapshot snapshot;
	s32 analogEnabled;
	s32 switchingAnalog;
	s32 controllerToSlotMapping;
};

struct NativeInputStateSnapshot
{
	u32 magic;
	u32 version;
	u32 size;
	s32 keyboardControllerSlot;
	s32 lastActiveControllerSlot;
	s32 installedSnapshotsActive;
	struct PlatformInputPadSnapshot installedSnapshots[NATIVE_INPUT_MAX_CONTROLLERS];
	struct NativeInputControllerStateSnapshot controllers[NATIVE_INPUT_MAX_CONTROLLERS];
};

global_variable struct NativeInputControllerMapping s_controllerMapping;
global_variable s32 s_controllerToSlotMapping[NATIVE_INPUT_MAX_CONTROLLERS] = {-1, -1, -1, -1};

global_variable struct NativeInputController s_controllers[NATIVE_INPUT_MAX_CONTROLLERS];
global_variable struct PlatformInputPadSnapshot s_installedSnapshots[NATIVE_INPUT_MAX_CONTROLLERS];
global_variable u8 *s_padSlotData[NATIVE_INPUT_PHYSICAL_SLOT_COUNT];
global_variable s32 s_inputInitialized;
global_variable s32 s_installedSnapshotsActive;
global_variable s32 s_keyboardControllerSlot = NATIVE_INPUT_DEFAULT_KEYBOARD_SLOT;
global_variable s32 s_lastActiveControllerSlot = -1;
global_variable u32 s_rumbleTick = 0;

extern s32 g_padCommEnable;

/* Opt-in test controller. Rows are level ID, first/last frames in that LEV,
 * and a pressed PSX button mask. V2 appends L (LEV age, as V1) or G
 * (global frameCounter, which advances in paused menus). Only pad bytes are supplied; the
 * game's menu, loader and race state machines still process every action. */
#define NATIVE_INPUT_SCRIPT_LIMIT 128
struct NativeInputScriptRow
{
	int level, first, last;
	u16 pressed;
	char clock;
};
static struct NativeInputScriptRow s_inputScript[NATIVE_INPUT_SCRIPT_LIMIT];
static int s_inputScriptCount;

static void NativeInput_LoadScript(void)
{
	FILE *file;
	char header[32];
	int level, first, last, fields, version;
	char clock;
	unsigned pressed;
	s_inputScriptCount = 0;
	file = fopen("game:\\assets\\ctr360_pad_script.txt", "r");
	if (file == NULL) return;
	if (fscanf(file, "%31s", header) != 1) goto invalid;
	version = strcmp(header, "CTR360_PAD_SCRIPT_V1") == 0 ? 1 :
	          strcmp(header, "CTR360_PAD_SCRIPT_V2") == 0 ? 2 : 0;
	if (version == 0) goto invalid;
	for (;;)
	{
		struct NativeInputScriptRow *row;
		clock = 'L';
		fields = version == 2 ? fscanf(file, "%d %d %d %x %c", &level, &first, &last, &pressed, &clock) :
		                        fscanf(file, "%d %d %d %x", &level, &first, &last, &pressed);
		if (fields == EOF) break;
		if (fields != (version == 2 ? 5 : 4) || (clock != 'L' && clock != 'G')) goto invalid;
		if (s_inputScriptCount == NATIVE_INPUT_SCRIPT_LIMIT || level < 0 || first < 0 || last < first || pressed > 0xffff)
			goto invalid;
		row = &s_inputScript[s_inputScriptCount++];
		row->level = level;
		row->first = first;
		row->last = last;
		row->pressed = (u16)pressed;
		row->clock = clock;
	}
	fclose(file);
	Platform_Log("[probe] hb input-script enabled rows=%d version=%d\n", s_inputScriptCount, version);
	return;
invalid:
	s_inputScriptCount = 0;
	fclose(file);
	Platform_Log("[probe] hb input-script rejected\n");
}

internal u16 NativeInput_GetSnapshotButtons(const struct PlatformInputPadSnapshot *snapshot)
{
	return (u16)(snapshot->buttons[0] | (snapshot->buttons[1] << 8));
}

internal void NativeInput_SetSnapshotButtons(struct PlatformInputPadSnapshot *snapshot, u16 buttons)
{
	snapshot->buttons[0] = (u8)(buttons & 0xff);
	snapshot->buttons[1] = (u8)(buttons >> 8);
}

internal void NativeInput_ResetSnapshot(s32 slot)
{
	struct PlatformInputPadSnapshot *snapshot = &s_controllers[slot].snapshot;

	snapshot->connected = (u8)(slot == 0);
	snapshot->status = snapshot->connected ? 0 : NATIVE_INPUT_PAD_DISCONNECT;
	snapshot->id = snapshot->connected ? NATIVE_INPUT_PAD_DIGITAL : NATIVE_INPUT_PAD_DISCONNECT;
	NativeInput_SetSnapshotButtons(snapshot, 0xffff);
	snapshot->analog[0] = 0x80;
	snapshot->analog[1] = 0x80;
	snapshot->analog[2] = 0x80;
	snapshot->analog[3] = 0x80;
	memset(snapshot->reserved, 0, sizeof(snapshot->reserved));
}

internal s32 NativeInput_IsValidControllerSlot(s32 slot)
{
	return (slot >= 0) && (slot < NATIVE_INPUT_MAX_CONTROLLERS);
}

internal s32 NativeInput_NextControllerSlot(s32 slot)
{
	slot++;
	if (slot >= NATIVE_INPUT_MAX_CONTROLLERS)
	{
		slot = 0;
	}

	return slot;
}

internal void NativeInput_MoveKeyboardOffControllerSlot(s32 slot)
{
	if (s_keyboardControllerSlot == slot)
	{
		s_keyboardControllerSlot = NativeInput_NextControllerSlot(s_keyboardControllerSlot);
	}
}

internal void NativeInput_MakeDisconnectedSnapshot(struct PlatformInputPadSnapshot *snapshot)
{
	if (snapshot == NULL)
	{
		return;
	}

	snapshot->connected = 0;
	snapshot->status = NATIVE_INPUT_PAD_DISCONNECT;
	snapshot->id = NATIVE_INPUT_PAD_DISCONNECT;
	NativeInput_SetSnapshotButtons(snapshot, 0xffff);
	snapshot->analog[0] = 0x80;
	snapshot->analog[1] = 0x80;
	snapshot->analog[2] = 0x80;
	snapshot->analog[3] = 0x80;
	memset(snapshot->reserved, 0, sizeof(snapshot->reserved));
}

internal void NativeInput_WritePadPacket(u8 *dst, const struct PlatformInputPadSnapshot *snapshot)
{
	if ((dst == NULL) || (snapshot == NULL))
	{
		return;
	}

	dst[0] = snapshot->status;
	dst[1] = snapshot->id;
	dst[2] = snapshot->buttons[0];
	dst[3] = snapshot->buttons[1];
	dst[4] = snapshot->analog[0];
	dst[5] = snapshot->analog[1];
	dst[6] = snapshot->analog[2];
	dst[7] = snapshot->analog[3];
}

internal s32 NativeInput_UseMultitapBus(void)
{
	s32 slot;

	for (slot = NATIVE_INPUT_PHYSICAL_SLOT_COUNT; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		if (s_controllers[slot].snapshot.connected != 0)
		{
			return 1;
		}
	}

	return 0;
}

internal void NativeInput_WritePadBus(void)
{
	u8 *slot0 = s_padSlotData[0];
	u8 *slot1 = s_padSlotData[1];
	s32 useMultitap = NativeInput_UseMultitapBus();
	s32 slot;

	if (slot0 != NULL)
	{
		if (useMultitap != 0)
		{
			slot0[0] = 0;
			slot0[1] = NATIVE_INPUT_PAD_MULTITAP;
			for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
			{
				NativeInput_WritePadPacket(&slot0[NATIVE_INPUT_MULTITAP_HEADER + (slot * NATIVE_INPUT_PAD_PACKET_BYTES)], &s_controllers[slot].snapshot);
			}
		}
		else
		{
			NativeInput_WritePadPacket(slot0, &s_controllers[0].snapshot);
		}
	}

	if (slot1 != NULL)
	{
		if (useMultitap != 0)
		{
			struct PlatformInputPadSnapshot disconnected;

			NativeInput_MakeDisconnectedSnapshot(&disconnected);
			NativeInput_WritePadPacket(slot1, &disconnected);
		}
		else
		{
			NativeInput_WritePadPacket(slot1, &s_controllers[1].snapshot);
		}
	}
}

internal void NativeInput_WriteInstalledSnapshots(void)
{
	s32 slot;

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		s_controllers[slot].snapshot = s_installedSnapshots[slot];
	}

	NativeInput_WritePadBus();
}

static void NativeInput_ApplyScript(void)
{
	static u16 previousPressed;
	struct GameTracker *tracker;
	u16 pressed = 0;
	int i, frame;
	if (s_inputScriptCount == 0 || sdata == NULL || sdata->gGT == NULL) return;
	tracker = sdata->gGT;
	frame = tracker->framesInThisLEV;
	for (i = 0; i < s_inputScriptCount; i++)
	{
		const struct NativeInputScriptRow *row = &s_inputScript[i];
		int tick = row->clock == 'G' ? (int)sdata->frameCounter : frame;
		if (tracker->levelID == row->level && tick >= row->first && tick <= row->last)
			pressed |= row->pressed;
	}
	for (i = 0; i < NATIVE_INPUT_MAX_CONTROLLERS; i++)
		NativeInput_MakeDisconnectedSnapshot(&s_controllers[i].snapshot);
	s_controllers[0].snapshot.connected = 1;
	s_controllers[0].snapshot.status = 0;
	s_controllers[0].snapshot.id = NATIVE_INPUT_PAD_DIGITAL;
	NativeInput_SetSnapshotButtons(&s_controllers[0].snapshot, (u16)~pressed);
	if (pressed != previousPressed)
		Platform_Log("[probe] hb input-script f=%d level=%d levFrame=%d pressed=%04x\n", (int)sdata->frameCounter, (int)tracker->levelID, frame, (unsigned)pressed);
	previousPressed = pressed;
}

internal void NativeInput_DefaultMappings(void)
{
	s_controllerMapping.gc_square = X360_BTN_X;
	s_controllerMapping.gc_circle = X360_BTN_B;
	s_controllerMapping.gc_triangle = X360_BTN_Y;
	s_controllerMapping.gc_cross = X360_BTN_A;

	s_controllerMapping.gc_l1 = X360_BTN_LEFT_SHOULDER;
	s_controllerMapping.gc_l2 = X360_MAP_AXIS | X360_AXIS_LEFT_TRIGGER;
	s_controllerMapping.gc_l3 = X360_BTN_LEFT_THUMB;

	s_controllerMapping.gc_r1 = X360_BTN_RIGHT_SHOULDER;
	s_controllerMapping.gc_r2 = X360_MAP_AXIS | X360_AXIS_RIGHT_TRIGGER;
	s_controllerMapping.gc_r3 = X360_BTN_RIGHT_THUMB;

	s_controllerMapping.gc_dpad_up = X360_BTN_DPAD_UP;
	s_controllerMapping.gc_dpad_down = X360_BTN_DPAD_DOWN;
	s_controllerMapping.gc_dpad_left = X360_BTN_DPAD_LEFT;
	s_controllerMapping.gc_dpad_right = X360_BTN_DPAD_RIGHT;

	s_controllerMapping.gc_select = X360_BTN_BACK;
	s_controllerMapping.gc_start = X360_BTN_START;

	s_controllerMapping.gc_axis_left_x = X360_MAP_AXIS | X360_AXIS_LEFT_X;
	s_controllerMapping.gc_axis_left_y = X360_MAP_AXIS | X360_AXIS_LEFT_Y | X360_MAP_INVERSE;
	s_controllerMapping.gc_axis_right_x = X360_MAP_AXIS | X360_AXIS_RIGHT_X;
	s_controllerMapping.gc_axis_right_y = X360_MAP_AXIS | X360_AXIS_RIGHT_Y | X360_MAP_INVERSE;
}

/* Trigger axes (4 = left trigger, 5 = right trigger) scale 0..255 -> 0..32767
 * so the PSX neutral-vs-pressed bytes line up with the button threshold. */
internal s32 NativeInput_ReadAxis(const XINPUT_GAMEPAD *gamepad, s32 axis)
{
	switch (axis)
	{
	case X360_AXIS_LEFT_TRIGGER:
		return (s32)gamepad->bLeftTrigger * 32767 / 255;
	case X360_AXIS_RIGHT_TRIGGER:
		return (s32)gamepad->bRightTrigger * 32767 / 255;
	case X360_AXIS_LEFT_X:
		return (s32)gamepad->sThumbLX;
	case X360_AXIS_LEFT_Y:
		return (s32)gamepad->sThumbLY;
	case X360_AXIS_RIGHT_X:
		return (s32)gamepad->sThumbRX;
	case X360_AXIS_RIGHT_Y:
		return (s32)gamepad->sThumbRY;
	}

	return 0;
}

internal s32 NativeInput_ControllerButtonState(const XINPUT_GAMEPAD *gamepad, s32 buttonOrAxis)
{
	if (gamepad == NULL)
	{
		return 0;
	}

	if ((buttonOrAxis & X360_MAP_AXIS) != 0)
	{
		const s32 axis = buttonOrAxis & 0xFF;
		s32 value = NativeInput_ReadAxis(gamepad, axis);

		if ((value > NATIVE_INPUT_AXIS_DEADZONE || value < -NATIVE_INPUT_AXIS_DEADZONE) && ((buttonOrAxis & X360_MAP_INVERSE) != 0))
		{
			value *= -1;
		}

		return value;
	}

	if ((buttonOrAxis < 0) || (buttonOrAxis >= X360_BTN_COUNT))
	{
		return 0;
	}

	return ((gamepad->wButtons & s_buttonMasks[buttonOrAxis]) != 0) ? 32767 : 0;
}

internal u8 NativeInput_AxisToByte(s32 axis)
{
	s32 value = (axis / 256) + 128;

	if (value < 0)
	{
		return 0;
	}

	if (value > 0xff)
	{
		return 0xff;
	}

	return (u8)value;
}

internal s32 NativeInput_AxisIsActive(s32 axis)
{
	s32 absValue = axis < 0 ? -axis : axis;
	return absValue > NATIVE_INPUT_AXIS_DEADZONE;
}

internal void NativeInput_ApplyController(s32 slot)
{
	struct NativeInputController *nativeController = &s_controllers[slot];
	struct PlatformInputPadSnapshot *snapshot = &nativeController->snapshot;
	const struct NativeInputControllerMapping *mapping = &s_controllerMapping;
	const XINPUT_GAMEPAD *gamepad = &nativeController->state.Gamepad;
	u16 buttons = 0xffff;
	s32 rightX, rightY, leftX, leftY;

	if (nativeController->connected == 0)
	{
		return;
	}

	snapshot->connected = 1;
	snapshot->status = 0;
	snapshot->id = nativeController->analogEnabled ? NATIVE_INPUT_PAD_ANALOG : NATIVE_INPUT_PAD_DIGITAL;

	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_square) > 16384)
	{
		buttons &= ~0x8000;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_circle) > 16384)
	{
		buttons &= ~0x2000;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_triangle) > 16384)
	{
		buttons &= ~0x1000;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_cross) > 16384)
	{
		buttons &= ~0x4000;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_l1) > 16384)
	{
		buttons &= ~0x400;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_r1) > 16384)
	{
		buttons &= ~0x800;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_l2) > 16384)
	{
		buttons &= ~0x100;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_r2) > 16384)
	{
		buttons &= ~0x200;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_dpad_up) > 16384)
	{
		buttons &= ~0x10;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_dpad_down) > 16384)
	{
		buttons &= ~0x40;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_dpad_left) > 16384)
	{
		buttons &= ~0x80;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_dpad_right) > 16384)
	{
		buttons &= ~0x20;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_l3) > 16384)
	{
		buttons &= ~0x2;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_r3) > 16384)
	{
		buttons &= ~0x4;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_select) > 16384)
	{
		buttons &= ~0x1;
	}
	if (NativeInput_ControllerButtonState(gamepad, mapping->gc_start) > 16384)
	{
		buttons &= ~0x8;
	}

	rightX = NativeInput_ControllerButtonState(gamepad, mapping->gc_axis_right_x);
	rightY = NativeInput_ControllerButtonState(gamepad, mapping->gc_axis_right_y);
	leftX = NativeInput_ControllerButtonState(gamepad, mapping->gc_axis_left_x);
	leftY = NativeInput_ControllerButtonState(gamepad, mapping->gc_axis_left_y);

	if ((buttons != 0xffff) || NativeInput_AxisIsActive(rightX) || NativeInput_AxisIsActive(rightY) || NativeInput_AxisIsActive(leftX) ||
	    NativeInput_AxisIsActive(leftY))
	{
		s_lastActiveControllerSlot = slot;
	}

	if (((buttons & 0x1) == 0) && ((buttons & 0x8) == 0))
	{
		buttons = 0xffff;
		if (nativeController->switchingAnalog == 0)
		{
			nativeController->analogEnabled = nativeController->analogEnabled == 0;
		}
		nativeController->switchingAnalog = 1;
	}
	else
	{
		nativeController->switchingAnalog = 0;
	}

	NativeInput_SetSnapshotButtons(snapshot, buttons);
	snapshot->analog[0] = NativeInput_AxisToByte(rightX);
	snapshot->analog[1] = NativeInput_AxisToByte(rightY);
	snapshot->analog[2] = NativeInput_AxisToByte(leftX);
	snapshot->analog[3] = NativeInput_AxisToByte(leftY);
}

internal s32 NativeInput_FindActiveControllerSlot(void)
{
	s32 slot;

	if (NativeInput_IsValidControllerSlot(s_lastActiveControllerSlot) && (s_controllers[s_lastActiveControllerSlot].connected != 0))
	{
		return s_lastActiveControllerSlot;
	}

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		if (s_controllers[slot].connected != 0)
		{
			return slot;
		}
	}

	return -1;
}

internal void NativeInput_SwapControllerSlots(s32 slotA, s32 slotB)
{
	struct NativeInputController controller;
	s32 mapping;

	if (!NativeInput_IsValidControllerSlot(slotA) || !NativeInput_IsValidControllerSlot(slotB) || (slotA == slotB))
	{
		return;
	}

	controller = s_controllers[slotA];
	s_controllers[slotA] = s_controllers[slotB];
	s_controllers[slotB] = controller;

	mapping = s_controllerToSlotMapping[slotA];
	s_controllerToSlotMapping[slotA] = s_controllerToSlotMapping[slotB];
	s_controllerToSlotMapping[slotB] = mapping;

	if (s_lastActiveControllerSlot == slotA)
	{
		s_lastActiveControllerSlot = slotB;
	}
	else if (s_lastActiveControllerSlot == slotB)
	{
		s_lastActiveControllerSlot = slotA;
	}
}

internal s32 NativeInput_FindSlotForDeviceIndex(s32 deviceIndex)
{
	s32 slot;

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		if (s_controllerToSlotMapping[slot] == deviceIndex)
		{
			return slot;
		}
	}

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		if ((s_controllerToSlotMapping[slot] < 0) && (s_controllers[slot].connected == 0))
		{
			return slot;
		}
	}

	return -1;
}

internal void NativeInput_CloseController(s32 slot)
{
	struct NativeInputController *controller;

	if (!NativeInput_IsValidControllerSlot(slot))
	{
		return;
	}

	controller = &s_controllers[slot];
	controller->connected = 0;
	controller->analogEnabled = 0;
	controller->switchingAnalog = 0;
	controller->rumbleStopTick = 0;

	if (s_lastActiveControllerSlot == slot)
	{
		s_lastActiveControllerSlot = -1;
	}
}

internal void NativeInput_PollController(s32 slot)
{
	struct NativeInputController *controller;
	XINPUT_STATE state;
	DWORD result;

	if (!NativeInput_IsValidControllerSlot(slot))
	{
		return;
	}

	controller = &s_controllers[slot];
	result = XInputGetState((DWORD)slot, &state);

	if (result == ERROR_SUCCESS)
	{
		const int wasConnected = controller->connected;

		controller->state = state;
		controller->connected = 1;

		if (wasConnected == 0)
		{
			controller->analogEnabled = 1;
			controller->switchingAnalog = 0;
			NativeInput_MoveKeyboardOffControllerSlot(slot);
			Platform_Log("[CTR Native] Pad %d connected\n", slot);
		}
	}
	else if (controller->connected != 0)
	{
		NativeInput_CloseController(slot);
		Platform_Log("[CTR Native] Pad %d disconnected\n", slot);
	}
}

int Platform_InputInit(void)
{
	s32 slot;

	if (s_inputInitialized != 0)
	{
		return 1;
	}

	memset(s_controllers, 0, sizeof(s_controllers));
	memset(s_padSlotData, 0, sizeof(s_padSlotData));

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		s_controllerToSlotMapping[slot] = -1;
		NativeInput_ResetSnapshot(slot);
		s_installedSnapshots[slot] = s_controllers[slot].snapshot;
	}

	NativeInput_DefaultMappings();
	NativeInput_LoadScript();
	s_keyboardControllerSlot = NATIVE_INPUT_DEFAULT_KEYBOARD_SLOT;
	s_lastActiveControllerSlot = -1;
	s_installedSnapshotsActive = 0;
	s_rumbleTick = GetTickCount();

	/* Register the (up to) four XInput slots this build can use. */
	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		NativeInput_PollController(slot);
	}

	s_inputInitialized = 1;
	return 1;
}

void Platform_InputShutdown(void)
{
	s32 slot;

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		NativeInput_CloseController(slot);
	}

	s_inputInitialized = 0;
	s_inputScriptCount = 0;
	s_installedSnapshotsActive = 0;
	s_keyboardControllerSlot = NATIVE_INPUT_DEFAULT_KEYBOARD_SLOT;
	s_lastActiveControllerSlot = -1;
	memset(s_padSlotData, 0, sizeof(s_padSlotData));
}

void Platform_InputUpdate(void)
{
	s32 slot;

	if (s_inputInitialized == 0)
	{
		return;
	}

	if (s_installedSnapshotsActive != 0)
	{
		/* Replay/state installs PSX-shaped pad bytes; host pad state is not
		 * serialized, same contract as the SDL backend. */
		NativeInput_WriteInstalledSnapshots();
		return;
	}

	if (g_padCommEnable == 0)
	{
		return;
	}

	s_rumbleTick = GetTickCount();

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		NativeInput_PollController(slot);
		NativeInput_ResetSnapshot(slot);
		NativeInput_ApplyController(slot);

		if ((s_controllers[slot].connected != 0) && (s_controllers[slot].rumbleStopTick != 0) &&
		    ((s32)(s_rumbleTick - s_controllers[slot].rumbleStopTick) >= 0))
		{
			XINPUT_VIBRATION stop;
			stop.wLeftMotorSpeed = 0;
			stop.wRightMotorSpeed = 0;
			XInputSetState((DWORD)slot, &stop);
			s_controllers[slot].rumbleStopTick = 0;
		}
	}
	NativeInput_ApplyScript();
	NativeInput_WritePadBus();
}

void Platform_InputControllerAdded(int deviceIndex)
{
	NativeInput_PollController(deviceIndex);
}

void Platform_InputControllerRemoved(int instanceId)
{
	NativeInput_CloseController(instanceId);
}

int Platform_InputCycleKeyboardController(void)
{
	s_keyboardControllerSlot = NativeInput_NextControllerSlot(s_keyboardControllerSlot);
	return s_keyboardControllerSlot + 1;
}

int Platform_InputCycleGamepadController(void)
{
	const s32 slot = NativeInput_FindActiveControllerSlot();
	s32 nextSlot;

	if (slot < 0)
	{
		return 0;
	}

	nextSlot = NativeInput_NextControllerSlot(slot);
	NativeInput_SwapControllerSlots(slot, nextSlot);
	NativeInput_WritePadBus();
	return nextSlot + 1;
}

void Platform_InputPadInit(int slot, unsigned char *padData)
{
	if ((slot < 0) || (slot >= NATIVE_INPUT_PHYSICAL_SLOT_COUNT))
	{
		return;
	}

	s_padSlotData[slot] = padData;
	NativeInput_WritePadBus();
}

int Platform_InputPadGetState(int port)
{
	const s32 physicalSlot = (port >> 4) & 1;
	const s32 tap = port & 3;
	s32 slot;

	if (NativeInput_UseMultitapBus() != 0)
	{
		if (physicalSlot != 0)
		{
			return PadStateDiscon;
		}
		slot = tap;
	}
	else
	{
		if (tap != 0)
		{
			return PadStateDiscon;
		}
		slot = physicalSlot;
	}

	if ((slot < 0) || (slot >= NATIVE_INPUT_MAX_CONTROLLERS))
	{
		return PadStateDiscon;
	}

	return s_controllers[slot].snapshot.connected ? PadStateStable : PadStateDiscon;
}

int Platform_InputCapturePadSnapshots(struct PlatformInputPadSnapshot *dst, int count)
{
	s32 slot;

	if ((dst == NULL) || (count < NATIVE_INPUT_MAX_CONTROLLERS))
	{
		return 0;
	}

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		dst[slot] = s_controllers[slot].snapshot;
	}

	return NATIVE_INPUT_MAX_CONTROLLERS;
}

int Platform_InputInstallPadSnapshots(const struct PlatformInputPadSnapshot *src, int count)
{
	s32 slot;

	if ((src == NULL) || (count < NATIVE_INPUT_MAX_CONTROLLERS))
	{
		return 0;
	}

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		s_installedSnapshots[slot] = src[slot];
	}

	s_installedSnapshotsActive = 1;
	NativeInput_WriteInstalledSnapshots();
	return NATIVE_INPUT_MAX_CONTROLLERS;
}

void Platform_InputClearInstalledPadSnapshots(void)
{
	s_installedSnapshotsActive = 0;
}

int Platform_InputGetStateSize(void)
{
	return (int)sizeof(struct NativeInputStateSnapshot);
}

int Platform_InputCaptureState(void *dst, int dstSize)
{
	struct NativeInputStateSnapshot *snapshot = (struct NativeInputStateSnapshot *)dst;
	s32 slot;

	if ((dst == NULL) || (dstSize < (int)sizeof(*snapshot)))
	{
		return 0;
	}

	memset(snapshot, 0, sizeof(*snapshot));
	snapshot->magic = NATIVE_INPUT_STATE_MAGIC;
	snapshot->version = NATIVE_INPUT_STATE_VERSION;
	snapshot->size = sizeof(*snapshot);
	snapshot->keyboardControllerSlot = s_keyboardControllerSlot;
	snapshot->lastActiveControllerSlot = s_lastActiveControllerSlot;
	snapshot->installedSnapshotsActive = s_installedSnapshotsActive;

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		snapshot->installedSnapshots[slot] = s_installedSnapshots[slot];
		snapshot->controllers[slot].snapshot = s_controllers[slot].snapshot;
		snapshot->controllers[slot].analogEnabled = s_controllers[slot].analogEnabled;
		snapshot->controllers[slot].switchingAnalog = s_controllers[slot].switchingAnalog;
		snapshot->controllers[slot].controllerToSlotMapping = s_controllerToSlotMapping[slot];
	}

	return 1;
}

int Platform_InputRestoreState(const void *src, int srcSize)
{
	const struct NativeInputStateSnapshot *snapshot = (const struct NativeInputStateSnapshot *)src;
	s32 slot;

	if ((src == NULL) || (srcSize < (int)sizeof(*snapshot)))
	{
		return 0;
	}
	if ((snapshot->magic != NATIVE_INPUT_STATE_MAGIC) || (snapshot->version != NATIVE_INPUT_STATE_VERSION) || (snapshot->size != sizeof(*snapshot)))
	{
		return 0;
	}
	if (!NativeInput_IsValidControllerSlot(snapshot->keyboardControllerSlot))
	{
		return 0;
	}
	if ((snapshot->lastActiveControllerSlot < -1) || (snapshot->lastActiveControllerSlot >= NATIVE_INPUT_MAX_CONTROLLERS))
	{
		return 0;
	}
	if ((snapshot->installedSnapshotsActive < 0) || (snapshot->installedSnapshotsActive > 1))
	{
		return 0;
	}
	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		if ((snapshot->controllers[slot].analogEnabled < 0) || (snapshot->controllers[slot].analogEnabled > 1))
		{
			return 0;
		}
		if ((snapshot->controllers[slot].switchingAnalog < 0) || (snapshot->controllers[slot].switchingAnalog > 1))
		{
			return 0;
		}
		if (snapshot->controllers[slot].controllerToSlotMapping < -1)
		{
			return 0;
		}
	}

	s_keyboardControllerSlot = snapshot->keyboardControllerSlot;
	s_lastActiveControllerSlot = snapshot->lastActiveControllerSlot;
	s_installedSnapshotsActive = snapshot->installedSnapshotsActive != 0;

	for (slot = 0; slot < NATIVE_INPUT_MAX_CONTROLLERS; slot++)
	{
		s_installedSnapshots[slot] = snapshot->installedSnapshots[slot];
		s_controllers[slot].snapshot = snapshot->controllers[slot].snapshot;
		s_controllers[slot].analogEnabled = snapshot->controllers[slot].analogEnabled;
		s_controllers[slot].switchingAnalog = snapshot->controllers[slot].switchingAnalog;
		s_controllerToSlotMapping[slot] = snapshot->controllers[slot].controllerToSlotMapping;
	}
	NativeInput_WritePadBus();

	return 1;
}

void Platform_InputPadVibrate(int port, unsigned char *table, int len)
{
	const s32 physicalSlot = (port >> 4) & 1;
	const s32 tap = port & 3;
	s32 slot;
	u16 freqHigh;
	u16 freqLow;
	XINPUT_VIBRATION vibration;

	if (NativeInput_UseMultitapBus() != 0)
	{
		if (physicalSlot != 0)
		{
			return;
		}
		slot = tap;
	}
	else
	{
		if (tap != 0)
		{
			return;
		}
		slot = physicalSlot;
	}

	if ((slot < 0) || (slot >= NATIVE_INPUT_MAX_CONTROLLERS) || (table == NULL) || (len <= 0))
	{
		return;
	}

	if (s_controllers[slot].connected == 0)
	{
		return;
	}

	freqHigh = (u16)(table[0] * 255);
	freqLow = (u16)(len > 1 ? table[1] * 255 : 0);

	if ((freqLow != 0) && (freqLow < 4096))
	{
		freqLow = 4096;
	}

	if ((freqHigh != 0) && (freqHigh < 4096))
	{
		freqHigh = 4096;
	}

	/* XInput: left motor is the low-frequency actuator, right the high. */
	vibration.wLeftMotorSpeed = freqLow;
	vibration.wRightMotorSpeed = freqHigh;
	XInputSetState((DWORD)slot, &vibration);

	/* Run the actuators for 200ms, matching the SDL rumble duration. */
	s_controllers[slot].rumbleStopTick = GetTickCount() + 200;
}
