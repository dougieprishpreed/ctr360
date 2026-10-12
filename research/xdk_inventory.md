# ctr360 — Xbox 360 XDK inventory, build path, and debug facilities

_Read-only inventory produced 2026-09-19 for the ctr360 port. Every claim below is
tied to a file path + line, a registry value, a log line, or a tool output that was
actually read on this machine. No builds were run; no processes were launched or
killed; no file other than this report was created or modified._

Sources read:

| What | Path |
|---|---|
| XDK install | `C:\Program Files (x86)\Microsoft Xbox 360 SDK` (`%XEDK%`) |
| XDK registry key | `HKLM\SOFTWARE\WOW6432Node\Microsoft\Xbox\2.0\SDK` |
| Build wrapper | `ctr360/tools/ctr360/build_xex.sh` |
| Project | `ctr360/build-360/xex/ctr360.vcxproj` |
| Port backend | `ctr360/platform/xbox360/*.c` |
| Xenia | `F:\downloads\xenia_canary_windows` (`xenia_canary.exe`, `xenia-canary.config.toml`) |
| Logs | `F:\downloads\xenia_canary_windows\xenia.log` (218,486 lines), `...\cache\ctr360.log` (42,366 lines) — both mtime **Sep 19 10:12** (one run) |
| Xenia source (upstream, for capability questions) | `xenia-canary/xenia-canary@canary_experimental`, fetched read-only via raw.githubusercontent/API into `%LOCALAPPDATA%\Temp\xbdm_probe` |

---

## 1. XDK version, install path, and install provenance

### 1.1 Version and identity

- `%XEDK%` is set in this shell's environment: `C:\Program Files (x86)\Microsoft Xbox 360 SDK`.
- Registry `HKLM\SOFTWARE\WOW6432Node\Microsoft\Xbox\2.0\SDK`:
  - `InstalledVersion = 2,0,21256,3`
  - `ProductName = Microsoft Xbox 360 Software Development Kit`
  - `InstallPath = C:\Program Files (x86)\Microsoft Xbox 360 SDK`
  - `InstallType = Full`, `MinimumFWVersion = 6.D`
  - `SymbolsServer = SRV*C:\Program Files (x86)\Microsoft Xbox 360 SDK\bin\xbox\symsrv`
- `include/win32/xdk.h`: `#define _XDK_VER 21256`.
- Compiler banner, run read-only: `bin/win32/cl.exe` →
  `Microsoft (R) 32-bit C/C++ Optimizing Compiler Version 16.00.11886.00 for PowerPC`.
- CRT version stamp: `include/xbox/crtversion.h` → `_VC_CRT_MAJOR_VERSION 10`, `_VC_CRT_MINOR_VERSION 0`, `_VC_CRT_BUILD_VERSION 11886`, `_VC_CRT_RBUILD_VERSION 00`.
- Docs footer in the CHM topics reads `Version: 21256.3` (e.g. `DmCaptureStackBackStack`/`DmSetBreakpoint`/`XSetThreadProcessor` topics).
- Install date: XDK files stamped `Sep 5 2013` / `Dec 6 2013`; install root mtime `Sep 18 09:20` (this machine installed it during the port).
- Cross-checked against the artifact: `imagexex.exe /DUMP build-360/xex/dist/default.xex` reports library versions
  `XAPILIB 2.0.21256.0`, `D3D9 2.0.21256.0`, `D3DX9 2.0.21256.0`, `XGRAPHC 2.0.21256.0`, `XBOXKRNL 2.0.21256.0`,
  tool versions `LIBCPMT 2.0.11886.0`, `LINK 10.0.11886.0`, `C2 16.0.11886.0`, `C1 16.0.11886.0`.

### 1.2 Top-level layout

```
art/  bin/{win32,x64,xbox}/  cpu_documentation.htm  doc/1033/  include/{win32,xbox}/
lib/{win32,x64,xbox}/  readme1st.txt  redist/  relnotes.htm  Source/{crt,Samples}/
system/{uninstall,vs}/  TechPreview/Jul12Compiler/  xboxfont/
```

- `readme1st.txt` — devkit console bring-up (AV pack, DVD-EMU USB, video-mode reset combos). No build info.
- `relnotes.htm` / `cpu_documentation.htm` — both are stubs pointing at the (dead) `developer.xboxlive.com` GDN; the
  relnotes body is empty. **There is no local release-notes text.**
- `bin/win32` — 264 entries: the host-side toolchain and tools (`cl.exe`, `c1.dll`, `c1xx.dll`, `c2.dll`, `link.exe`,
  `lib.exe`, `dumpbin.exe`, `editbin.exe`, `fxc.exe`, `imagexex.exe`, `make100.exe`, `ml.exe`, plus the
  `xb*` console tools: `xbconsoletype.exe`, `xbcp.exe`, `xbdir.exe`, `xbmemdump.exe`, `xbperfview.exe`, `xbreboot.exe`,
  `xbsetcfg.exe`, `xbecopy.exe`, `xbcapture.exe`, `xbdm.dll`, `X360DebugEnginev100.dll`, `dbgeng.dll`, `windbg.exe`,
  `remote.exe`).
- `bin/xbox` — target-side payload only: `xnetconfig.xex`, `demofixer.xex`, `finished.xex`, `graphics/`, `ui/`,
  `playready/`, `symsrv/`, `ExpansionInstaller/`.
- `Source/crt` — the full CRT source tree shipped with the XDK (e.g. `assert.c`, `abort.c`, `access.c`, headers).
- `Source/Samples` — 382 sample projects across `Audio (18) / Common (110) / Graphics (87) / Media (12) /
  NaturalInput (60) / Online (22) / System (61) / ui (12)`; **263 are `*2010.vcxproj`** (the VS2010-era projects the
  build recipe uses as the canonical flag reference).
- `doc/1033` — `xbox360sdk.chm` (88,281,632 bytes, 13,854 archive entries listed by 7-Zip), plus two doc `.cab`s
  (`gpdoc_..._en-us.cab` 107 MB, `..._1.cab` 2.9 MB), `xbox360sdk.chi`, `helpcontentsetup.msha`.
  **This is the real documentation corpus** and it is 7-Zip-readable (`7z l`/`7z e` both work — used below).

### 1.3 Repo-side toolchain references

- **There is no `ctr360/toolchain/` directory** (`ls` → "No such file or directory"; `find -maxdepth 3 -type d -name 'toolchain*'` → nothing).
  The XDK is referenced purely by absolute path from three repo scripts:
  - `tools/ctr360/build_xex.sh:15` → `MSBUILD="/c/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe"`,
    `:26` → `export VCTargetsPath='C:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\'`.
  - `tools/ctr360/xdk_smoke.sh:9` → `XEDK="/c/Program Files (x86)/Microsoft Xbox 360 SDK"`, `:20-21` →
    `INCLUDE=...\include\win32;...\include\xbox;...\include\xbox\sys`, `LIB=...\lib\win32;...\lib\xbox`.
  - `tools/ctr360/find_macro_collisions.py:7` → `XDK = r"C:\Program Files (x86)\Microsoft Xbox 360 SDK\include\xbox"`.
- MSBuild integration is present and complete:
  `C:\Program Files (x86)\MSBuild\Microsoft.Cpp\v4.0\Platforms\Xbox 360\` with
  `Microsoft.Cpp.Xbox 360.{props,targets,Core.props,default.props,DLL.props,Title.props}`,
  `Microsoft.{ImageXex,Link,Lib,Deploy}.Xbox 360.props`, `Microsoft.Makefile.Xbox 360.targets`,
  `Microsoft.Cl.Xbox 360.props`, and `PlatformToolsets/2010-01`.

---

## 2. The build path (MSBuild + ImageXex) — what actually produces the XEX

`tools/ctr360/build_xex.sh` (96 lines) is the whole build:

1. `:26` sets `VCTargetsPath` so MSBuild can find the Xbox 360 platform targets under the VS2010 MSBuild tree.
2. `:33` `rm -f build-360/xex/$CONFIG/ctr360.xex` — the ImageXex step is incremental and has been observed to skip,
   so the target is deleted to force packaging.
3. `:38-40` `MSBuild.exe ctr360.vcxproj -nologo -v:minimal -m -p:Configuration=Release "-p:Platform=Xbox 360" -p:MirrorRoot=...`
   (dash switches, per the MSYS path-conversion rule).
4. `:44-55` **hard gate**: any `: error` line in the log or a non-zero msbuild exit → `FATAL`, nothing staged.
5. `:59-76` **freshness gate**: `ctr360.exe` must not be older than any mirrored `.c/.h`, and `ctr360.xex` must not be
   older than `ctr360.exe`.
6. `:80-93` stages `Release/ctr360.xex` → `dist/default.xex`, and `ctr360.xdb` (from `dist/` or `Release/`) → `dist/default.xdb`.

Project (`build-360/xex/ctr360.vcxproj`):

- `ConfigurationType=Application`, `CharacterSet=MultiByte`, `TargetName=default`, `Keyword=Xbox360Proj`.
- Release: `Optimization=MaxSpeed`, `FunctionLevelLinking=true`, `ExceptionHandling=false`, `BufferSecurityCheck=false`,
  `RuntimeLibrary=MultiThreaded` (→ `libcMT`), `CompileAs=CompileAsC`, `DebugInformationFormat=ProgramDatabase`.
- Defines: `_XBOX;CTR_NATIVE;_CRT_SECURE_NO_WARNINGS`.
- Includes: `$(MirrorRoot);$(MirrorRoot)\include;$(MirrorRoot)\platform\xbox360\sdl_shim`.
- Link (Release, `:84`): `xapilib.lib;d3d9.lib;d3dx9.lib;xgraphics.lib;xinput2.lib;xboxkrnl.lib;xbdm.lib` + `/ignore:4089`.
  Debug (`:65`) uses the `d` variants (`xapilibd.lib;d3d9d.lib;...;xinput2d.lib`).
  **`xbdm.lib` is already on the link line in both configs**, so the `Dm*` surface is linkable today with no project change.
- Build model: a **unity TU** — `main_xbox360.c` `#include`s every backend `.c` (`platform/xbox360/main_xbox360.c:44-63`).

Artifact currently staged (read-only inspection):
`build-360/xex/dist/default.xex` 3,645,440 bytes, `default.xdb` 12,004,352 bytes (Sep 19 10:07);
`imagexex /DUMP` → load address `82000000`, image size `9D0000`, entry `8211B148`, default stack size `0x40000`,
TLS slots 64 (Xenia's own dump says 64; the DUMP tool prints 40 — see §10), `NOT-COMPRESSED, ENCRYPTED`,
original PE name `ctr360.exe`, imports `xam.xex` (16) + `xboxkrnl.exe` (220), static libs listed in §1.1.

---

## 3. Libraries, include dirs, docs, samples

### 3.1 `lib/xbox` (the console link libraries)

Present (size in bytes, all stamped `Sep 5 2013`):

| Library | Size | Note |
|---|---|---|
| `xapilib.lib` / `xapilibd.lib` / `xapilibi.lib` | 12,843,184 / 13,864,118 / 12,961,614 | XAM/XAPI surface; imports `xam.xex`; **also references `xbdm.xex`** |
| `d3d9.lib` / `d3d9d.lib` / `d3d9i.lib` / `d3d9ltcg.lib` / `d3d9ltcgi.lib` | 5.9 MB … 133 MB | D3D9 + LTCG/instruction-instrumented variants |
| `d3dx9.lib` / `d3dx9d.lib` / `d3dx9i.lib` | 36.6 / 39.7 / 36.8 MB | `D3DXCompileShader` lives here (port uses it) |
| `xgraphics.lib` / `xgraphicsd.lib` | 50,990,488 / 60,616,614 | tiling, surface sizing, GPU↔CPU address translation |
| `xinput2.lib` / `xinput2d.lib` / `xinputremap.lib` | 1.40 / 1.42 / 1.80 MB | pad API the port links |
| `xbdm.lib` | 2,016,678 | **guest-side debug-monitor API**; `__IMPORT_DESCRIPTOR_xbdm.xex@21256.0+1861` |
| `xboxkrnl.lib` | 221,440 | kernel import lib; also exports `DmPrintData` |
| `xaudio2.lib` / `xaudiod2.lib` | 13.8 / 18.8 MB | XAudio2 (the port's next audio milestone) |
| `xact3.lib`, `x3daudio.lib`, `XAPOBase.lib`, `XAPOFX.lib`, `xmcore.lib`, `xmah*.lib`, `xwmadecode.lib` | — | XACT/XAPO/XMA/WMA audio |
| `libcMT.lib` / `libcMTd.lib` / `libcpMT.lib` / `libcpMTd.lib` | 10.0 / 12.6 / 10.4 / 12.3 MB | C and C++ CRT (MT / MTd) |
| `xav.lib` / `xavd.lib` | 250.9 / 273.2 MB | audio/video decode |
| `xcam.lib`, `xmedia2.lib`, `xmp.lib`, `xmic.lib`, `xhv2.lib`, `xime.lib`, `xjson.lib`, `xhttp.lib`, `xnet.lib`, `xonline.lib`, `xparty.lib`, `xrn*.lib`, `xui*.lib`, `xavatar2.lib`, `xtms.lib`, `xbc.lib`, `xcompress`(win32), `multidisc.lib`, `nuiapi.lib`, `nuispeech.lib`, `vcomp.lib`, `st.lib`/`std.lib`/`stltcg.lib`, `oldnames.lib`, `nothrownew.obj`, `tracerecording.lib` | — | full SDK surface |

`lib/win32/vs2010` holds the **host-side** debugger pieces: `xbdm.lib`, `dbgeng`-adjacent `xcompress.lib`,
`xedfile.lib`, `xgraphics.lib`, `xmaencoder.lib`, `xmcorew.lib`, `xsim.lib`, `xstudio.lib`, `xwmaencoder.lib`
(plus d3d9/d3dx9 host copies for the PC-side tools).

### 3.2 `include/` — the include dirs the build uses

The two include roots the toolchain consumes (`xdk_smoke.sh:20`, and implicitly MSBuild):

- `include/win32` — **host** headers: `xbdm.h`, `XDevkit.h`, `XDevkit.idl`, `xgraphics.h`, `xboxmath.h`, `xnamath*.h`,
  `xcompress.h`, `xdk.h`, `xectx.h`, `XedFile.h`, `xma2defs.h`, `xmaencoder.h`, `xmcore.h`, `fxl.h`, `dxfile.h`,
  `NuiTools.h`, `d3d9*.h`, `d3dx9*.h`.
- `include/xbox` (307 entries) — **target** headers, plus `include/xbox/sys` (`locking.h`, `stat.h`, `stat.inl`,
  `timeb.h`, `timeb.inl`, `types.h`, `utime.h`, `utime.inl`, `wstat.inl`).

Key target headers (lines): `d3d9gpu.h` 5,604 · `d3d9.h` 5,282 · `xgraphics.h` 2,791 · `xbox.h` 3,014 ·
`xact3.h` 1,551 · `xbdm.h` 1,477 · `xaudio2.h` 1,314 · `xam.h` 867 · `d3d9caps.h` 531 · `xinput2.h` 512 ·
`xbcrash.h` 172 · `xboxmath.h` 97 · `xtl.h` 95 · `xui.h` 38.

Library-named headers present: `d3d9.h`/`d3d9caps.h`/`d3d9types.h`/`d3d9gpu.h`/`d3d9xps.h`/`d3d9fftypes.h`/`d3dx9*.h`,
`xgraphics.h`, `xinput2.h`+`xinputdefs.h`, `xbdm.h`, `xbcrash.h`, `xtl.h`, `xbox.h`, `xam.h`, `xauth.h`, `xav.h`,
`xavatar*.h`, `xboxmath.h`/`ymath.h`, `xaudio2.h`/`xaudio2fx.h`/`XAPO.h`/`XAPOBase.h`/`XAPOFX.h`/`x3daudio.h`,
`xact3*.h`, `xmcore.h`/`xmadecoder.h`/`xma2defs.h`/`xmahardwareabstraction.h`, `xwmadecode.h`, `xmedia2.h`, `xmp.h`,
`xui*.h`, `xonline.h`, `xnet*`, `xparty.h`, `xrn*.h`, `xmic.h`, `xcam.h`, `xhv2.h`, `xime.h`, `xjson*.h`, `xhttp.h`,
`xcompress.h`, `xfilecache.h`, `xconfig.h`, `xsim*.h`, `xtms.h`, `XStudio*.h`, `Nui*.h`/`nuiapi.h`/`nuispeech.h`,
`tracerecording.h`, `xdebug` (a header), `ppcintrinsics.h`, `vectorintrinsics.h`, `omp.h`.
There is **no `xboxkrnl.h`** — the kernel surface is imported via `xboxkrnl.lib` + `winnt.h`/`xbox.h`/`xtl.h` declarations.

### 3.3 Docs

- `doc/1033/xbox360sdk.chm` — 88 MB, 13,854 entries, 7-Zip readable. Useful topics confirmed present by listing:
  `atoc_debugging*.htm`, `atoc_debug_manager*.htm` (COM `IXboxManager`/`IXboxConsole`/`IXboxDebugTarget`/`IXboxThread`/
  `IXboxStackFrame`), `atoc_IXboxDebugTarget.htm`, `atoc_hardware_perf_debug_*.htm`, `atoc_hlsl_debugging.htm`,
  `atoc_performance*.htm`, `atoc_macros_perf.htm` (VMX128 macros), `atoc_system_tools_perf_pix_*.htm`,
  `atoc_vs_debug.htm`, `audio_overview_xaudio2_debugging*.htm`, `callstd_stack_frame_layout.htm`,
  `xenon_call_stack.jpg`, and per-function pages for the whole `Dm*` set
  (`DmCaptureStackBackTrace.htm`, `DmSetBreakpoint.htm`, `DmSetDataBreakpoint.htm`, `DmGetMemory.htm`,
  `DmGetSymbolFromAddress.htm`, `DmGetSourceLineFromAddress.htm`, `DmConnectDebugger.htm`, …) plus
  `sample_CallStackRecording.htm` / `sample_CallStackDisplay.htm`.
  Extracted and read: `DmCaptureStackBackTrace`, `DmSetBreakpoint`, `DmSetDataBreakpoint`, `XSetThreadProcessor`, `atoc_macros_perf`.
- `cpu_documentation.htm` points to the Altivec PEM / PPC PEM PDFs on the (dead) GDN — **not on disk**.

### 3.4 Samples relevant to debugging (all under `Source/Samples/System`)

| Sample | Files | What it demonstrates |
|---|---|---|
| `DebugChannel` | `DebugChannel.cpp`, `DebugCmd.cpp/.h` | **guest-side remote command console**: `DmRegisterCommandProcessor(g_strDebugConsoleCommandPrefix, ...)` (`DebugCmd.cpp:92`), `DmSendNotificationString` (`:591`), plus a `REMOTE_VARIABLE` table exposing game variables to the PC console's `set` command (`DebugChannel.cpp:74-83`). PC side is the `DebugConsole` sample using `DmSendCommand`/`DmReceiveBinary` (`DebugConsole.cpp:371,411,426,451`). |
| `CallStackRecording` | `CallStackRecording.cpp` | **guest records its own call stack to a file**: `WriteStackBackTrace`/`WriteAddresses`, `DmMapDevkitDrive()` then `CreateFile("e:\\callstacks.dat")`, `DmWalkLoadedModules` + `DmFindPdbSignature` per module, writes module name / PDB path / base / size / timestamp / GUID+age, then the return addresses (byte-reversed for the host) (`CallStackRecording.cpp:75-160`). |
| `CallStackDisplay` | `CallStackDisplay.cpp`, `SymbolHelper.cpp/.h` | PC-side decoder for the above (PDB lookup → symbol names). |
| `DebuggerExtension` | `DebuggerExtension.c`, `ExtensionCommands.c`, `wdbgexts.h` | **WinDbg extension DLL** (`ExtensionCommands.c` + `.def`) — host-side debugger plugin. |
| `DebugConsole` | `DebugConsole.cpp`, `Commands.cpp` | PC-side console app that drives `DebugChannel`. |
| `PDBScope` | C#/XAML app | PDB inspection GUI. |
| `MemoryViews`, `FastCPU` (+ `XboxHardwareTimer.cpp`), `EndianSwapping` (+ `EndianSwitch.cpp`), `LockL2Cache`, `MultiCoreCollision`, `JobScheduler`, `MemAlloc`, `Privileges`, `ContentIntegrityVerification`, `Compilation` | — | platform/CPU/memory constraints and perf measurement. |

Also `Source/Samples/Graphics/HLSLDebugging` and `Graphics/FXLDumpInfo` for shader work (the port already compiles its
9–11 HLSL stages with the XDK `fxc` via `tools/ctr360/write_shader_probes.py` / `shader_probes/`).

---

## 4. Guest-side debugging APIs available from the XDK (the `xbdm`/`Dm*` surface)

`include/xbox/xbdm.h` (1,477 lines) is the guest-visible debug API. Library: `xbdm.lib` (already on the link line).
The header is explicit that this is the **console-side** half of the debug monitor; the PC half is `xbdm.dll` +
`X360DebugEnginev100.dll` + `windbg.exe` in `bin/win32`.

### 4.1 What exists (header evidence)

- **Breakpoints** (`xbdm.h:216-221`): `DmSetBreakpoint(PVOID)`, `DmRemoveBreakpoint(PVOID)`, `DmSetInitialBreakpoint(void)`,
  `DmSetDataBreakpoint(PVOID, DWORD dwType, DWORD dwSize)`, `DmIsBreakpoint(PVOID, LPDWORD)`.
  Types (`:208-214`): `DMBREAK_NONE/WRITE/READWRITE/EXECUTE/FIXED/READ`.
- **Execution control** (`:224-227`): `DmStop(void)`, `DmGo(void)`, `DmHaltThread(DWORD)`, `DmContinueThread(DWORD, BOOL)`.
- **Stack trace** (`:1136-1138`): `#define DM_MAX_STACK_DEPTH 256` and
  `DmCaptureStackBackTrace(ULONG FramesToCapture, PVOID *BackTrace)`.
  CHM page: *"Retrieves function return addresses from the frames on the call stack… relies on the consistent
  application of the PowerPC Calling Convention… Xbox 360 executables do not load at the preferred load address, use
  `DmWalkLoadedModules` to determine the base address."* Max 256 frames; unfilled slots are 0.
- **Notifications** (`:190-203`, `:34-64`): `DmOpenNotificationSession(DWORD dwFlags, PDMN_SESSION*)`,
  `DmNotify(PDMN_SESSION, DWORD dwNotification, PDM_NOTIFY_FUNCTION)`, `DmRegisterNotificationProcessor(...)`,
  `DmCloseNotificationSession`. Notification IDs include `DM_BREAK`, `DM_DEBUGSTR`, `DM_EXCEPTION`, `DM_ASSERT`,
  `DM_DATABREAK`, `DM_BUGCHECK`, `DM_ASSERTION_FAILURE`, `DM_STACKTRACE`, `DM_CREATETHREAD`, `DM_MODLOAD`, …
  (`:37-58`). Session flags: `DM_PERSISTENT|DM_DEBUGSESSION|DM_ASYNCSESSION`.
- **Stop-on-event** (`:238-246`): `DMSTOP_CREATETHREAD 0x1`, `DMSTOP_FCE 0x2`, `DMSTOP_DEBUGSTR 0x4`,
  `DMSTOP_STACKTRACE 0x8`, `DMSTOP_MODLOAD 0x10`, `DMSTOP_TITLELAUNCH 0x20`, `DMSTOP_PGOMODSTARTUP 0x40`; `DmStopOn(flags, fStop)`.
- **Thread introspection** (`:324-341`): `DmGetThreadList`, `DmGetThreadContext(DWORD, PXCONTEXT)`,
  `DmSetThreadContext`, `DmIsThreadStopped(DWORD, PDM_THREADSTOP)`, `DmGetThreadInfoEx`, `DmSuspendThread`, `DmResumeThread`.
  (`PXCONTEXT` = `PCONTEXT` on console — `xbdm.h:14-16`.)
- **Module/symbol walks** (`:336-345`): `DmWalkLoadedModules(PDM_WALK_MODULES*, PDMN_MODLOAD)`,
  `DmWalkLoadedModulesEx`, `DmCloseLoadedModules`, `DmWalkModuleSections`, `DmGetXexHeaderField`.
- **Memory access** (`:265-286`): `DmGetMemory`, `DmSetMemory`, `DmWalkCommittedMemory`, `DmCloseCommittedMemory`,
  `DmAllocatePool`, `DmAllocatePoolWithTag`, `DmFreePool`.
- **Console-state / crash** (`:252-263`, `:396-457`, `:485`): `DmReboot`, `DmRebootEx`, **`DmCrashDump(BOOL fReturn)`**,
  `DmGetConsoleType`, `DmGetConsoleFeatures`, `DmGetSystemInfo`, `DmGetXboxName`/`DmSetXboxName`, `DmGetDumpMode`/`DmSetDumpMode`.
- **Memory reporting** (`:1084-1115`): `DmQueryMemoryStatistics`, `DmQueryTitleMemoryStatistics`,
  `DmQueryAllocationTypeName`, `DmRegisterAllocationType`, `DmInsertAllocationEntry`, `DmRemoveAllocationEntry`
  (allocation-type tags from `DM_ALLOCTYPE_*`, `:1100-1134`).
- **Profiling / counters** (`:552-568`, `:654-658`, `:867-1017`): `DmStartProfiling(LPCSTR logFileName, DWORD bufSize)`,
  `DmStopProfiling`, `DmAbortProfiling`, `DmSetProfilingOptions`, `DmIsFastCAPEnabled`,
  `DmRegisterPerformanceCounter`/`DmUnregisterPerformanceCounter`, `DmOpenPerformanceCounter`/`DmQueryPerformanceCounterHandle`,
  `DmEnableGPUCounter`, and a full PMC block (`DmPMCInstallAndStart`, `DmPMCStart`/`Stop`, `DmPMCGetCounters`, …).
- **File-event monitor** (`:229-232`): `DmStartFileEventCapture`, `DmStopFileEventCapture`, `DmSetFileEventMarker`.
- **Debugger presence** (`:234-236`): `DmIsDebuggerPresent(void)`, `DmGetDebuggerConnection(ULONG*, ULONG*)`;
  `#define DEBUGGER_PORT 0x2da` (`:206`).
- **Error space**: `XBDM_NOERR = 0x02DA0000`, failures `0x82DA00xx` (`xbdm.h:579-634`), incl. `XBDM_ENDOFLIST = 0x82DA0104`.
- **Crash-dump reader (host side)**: `include/xbox/xbcrash.h` (172 lines) — `XcrashOpenFile`, `XcrashGetMemory`,
  `XcrashGetThreadList`, `XcrashGetThreadContext`, `XcrashWalkLoadedModules`, `XcrashGetXtlData`, … for reading a
  `.xcrash` dump off a console.

### 4.2 The other debug-print channels (not `Dm*`)

- **`OutputDebugStringA/W`** — declared in `include/xbox/winbase.h:2212-2227` (`XWINBASEAPI VOID WINAPI OutputDebugStringA(LPCSTR)`).
  **This is what the port already uses** (`platform/xbox360/native_xbox360_log.c:31`, plus error paths at `:75`, `:127`).
  `xapilib.lib` also exports `RtlOutputDebugString`, `DbgPrintf`, `XDebugClearTitle`.
- **`DbgPrint`** — an `xboxkrnl` ordinal (Xenia's table: `XE_EXPORT(xboxkrnl, 0x00000003, DbgPrint, kFunction)`).
  Not declared in any XDK header that ships on disk (the only in-tree use is
  `include/xbox/xnamathmisc.inl:2331`, which calls it for assert text); `xboxkrnl.lib` exports `__imp_DbgPrint`.
  It is a printf-style kernel debug print — on real hardware it lands in the debug channel.
- **`RtlCaptureStackBackTrace`** — `xboxkrnl` ordinal `0x2CD`; also exported by `xboxkrnl.lib`
  (`__imp_RtlCaptureStackBackTrace`). **Guest-side, no debugger needed** — this is the cheapest stack-trace facility
  available to the port on real hardware. (See §4.4 for Xenia's handling.)
- **`DbgBreakPoint`** / `DbgBreakPointWithStatus` — `xboxkrnl` ordinals 1 / 2 (`__imp_DbgBreakPoint`);
  `__debugbreak()` / `__trap()` are available from `include/xbox/ppcintrinsics.h:291` (`#define __trap() __debugbreak()`).
- **`RtlAssert`** (`xboxkrnl` ordinal `0x118`), `RtlRaiseException`, `KeBugCheck`/`KeBugCheckEx` (0x52/0x53).
- **CRT assert machinery**: `include/xbox/crtdbg.h` — `_ASSERT`/`_ASSERTE`/`_ASSERT_EXPR` (no-op in non-debug builds,
  `:179-191`; report-based in `_DEBUG`, `:395-414`), `_CrtDbgBreak()` = `__debugbreak()` (`:502`),
  `_CrtDbgReport`/`_CrtSetReportHook`/`_CrtSetReportMode` (`:267-397`).
- **Xbox trace recording (PIX)**: `include/xbox/tracerecording.h` — `XTraceStartRecording("devkit:\\trace.pix2")`,
  `XTraceStartRecordingFunction`, `XTraceStopRecording`, `XTraceSaveBuffer`, `XTraceIsRecording`, `XTraceSetBufferSize`,
  `XTraceSetIOThread`; lib `lib/xbox/tracerecording.lib` (1.09 MB). Requires PIX attached; not usable under Xenia
  (`kernel_pix = false` in the config, §5).

### 4.3 How Xenia implements the same surface (read from upstream source, `canary_experimental`)

`src/xenia/kernel/xbdm/` = `xbdm_table.inc` (255 exports) + `xbdm_misc.cc` (the only implementation file) +
`xbdm_module.cc`/`xbdm_ordinals.h`/`xbdm_private.h`. `xbdm_module_export_groups.inc` registers exactly one group:
`XE_MODULE_EXPORT_GROUP(xbdm, Misc)`.

- **Implemented (10)** — `DmAllocatePool`, `DmFreePool`, `DmGetConsoleType`, **`DmGetMemory`**, `DmGetThreadList`,
  `DmGetXboxName`, **`DmMapDevkitDrive`**, `DmResumeThread`, `DmSetMemory`, `DmSuspendThread`.
- **Stub (25)** — incl. `DmIsDebuggerPresent` (returns `cvars::debug`), `DmSendNotificationString` (returns success),
  `DmOpenNotificationSession`/`DmNotify`, `DmRegisterCommandProcessor[Ex]` ("Return success to prevent some games from
  stalling"), `DmWalkLoadedModules` (returns `XBDM_ENDOFLIST` — *"Some games will loop forever unless this code is
  returned"*), `DmFindPdbSignature` (zeroes the struct, returns `X_ERROR_INVALID_PARAMETER`), `DmGetSystemInfo`,
  `DmGetXbeInfo`, `DmStartProfiling`/`DmStopProfiling`/`DmSetProfilingOptions`, `DmPMC*`, `DmQueryTitleMemoryStatistics`.
- **Sketchy (3)** — `DmGetThreadInfoEx`, `DmPMCGetCounterName`, `DmPMCInstallAndStart`.
- **Not implemented at all (~217 exports)** — no `*_entry` function exists. **This includes every breakpoint and
  execution-control call the port would want:**
  `DmSetBreakpoint`, `DmRemoveBreakpoint`, `DmSetDataBreakpoint`, `DmSetInitialBreakpoint`, `DmIsBreakpoint`,
  `DmStop`, `DmGo`, `DmHaltThread`, `DmContinueThread`, `DmStopOn`, `DmGetThreadContext`, `DmSetThreadContext`,
  `DmIsThreadStopped`, `DmCrashDump`, `DmReboot`, `DmEnableStackTrace`, `DmGetDebuggerConnection`, `DmLoadExtension`,
  `DmWalkModuleSections`, `DmGetXexHeaderField`, `DmGetFileAccessCount`, `DmStartFileEventCapture`/`DmSetFileEventMarker`,
  and the whole `XLF*` lock-free-logging family.
- **`DmCaptureStackBackTrace` is a stub that returns success and writes only zeros**: the entry zero-fills
  `frames_to_capture` words and returns `XBDM_SUCCESSFUL` (`xbdm_misc.cc:114-131`). A caller that checks the HRESULT
  sees success and reads a buffer of NULLs. There is no guest stack walker in Xenia.
- **The module is only loaded in devkit mode**: `src/xenia/emulator.cc:320-323` —
  `// 415608C3 anti-cheat checks if XDBM is loaded.` / `if (cvars::console_type >= 0) { LOAD_KERNEL_MODULE(xbdm::XbdmModule); }`.
  `console_type = 0` (Development Kit) in this config, so `xe:\xbdm.xex` **is** registered under Xenia.
- **The one genuinely useful `Dm*` for the port under Xenia is `DmMapDevkitDrive`**: it mounts `devkit:`/`e:` onto
  `<xenia dir>\devkit` (`xbdm_misc.cc:150-175`) — a real host path that is writable, unlike `game:\` without
  `allow_game_relative_writes`. `DmGetMemory`/`DmSetMemory` also work (they translate through guest memory).
- **`DbgPrint` IS implemented in Xenia** and is the best guest print channel that is *not* the port's own log:
  `src/xenia/kernel/xboxkrnl/xboxkrnl_strings.cc:628-647` —
  `XELOGI("(DbgPrint) {}", string_util::rtrim(data.str()));`, registered `DECLARE_XBOXKRNL_EXPORT1(DbgPrint, kNone, kImplemented)`.
  It goes through the full guest `StringFormatData` formatter, so `%d/%s/%08X` work like the guest expects.
  `XamDbgPrint` (xam 0x1E0), `RtlOutputDebugString` (xam 0x3EB), `RtlDebugPrint` (xam 0x3F1), `DmPrintData`
  (xboxkrnl 0x378), `RtlAssert` (xboxkrnl 0x118) and `RtlCaptureStackBackTrace` (0x2CD) are **in the ordinal tables
  but have no implementation in the tree** — they resolve to the unimplemented-import path
  (`"WARNING: Imported kernel function {} is unimplemented!"` in the binary).
- **Guest crash paths Xenia does implement** (`xboxkrnl_debug.cc`):
  - `DbgBreakPoint_entry() { xe::debugging::Break(); }` (`:26`) — `debugging::Break()` is `__debugbreak()` on the
    **host** (`base/debugging_win.cc:20`), so a guest `__debugbreak()` traps into the host debugger, or crashes the
    host process if none is attached. With the config's `break_on_debugbreak = true` (Xenia JITs an `int3`) this is a
    usable hard breakpoint — but only when a host debugger is attached.
  - `RtlRaiseException_entry` (`:126-150`) — handles `0x406D1388` (SetThreadName) and `0xE06D7363` (C++ exception →
    `XELOGE("Guest attempted to throw a C++ exception!")`); **anything else logs
    `XELOGE("Guest attempted to trigger a breakpoint!")` and returns** — no unwinding ("TODO(benvanik): unwinding.
    This is going to suck."). Registered `kStub`.
  - `KeBugCheckEx_entry` (`:150-188`) — logs `*** STOP: 0x%08X (…)`, breaks to the host debugger if attached, shows a
    GUI box *"The guest kernel has crashed (KeBugCheck). … The faulting thread has been suspended."*, then **suspends
    the guest thread instead of killing the host process**. `KeBugCheck` → `KeBugCheckEx(code,0,0,0,0)`.
  - `RtlUnwind` and `__C_specific_handler` are the two imports Xenia's own log flags `!!` (unimplemented) — relevant
    because the port's SEH-free C89 build never uses them (see §4.4).

### 4.4 What the port could call today (concrete, evidence-based)

1. **`DbgPrint(fmt, ...)`** — implemented by Xenia (`XELOGI("(DbgPrint) …")` → `xenia.log`), real hardware puts it in
   the debug channel. `xboxkrnl.lib` provides `__imp_DbgPrint`. This gives a **second, independent print channel**
   that does not share the port's own `Platform_Log` file path, and — unlike `OutputDebugStringA` — its output is
   formatted by the guest CRT and re-formatted by the emulator.
   *Caveat*: the XDK ships no header declaration for it (`grep -rn 'DbgPrint' include/` finds only `xnamathmisc.inl:2331`),
   so the port would declare it itself: `XBOXAPI ULONG DbgPrint(const char *fmt, ...);` — signature per the Xenia
   implementation (`format` + varargs via `StackArgList`).
2. **`RtlCaptureStackBackTrace(frames, hash, buf, ...)`** — exported by `xboxkrnl.lib` and available on real hardware,
   but **Xenia has no implementation** → calling it under Xenia hits the unimplemented-import warning. On a real
   RGH/JTAG console it is the only stack-trace primitive the port can use without `xbdm`. Treat it as a
   console-only facility, or guard it behind `DmIsDebuggerPresent()`/a build flag.
3. **`DmCaptureStackBackTrace(frames, PVOID *buf)`** — returns `XBDM_SUCCESSFUL` under Xenia **with a zero-filled
   buffer**, so a caller cannot distinguish "no frames" from "no walker". Do not build a fault reporter on it.
4. **`__debugbreak()` / `__trap()`** — `ppcintrinsics.h:291`. Under Xenia with `break_on_debugbreak = true` this traps
   to the host debugger; with none attached it crashes the host process (which is *worse* than the current silent
   wedge — see the §7 note). Not recommended as a probe.
5. **`KeBugCheckEx(code, a,b,c,d)`** — the most *informative* failure path under Xenia: it prints a full
   `*** STOP: …` line and suspends the faulting thread instead of wedging silently. `KeBugCheck` is `kImplemented`,
   `KeBugCheckEx` is registered `kStub` but has a real body. A port-side "unreachable/invariant violated" handler could
   call it — but note the guest thread is suspended, so the run ends.
6. **`DmMapDevkitDrive()`** — mounts a writable host directory under Xenia (`<xenia>\devkit` → `devkit:`/`e:`),
   independent of `game:\` write policy. Useful if the port ever needs a second output target.
7. **`DmIsDebuggerPresent()`** — returns `cvars::debug` under Xenia (`xbdm_misc.cc:76-80`), i.e. it reports "true"
   whenever `[General] debug = true`, **not** whether a debugger is really attached. On real hardware it reflects the
   actual debug-monitor connection. Do not use it to gate behaviour that must differ between emulator and console.
8. **`DmRegisterCommandProcessor(prefix, handler)`** — stubbed to success under Xenia (deliberately, so games do not
   stall), real on hardware (drives the `DebugConsole` PC app). A port-side remote-console command table
   (`DebugChannel.cpp:74-83` pattern) would work on the console and be inert-but-harmless under Xenia.

### 4.5 What the port does today

`platform/xbox360/native_xbox360_log.c` — `s_logRoots[4] = { "cache:\\", "game:\\", "hdd1:\\", "usb0:\\" }` (`:24`),
per-line `fflush` (`:35-36`), and `OutputDebugStringA(text)` on **every** line (`:31`), so the whole trace is mirrored
into the emulator log. There is **no** fault handler, no `__try/__except`, no `RtlCaptureStackBackTrace`, no
`SetUnhandledExceptionFilter`, no `DbgPrint` anywhere in `platform/` or `game/`
(`grep -rn 'RtlCaptureStackBackTrace|SetUnhandledExceptionFilter|__try|__except|DbgBreakPoint|KeBugCheck' platform/ game/` → 0 hits).
The consequence is visible in the current run: the port **wedges silently** — the last guest line is a probe, and
nothing reports that the thread is stuck (§6.4).

---

## 5. Xenia Canary's debugging options (`F:\downloads\xenia_canary_windows\xenia-canary.config.toml`)

Note: the file named `config.toml` **does not exist** in that directory; the live config is
**`xenia-canary.config.toml`** (62,777 bytes, mtime Sep 19 10:07; backups `.bak-ctr360`, `.bak-ctr360-2`,
`xenia-canary.config - Copy.toml`). Other per-title configs in the same dir (`fear2`, `halo3`, `haloreach`, `neverdead`)
are unrelated. Build: `canary_experimental@44cb87328 on Sep 13 2026` (`xenia.log:1`), exe mtime Sep 13 04:48,
17,124,864 bytes. `defaults_date = 2026040912`.

### 5.1 Currently-set values (the whole config, section by section — debug-relevant lines)

| Section | Option | Value | Relevance |
|---|---|---|---|
| `[CPU]` | `break_condition_gpr` / `break_condition_op` / `break_condition_value` / `break_condition_truncate` | `-1` / `"eq"` / `0` / `true` | conditional breakpoint on a GPR — **unset (gpr=-1)** |
| | `break_on_debugbreak` | `true` | `int3` on JITed `__debugbreak` |
| | `break_on_instruction` | `0` | **unset** — address breakpoint available (`--break-on-instruction`) |
| | `break_on_start` | `false` | |
| | `break_on_unimplemented_instructions` | `true` | breaks to host debugger / crashes without one |
| | `debug_symbol_loader` | `false` | dbghelp logging/validation |
| | `debugprint_trap_log` | `false` | log debugprint traps to the active debugger |
| | `disassemble_functions` | `false` | |
| | `dump_translated_hir_functions` | `false` | |
| | `store_all_context_values` | `false` | keeps dead context stores for debugging |
| | `trace_function_coverage` / `_data` / `_references` / `trace_functions` | `false` (all) | function-level tracing |
| | `trace_function_data_path` | `""` | |
| | `load_module_map` | `""` | load a `.map` for symbol names + diff with the generated DB |
| | `record_mmio_access_exceptions` / `emit_mmio_aware_stores_…` | `true` | MMIO profiling for later runs |
| | `validate_hir`, `emit_source_annotations`, `enable_early_precompilation`, `writable_code_segments`, `no_reserved_ops`, `pvr = 7407360` | — | JIT diagnostics / PVR id |
| `[D3D12]` | `d3d12_debug`, `d3d12_break_on_error`, `d3d12_break_on_warning`, `d3d12_dxbc_disasm`, `d3d12_dxbc_disasm_dxilconv`, `d3d12_tessellation_wireframe` | all `false` | D3D12 validation/disassembly — **all off** |
| `[GPU]` | `gpu` | `"any"` | picks D3D12 or Vulkan |
| | `readback_resolve` | `"none"` | CPU readback of resolve: **disabled** (relevant: the port does VRAM readback) |
| | `readback_memexport` | `false` | |
| | `occlusion_query` | `"fast"` | + `occlusion_query_fake_lower_threshold=80`, `_upper=100`, `_saturation=1` |
| | `draw_resolution_scale_x/y` | `1` / `1` | |
| | `async_shader_compilation` | `true` | |
| `[GPU.Debug]` | `dump_shaders` | `""` | shader dump path |
| | `target_trace_file` | `""` | load a GPU trace file |
| | `trace_gpu_stream` | `false` | trace all GPU packets (heavy) |
| | `trace_dump_path` / `trace_gpu_prefix` | `""` / `"scratch/gpu/"` | |
| | `dxbc_source_map` | `false` | Xenos disasm as DXBC comments |
| | `execute_unclipped_draw_vs_on_cpu` (+ `_for_psi_render_backend`, `_with_scissor`) | `true`/`true`/`false` | |
| | `tiled_shared_memory` | `true` | *"Disable for graphics debugger compatibility"* (RenderDoc) |
| | `primitive_processor_cache_min_indices` | `4096` | |
| | `store_shaders` | `true` | |
| `[General]` | **`debug`** | **`true`** | retain debug info → debugger UI / call stacks usable |
| | `allow_game_relative_writes` | `true` | makes `game:\` writable |
| | `allow_plugins` | `false` | loads `plugins\<title_id>\plugin.xex` |
| | `apply_patches` | `true` | |
| | `launch_module` | `""` | |
| | `time_scalar` | `1` | speed/slow guest time |
| | `priority_class` | `0` | |
| | `controller_hotkeys` | `false` | |
| `[Kernel]` | `console_type` | `0` | **Development Kit** → Xenia loads `xbdm.xex` (§4.3) |
| | `kernel_debug_monitor` | `false` | debug-monitor support |
| | `kernel_pix` | `false` | **PIX** — enables the `KeDebugMonitorCallback` PIX path |
| | `kernel_cert_monitor` | `false` | |
| | `cl` | `""` | extra command line handed to the guest |
| | `ignore_thread_affinities` / `ignore_thread_priorities` | `true` / `false` | |
| | `kernel_build_version` | `1888` | |
| | `staging_mode` | `false` | |
| `[Logging]` | **`log_level`** | **`3`** | 0=error,1=warning,2=info,3=debug |
| | `log_string_format_kernel_calls` | `true` | logs `sprintf`/`_snprintf`/`vsprintf` usage |
| | `log_to_stdout` | `true` | |
| | `flush_log` | `true` | |
| | `log_file` | `""` | → default `xenia.log` |
| | `log_to_debugprint` | `false` | needs DebugView |
| | `log_mask` | `0` | bitmask: Kernel=1, Apu=2, Cpu=4, Gpu=8 |
| | `enable_console` | `false` | console window |
| | `disassemble_pm4` | `false` | debug builds only |
| | `log_guest_driven_gpu_register_written_values` | `false` | debug builds only |
| | `log_ringbuffer_kickoff_initiator_bts` | `false` | debug builds only (pseudo-stacktrace of the guest thread) |
| | `log_high_frequency_kernel_calls` | `false` | |
| `[Memory]` | **`protect_zero`** | **`true`** | zero page unmapped — the null-deref trap the port already used |
| | `protect_on_release`, `scribble_heap`, `scribble_heap_value`, `writable_executable_memory`, `ignore_offset_for_ranged_allocations` | `false`/`false`/`0`/`true`/`false` | |
| `[UI]` | `headless` | `false` | |
| | `show_profiler` | `false` | **built-in profiler UI** |
| | `imgui_debug` | `false` | ImGui debug tools |
| | `storage_selection_dialog` | `false` | |
| `[Video]` | `avpack` | `8` (HDMI) | |
| | `interlaced` | `false` | |
| | `enable_3d_mode` | `false` | |
| | `custom_internal_display_resolution_x/y` | `0`/`0` | |
| `[Vulkan]` | `vulkan_validation` | `false` | validation layer |
| | `vulkan_log_debug_messages` | `true` | VK_EXT_debug_utils → Xenia log |
| | `spirv_disable_rounding_mode_rte` | `false` | *"Enable this to allow shader debugging in RenderDoc"* |
| | `vulkan_sparse_shared_memory` | `true` | *"Disabling … allows graphics debuggers that don't support sparse binding"* |
| | `vulkan_semaphore_reuse_workaround` | `false` | |
| `[x64]` | `enable_host_guest_stack_synchronization` | `true` | records guest/host stack mappings at function starts; *"fixes crashes in games that use setjmp/longjmp"* |
| | `max_stackpoints` | `65536` | |
| | `instrument_call_times` | `false` | **per-function guest timing** |
| | `align_all_basic_blocks` | `0` | |
| | `enable_incorrect_roundingmode_behavior`, `enable_rmw_context_merging`, `delay_via_maybeyield`, `x64_extension_mask`, `xop_*` | — | codegen knobs |
| `[APU]` | `mute`, `xma_decoder = "new"`, `use_dedicated_xma_thread`, `enable_xmp`, `ffmpeg_verbose` | — | audio; `mute=false` |
| `[Storage]` | `mount_cache`, `mount_memory_unit`, `mount_scratch`, `force_mount_devkit`, `storage_root`, `cache_root` | `true`/`false`/`false`/`false`/`""`/`""` | **`mount_scratch=false`** — `scratch:` is NOT mounted; `devkit:` only if `force_mount_devkit` or `DmMapDevkitDrive` |
| `[Profiles]` | `logged_profile_slot_0_xuid = "E03000004DE92116"` | — | |
| `[Display]` | `fullscreen=false`, `postprocess_*`, `present_*` | — | presentation only |

### 5.2 Options NOT currently enabled that are worth turning on for debugging

Ranked by usefulness for this port's current frontier (a guest-thread wedge with no crash):

1. **`[GPU.Debug] trace_gpu_stream = true`** (with `trace_dump_path` set) — dumps every PM4 packet. This is the
   direct instrument for the F2 class of bug (`Surface pitch 9552 …` / `PM4_DRAW_INDX … Failed in backend`, §6.3).
   Cost: hundreds of MB per run (skill's own warning).
2. **`[Logging] log_to_debugprint = true`** + DebugView — a second, host-level sink that survives a wedged guest.
3. **`[x64] instrument_call_times = true`** — per-function guest timings; would name the function that eats the
   wall-clock time in frame 13 (the port's own probes currently only bracket phases).
4. **`[Kernel] kernel_debug_monitor = true`** — enables the debug-monitor path (`KeDebugMonitorCallback`); required
   for the `kernel_pix` PIX route and generally for monitor-driven behaviour.
5. **`[UI] show_profiler = true`** — built-in profiling UI (host-side).
6. **`[CPU] break_on_instruction = <guest addr>`** / `break_condition_gpr` — a real guest-address breakpoint,
   settable from the config or `--break-on-instruction` on the command line. Combined with `[General] debug = true`
   this is the closest thing to an interactive breakpoint (the guest debugger window, below).
7. **`[GPU] readback_resolve`** — currently `"none"`; the port does VRAM readback through `Resolve`. `fast`/`full`
   changes readback semantics and may be needed once readback-dependent logic runs.
8. **`[Memory] protect_on_release = true`** — turns use-after-free into a visible fault instead of silent corruption;
   directly relevant given the port's history of wild stores (`modelPtr[-16896]`).
9. **`[GPU.Debug] dump_shaders = <path>`** — pairs with the port's 9–11 HLSL stages.

Deliberately-left-off items are consistent with the skill's guidance: `trace_functions` (millions of lines),
`dump_shaders` without a path, `log_to_debugprint` (needs an external viewer), `[GPU.Debug]` tracers.

### 5.3 Interactive debugger, menus and hotkeys (from strings in `xenia_canary.exe`)

Xenia Canary carries a **built-in guest debugger UI** (ImGui), not enabled by default:

- Menu: `&CPU` → **`&Break and Show Guest Debugger`** (hotkey **`Pause/Break`**) and
  **`&Break into Host Debugger`** (hotkey **`Ctrl+Pause/Break`**); `&GPU` → `&Trace Frame`; `&Display` →
  `&Clear Runtime Caches`, `&Take Screenshot`.
- Debugger window title `Xenia Debugger`; the gate string is
  **`Xenia must be launched with the --debug flag in order to enable debugging.`** — i.e. the debugger UI requires the
  `--debug` command-line flag, which this run does **not** use (the log shows
  `Disabling --debug due to lack of stack walker` in the binary's string table; the live run has no such line, so the
  flag was simply not passed — the run is launched by `tools/ctr360/run_xenia.sh` with just the XEX path).
- Debugger panes (ImGui ID strings): `##threads_pane`, `##registers_pane` (`##guest_general`, `##guest_float`,
  `##guest_vector`, `##host_general`, `##host_vector`, `##iregister%d`, `##dregister%d`, `##lregister%d`,
  `##vregister%d_%d`), `##breakpoints_pane` (`##add_code_breakpoint`, `##add_data_breakpoint`,
  `##add_gpu_breakpoint`, `##add_kernel_breakpoint`, `##toggle_line_bp`, `##breakpoint_context_menu`),
  `##function_pane`, `##source_pane`, `##memory_pane`, `##kernel_calls`, `##log_pane`.
  → **code breakpoints, data breakpoints, GPU breakpoints, kernel-call breakpoints, single-stepping, per-thread
  register/context inspection, a memory viewer and a kernel-call log are all present in this build.**
- Status strings for guest faults: `Guest attempted to trigger a breakpoint!`,
  `Guest attempted to throw a C++ exception!`, `The guest has crashed.`, `The guest kernel has crashed (KeBugCheck).`,
  `Xenia has now paused itself.`, `Click %s Button to break in debugger! (remap w/ Ctrl+Shift)`,
  `Debugger demanded a listener but no handler was registered.`
- Controller hotkeys (in-game, `controller_hotkeys = false` in the config): `A + Guide = Toggle Readback Resolve`,
  `X + Guide = Toggle Clear Memory Page State`, `B + Guide` / `Back + Start = Toggle between loglevel set in config and
  the 'Disabled' loglevel`, `Right Shoulder + Guide = Clear GPU Cache`, `D-PAD Up/Down + Guide = Double/Half CPU Scalar`,
  `D-PAD Right + Guide = Reset CPU Scalar`, `Y = Toggle Fullscreen`.

**Consequence for the port: the single biggest debugging lever that is not currently in use is launching Xenia with
`--debug`** — that is what unlocks the breakpoints/threads/registers/memory panes and the `Pause/Break` guest-break
hotkey. `tools/ctr360/run_xenia.sh` launches with no flags.

---

## 6. How Xenia reports guest faults, hangs, and unimplemented imports (from this run's logs)

Log prefixes (`xenia.log`): `d>` debug, `i>` info, `w>` warning, `!>` error, `F>` filesystem trace (not a failure),
`K>` kernel, `G>` GPU, `V`/`F`/`*` = import-table markers. In this run: 129,972 `d>`, 2,922 `G>`, 112 `F`,
104 `!>`, 79 `i>`, 68 `F>`, 9 `K>`.

### 6.1 What the run's `!>`/`w>` lines actually are

```
 38 !> Surface pitch 9552 larger than the maximum texture width 8192 specified by the guest
 25 !> PM4_DRAW_INDX(6, 4, 2): Failed in backend
 13 !> PM4_DRAW_INDX_2(3, 8, 2): Failed in backend
 12 !> Surface pitch 9328 larger than the maximum texture width 8192 specified by the guest
 12 !> PM4_DRAW_INDX(12, 4, 2): Failed in backend
  3 w> BaseHeap::AllocFixed attempting commit on unreserved page
  1 w> XEX load failed with code 3, trying with devkit encryption key...      (expected/benign)
  1 !> ResolvePath(SOUNDS/KART.HWL) failed - device not found                 (expected: override probe)
  1 !> ResolvePath(BIGFILE.BIG) failed - device not found                     (expected: override probe)
  1 !> File not found: \Device\Harddisk0\Partition1\xam.xex                   (expected: Xenia synthesises xam)
  1 !> File not found: \Device\Harddisk0\Partition1\$flash_xam.xex            (expected)
```

So the **only** real emulator-side errors in this run are the GPU draw failures. They are *not* fatal and are not
surfaced as a crash — the port keeps running.

The "unimplemented kernel function" warning does **not** appear for this title: `xenia.log` shows
`xam - 8 imports … Known: 100% … Implemented: 100%` and `xboxkrnl - 116 imports … Known: 100% …
Implemented: 98% (114 implemented, 2 unimplemented)` — the two are `__C_specific_handler` and `RtlUnwind`, both
flagged `!!` in the import table. The port's C89 `ExceptionHandling=false` build never calls them.

### 6.2 What a real guest crash would look like

From the binary's format strings and upstream `Emulator::ExceptionCallback` (`src/xenia/emulator.cc:1375-1465`), a
guest exception **inside JITed code** produces an `E`-level `==== CRASH DUMP ====` block with:
`Thread ID (Host: 0x… / Guest: 0x…)`, `Thread Handle: 0x…`, `PC: 0x…` (guest address), and either
`Access Violation: read|write at 0x…` or `Illegal Instruction`, then **all 32 GPRs, all 32 FPRs (hex + double + float)
and all 128 VMX vectors**, followed by the GUI box `Uh-oh!` / *"The guest has crashed. Xenia has now paused itself."*,
then the faulting guest thread is **suspended** (host process stays alive). Host-side exceptions produce a separate
`Exception encountered!` / `Exception address:` / `ExceptionCode: 0x…` block plus `Faulting thread name:`,
`Last Win32 Error`, `Last NTSTATUS`, `Last errno value`.

**This run produced none of those.** There is no `==== CRASH DUMP ====`, no `The guest has crashed.`, no `STOP:`
in either log. The run's failure mode is a **silent wedge**, which is exactly why it is expensive to localize.

### 6.3 The GPU failure lines are the port's own draws (with numbers)

`Surface pitch 9552` and `9328` are neither the port's VRAM render target (1024-wide, `D3DFMT_LIN_G8R8` —
`platform/xbox360/native_xbox360_video.c:973`) nor the 1280×720 backbuffer (`:564-571`). Arithmetic:
`9552 − 8192 = 1360`, `9328 − 8192 = 1136`, `9552 − 9328 = 224`, `9552/16 = 597`, `9552/32 = 298.5`
(i.e. **not** a multiple of the 32-texel pitch alignment `GPU_TEXTURE_TEXEL_PITCH_ALIGNMENT`), and
`1024 × 9.328125 = 9552`. The three distinct pitches (9552 / 9328 / 1024) look like **pitch fields read out of the
wrong place** in a fetch constant (garbage-derived), consistent with the port's known uncooked-data frontier.
First occurrence is `xenia.log:3921` (right after `Make 00001000 -> 00001000 (0b) coherent, action = N/A` and a
`VdGetCurrentDisplayInformation` call), and it recurs per frame (`:85753`, `:85824`, `:96546`, …) — so it starts
during the intro pages, i.e. it is a **present/offscreen-path draw**, not level geometry.
The `G>` lines confirm the port's own resources are known to Xenia:
`Created linear 1024x512x1 2D k_8_8 texture … base at 0x1EDB4000 (pitch 1024, size 0x00100000)` (the VRAM texture) and
`Created tiled 1280x720x1 2D k_8_8_8_8 texture … base at 0x1F6F8000 (pitch 1280, size 0x00398000)` (the backbuffer).

### 6.4 What the wedge looks like in the logs (state as of the 10:12 run)

`cache/ctr360.log` (42,366 lines): the last non-pump line is `line 41959: [trace] walk#23   prim code=00 len=2 primLength=3`,
and lines 41960-42366 are **only** the audio pump heartbeat
(`[CTR Audio] pump callbacks=85200 queuedBytes=129419329`). In `xenia.log` the guest's last lines are the same walk
trace at `:216604`, after which the log is only `NtWriteFile` + `RtlInitAnsiString` pairs from the audio thread.
Reading the ordering:

- `present ok 606` at `ctr360.log:11674` and `frame 600 presented` at `:11558` (heartbeat = every 300 present calls,
  `native_xbox360_video.c:2673`) — the **present counter is at 606**.
- The game's own `frameCounter` is at **13**: `q4 f=13` (`:39880`) → `rf11..rf15 f=13` → `lg1/lg2w/w1 bsp=00000000/
  lg4 leafs=0` → `rf16/rf19 f=13` → `DrawOTag#23 enter p=826ED938` (`:39892`).
- Inside that walk the OT is traversed packet-by-packet (`walk#23 pkt=… len=0 code=… tag=…`), then a real primitive:
  `pkt=826E0174 len=5 code=00 tag=05edec28` → `prim code=00 len=5 primLength=3` → two tagless commands
  (`cmd=e2000000`, `cmd=e100060a`) → later `pkt=826CFD0C len=2 code=00 tag=02eca7e4` → `prim code=00 len=2
  primLength=3` — **and then nothing**.

Interpretation supported by the logs alone: two different "frame" counters coexist in the port's telemetry
(**present-call counter 606 vs game `frameCounter` 13**) and they must not be conflated when reading a run; and the
current stall is inside `DrawOTag` for game frame 13, in the **primitive/split path** after the walker parsed a
`code=00` primitive — i.e. the F1 (mesh/vertex) frontier from `RESEARCH.md §7`, not the animtex class (which is gone:
`grep -c 'cy2|nf=4096' cache/ctr360.log` → 0).

Also of note: `w> BaseHeap::AllocFixed attempting commit on unreserved page` (3×, `xenia.log:380-382`) is the port's
own arena setup — the same path `DmSetMemory`/guest memory allocation goes through — and is benign here but worth
knowing about.

### 6.5 Reading rule for a wedge (derived from this run)

A guest wedge under Xenia produces **no** `!>`/crash line at all: the guest's own log stops, `xenia.log` continues only
with audio-thread kernel calls, and `run_xenia.sh`'s CPU sample (0.1-0.4 s per 3-5 s wall) is the only emulator-side
signal. Therefore **fault visibility must come from the guest** — which is the gap §4.4 items 1/5/7 and §5.3's
`--debug` address.

---

## 7. Does this Xenia build have a GDB stub or remote-debug capability?

**No.** Evidence:

- **String scan of `xenia_canary.exe`** (17,124,864 bytes; 52,151 ASCII strings extracted): `gdb` → 0 hits,
  `GDB` → 0, `gdbserver` → 0, `qSupported` → 0, `RSP` → 0, `remote` → 0 (case-sensitive; `Remote` matches only
  *Nintendo Wii Remote* / *RemotelyAnywhere Screen Capture* input-device names), `DEBUGGER_PORT` → 0, `2da` → 0
  (no hex-literal form either), `tcp` → only `ictcp`/`tcplx_mask` (FFmpeg/HID), `listen` → only
  `NetDll_listen` and `Debugger demanded a listener but no handler was registered.`
- What *does* exist is Xenia's **own** ImGui guest debugger (§5.3), gated behind `--debug`, driven by the menu/hotkeys
  and by `[CPU] break_on_*` cvars — a self-contained debugger, not a protocol server.
- Upstream confirms the feature request is still open: `xenia-canary/xenia-canary` issue **#979**
  *"[Feature Request] Add GDB for debugging Xbox 360 games using IDA with support for PowerPC registers"* —
  *"I would like to request to add a GDB feature that allows Xenia Canary to be connected/attached by IDA for remotely
  GDB debugging Xbox 360 games… Because Cheat Engine and IDA's regular debugger attached to Xenia Canary's process only
  supports x64 registers."* There is also issue #116 (memory searcher + debugger in-emulator).
- The nearest thing to a remote protocol is **`xbdm` itself** (the guest-side debug monitor, `DEBUGGER_PORT 0x2da` in
  `xbdm.h:206`), but under Xenia the transport half is absent and the interesting `Dm*` calls are stubs/absent (§4.3).
- Practical alternatives that do exist for this port:
  1. **Host debugger via `Ctrl+Pause/Break`** (`&Break into Host Debugger`) or `[CPU] break_on_instruction` /
     `break_on_debugbreak` — lands in a host debugger (WinDbg/x64dbg) at a **host** PC, with Xenia's
     `[General] debug = true` retaining enough info that Xenia's own UI can map it back to a guest function.
  2. **Xenia's built-in guest debugger** with `--debug` (§5.3): code/data/GPU/kernel breakpoints, per-thread registers,
     memory viewer, kernel-call log.
  3. **The port's own log + `DbgPrint`** (§4.4) for telemetry, which is what the project already relies on.

---

## 8. Platform constraints that matter for the port (from XDK headers + the backend)

### 8.1 GPU / D3D9 / Xenon

- `include/xbox/d3d9gpu.h:35,39,43` — `GPU_EDRAM_SIZE = 10*1024*1024` (10 MB EDRAM), `GPU_MEMORY_SIZE = 512*1024*1024`
  (512 MB unified), `GPU_CLOCK_SPEED = 500 MHz`.
- `d3d9gpu.h:249` — `GPU_MAX_TEXTURE_DIMENSION 8192` (2D max 8K×8K); `:257` `GPU_MAX_TEXTURE_DEPTH 1024`;
  `:262` `GPU_TEXTURE_ALIGNMENT 4096`; `:265` `GPU_TEXTURE_TEXEL_PITCH_ALIGNMENT 32`.
  `d3d9caps.h:58,61` — `D3DMAXTEXTUREDIMENSION = GPU_MAX_TEXTURE_DIMENSION`,
  `D3DMAXSURFACEOFFSET = GPU_EDRAM_SIZE` ("there's 10MB of EDRAM").
  → **This is the exact 8192 that the port's `Surface pitch 9552/9328` failures trip over** (§6.3).
- `d3d9gpu.h:178-192` — shader budget: `GPU_INSTRUCTIONS 4096`, `GPU_ALU_CONSTANTS 512`,
  `GPU_BOOLEAN_CONSTANTS 256`, `GPU_INTEGER_CONSTANTS 32`, `GPU_FETCH_CONSTANTS 32`,
  `GPU_VERTEX_FETCH_CONSTANTS 96`, `GPU_D3D_VERTEX_CONSTANTF_COUNT 256`,
  `GPU_D3D_VERTEX_CONSTANTI_COUNT 16`, `GPU_D3D_VERTEX_CONSTANTB_COUNT 128`.
- `d3d9.h:2308-2310` — `D3DDevice_BeginScene`/`EndScene` are **empty inline no-ops**
  (`D3DINLINE void WINAPI D3DDevice_BeginScene(...) { }`), and `D3DDevice_Clear(..., BOOL EDRAMClear)` takes an extra
  `EDRAMClear` argument the PC API does not; the `IDirect3DDevice9_Clear` wrapper passes `FALSE`
  (`d3d9.h:3536`). The port already wraps these (`Platform_BeginScene/EndScene` in
  `platform/xbox360/native_xbox360_platform.c`).
- `d3d9.h:3524-3536` — every `IDirect3DDevice9_*` call is a **C inline wrapper that takes the device explicitly** and
  returns an HRESULT synthesised from the underlying `D3DDevice_*` call (which itself returns the object or NULL);
  `CreateTexture`/`CreateSurface`-style calls have no constant-table reflection and no implicit device.
  The port's header comment records exactly this (`native_xbox360_video.c:26-39`).
- Port-side constraints already encoded in the backend (same header comment): *"No texture stage states and no
  fixed-function lighting exist on Xenos; everything is shader driven"*, *"The shader compiler rejects `discard`
  (use `clip()`), dynamic integer math, and integer uniform registers"*, *"GPU→CPU VRAM readback uses the Xbox 360
  `Resolve` API instead of `glReadPixels`; resolve rects are 8×8 aligned"*, *"the 360 backbuffer row 0 is the visual
  top row"* (GL→D3D9 orientation), and *"the 360 D3D9 API is C"*.
- The port's resources, for reference: 1280×720 `D3DFMT_A8R8G8B8` backbuffer + `D3DFMT_D24S8` depth
  (`native_xbox360_video.c:564-571`), offscreen RT `D3DFMT_A8R8G8B8` + `D24S8` (`:735,750`), 1×1 white texture and a
  LUT texture in `D3DFMT_LIN_A8R8G8B8` (`:843,856`), and the **1024×512 `D3DFMT_LIN_G8R8` VRAM texture** (render
  target at `:973`, plus a `D3DUSAGE_CPU_CACHED_MEMORY` readback texture at `:985`). `native_xbox360_video.c` is
  2,687 lines with 11 shader compile sites; 9 shaders verified against the XDK `fxc` in `tools/ctr360/shader_probes/`.

### 8.2 Memory

- 512 MB unified, 10 MB EDRAM (§8.1). Allocation API: `xbox.h:577-614` `XPhysicalAlloc`/`XPhysicalAllocEx`/`XPhysicalFree`,
  with `XALLOC_MEMTYPE_HEAP 0` / `XALLOC_MEMTYPE_PHYSICAL 1` (`:656-657`), write-combine/no-cache protection flags
  (`:659-662`), and a full alignment ladder `XALLOC_ALIGNMENT_4 … XALLOC_PHYSICAL_ALIGNMENT_32K` (`:664-683`).
- GPU↔CPU address windows: `d3d9gpu.h:57-99` — GPU physical `0xA0000000-0xBFFFFFFF` (64 KB pages) and
  `0xC0000000-0xDFFFFFFF` (16 MB pages), `GPU_TAIL_WRITEBACK_RANGE_*` at `0x7F000000`/`0xC0000000` (1 MB),
  `GPU_XPS_LOCKED_L2_RANGE_*` (`0x7F100000`/`0xC0100000`, ~127 MB) — i.e. **writable textures/surfaces must live in a
  GPU-visible window and be aligned/paged accordingly**; that is what `xgraphics.h`'s tiling/size helpers exist for.
- The port's own memory model: `platform/native_memory.c:17-31` —
  `CTR_NATIVE_MEMPACK_BUFFER_SIZE 0x200000` (2 MB), `START_OFFSET 0xba9f0`, `SIZE 0x144e10`, a compile-time assert that
  they tile exactly, a 2 MB static `s_mempackMemory[]`, and a `CTR_SCRATCHPAD_SIZE 0x400` (1 KB) scratchpad
  (`include/ctr_scratchpad.h:7`) that must match `sizeof(struct PushBufferSetMatrixVPScratch)`.
  `main_xbox360.c:115` calls `Platform_InitScratchpad()` before `CTR_Main()`.
- Xenia-side memory policy that matters: `protect_zero = true` (config `:433`) — the zero page is unmapped, which is
  why a probe that dereferences NULL wedges the guest (documented in `HANDOFF.md` "Probes must not deref pointers the
  code only compares to NULL"); `writable_executable_memory = true` (`:436`); `scribble_heap = false` (`:434`).

### 8.3 Threads and timing

- `XSetThreadProcessor(HANDLE, DWORD dwHardwareThread)` — `xbox.h:479`; CHM: *"dwHardwareThread … range 0 through
  MAXIMUM_PROCESSORS − 1. Each of the three CPU cores has two hardware threads"* with the mapping
  **0/1→core 0, 2/3→core 1, 4/5→core 2**; a new thread inherits the creator's hardware thread.
  The port uses this exactly once: `platform/xbox360/native_xbox360_audio_out.c:144` → `XSetThreadProcessor(stream->thread, 4)`
  ("keep it on a hardware thread [the render thread does not use]"). Thread creation: `CreateThread` at `:133`.
- Timing: Xenon QPC = **50 MHz** (`emulator.cc:211`: *"360 uses a 50MHz clock"*, `Clock::set_guest_tick_frequency(50000000)`).
  The port measures with `X360_GetCounter()`/`Native_CounterToMs` (`native_xbox360_platform.c:234-268`).
- Xenia emulates 6 guest threads for this title (`xenia.log:401-410, 770-773, 1143-1151`: XThread01000010/14/18/1C,
  XThread01000020, XThreadF8000008, XThreadF8000014/18), each with a 128 KB stack window
  (`Stack: 70010000-70030000` etc.), plus a 262,144-byte default guest stack from the XEX header.
- Relevant emulator-side thread options: `[Kernel] ignore_thread_affinities = true` (Xenia ignores the guest's
  affinities — so `XSetThreadProcessor` placement is *not* what decides host scheduling under Xenia),
  `ignore_thread_priorities = false`, `[x64] enable_host_guest_stack_synchronization = true`,
  `max_stackpoints = 65536`, `[General] priority_class = 0`, `[Win32] win32_mmcss = true`.
- Audio thread contract (port design): the sink still **pulls** PCM on a real thread
  (`X360_AUDIO_PULL_INTERVAL_MS 3`, `X360_AUDIO_PULL_FRAMES 512`, `audio_out.c:28-29,49-60`) because the emulated
  SPU/XA clock only advances when the device pulls — this is the documented "a replaced subsystem must keep its clock"
  rule, and it is why the pump heartbeat is the only reliable liveness signal in a wedged run (`§6.4`).

---

## 9. What this inventory implies for the next debugging cycle (no changes made)

Ranked, each with the exact facility it uses:

1. **Launch Xenia with `--debug`.** Unlocks the guest debugger (`Pause/Break` → *Break and Show Guest Debugger*;
   `##breakpoints_pane` code/data/GPU/kernel breakpoints; `##threads_pane`; `##registers_pane` guest+host;
   `##memory_pane`). One-line change in `tools/ctr360/run_xenia.sh` (currently launches with no flags). This is the
   single largest capability that is present in the binary and unused.
2. **Add a guest-side fault reporter that cannot be missed.** Under Xenia a wedge is silent (§6.5), so the port needs
   its own "I am stuck here" line. Cheapest options, in order of evidence:
   `DbgPrint(...)` (implemented by Xenia, `xboxkrnl_strings.cc:643`) → `xenia.log` with a distinct `(DbgPrint)` tag;
   `KeBugCheckEx(code, a,b,c,d)` (prints `*** STOP:` and suspends the faulting thread) for invariant violations;
   `OutputDebugStringA` is already mirrored on every line (`native_xbox360_log.c:31`).
   **Do not** build on `DmCaptureStackBackTrace` (returns success + zeroed buffer under Xenia) or
   `RtlCaptureStackBackTrace` (no implementation under Xenia) — both are console-only.
3. **Use `[CPU] break_on_instruction = <guest addr>`** with the `default.xdb` already staged next to the XEX
   (`build-360/xex/dist/default.xdb`, 12 MB, Sep 19 10:07) to stop exactly at the frame-13 primitive path.
   `debug_symbol_loader = true` / `load_module_map` are the symbol-quality knobs if the guest debugger shows raw addresses.
4. **Name the wedged function from the host side.** `[x64] instrument_call_times = true` (per-function guest timing)
   plus `[GPU.Debug] trace_gpu_stream = true` + `trace_dump_path` for the PM4 stream — the latter is the direct
   instrument for the `Surface pitch 9552/9328` failures (§6.3), which are the port's own draws and will matter as soon
   as real geometry is submitted.
5. **Keep the two counters separate in every future log line.** The port's present-call counter (606) and the game's
   `frameCounter` (13) diverge by ~46× during the intro; a heartbeat or probe that prints only "frame N" is ambiguous.
   This is a report/reading convention change, not a code requirement.
6. **Console-only facilities are real and should not be written off.** `DmSetBreakpoint`/`DmSetDataBreakpoint`/
   `DmStop`/`DmGo`/`DmGetThreadContext`, `DmCaptureStackBackTrace`, `DmCrashDump` and the `DmRegisterCommandProcessor`
   remote-console pattern (`DebugChannel`/`CallStackRecording` samples, §3.4) all work on an RGH/JTAG devkit, which is
   the port's stated second target (`HANDOFF.md §1`). A `#ifdef`-able console debug module built from the two samples
   would cost nothing under Xenia (all stubbed to success or absent) and pay off on hardware.

---

## 10. What could NOT be determined

- **Whether the `--debug` flag path in this exact binary yields a working debugger window** — I verified the strings,
  the gate message, and the pane IDs, but did not launch Xenia (task constraint) to confirm the UI appears and that
  the `.xdb` symbols resolve to ctr360 function names.
- **The XEX's TLS slot count**: `imagexex /DUMP` prints `40 number of TLS slots` while Xenia's own header dump prints
  `XEX_HEADER_TLS_INFO: Slot Count: 64` (`xenia.log:462`). I could not resolve which is authoritative (different
  fields/versions); it does not affect the port today (TLS Raw Data Address `00000000`, Data Size `0`).
- **Whether the 9552/9328 pitches come from a specific port call site**: I traced the *timing* (first occurrence
  `xenia.log:3921`, during the intro/present phase, recurring per frame) and the arithmetic
  (`1024 × 9.328125 = 9552`; `9552` is not a multiple of 32), but the identity of the offending fetch constant /
  `CreateTexture`/`Resolve` call was not established — that needs the `trace_gpu_stream` run or a read of
  `native_xbox360_video.c`'s present/offscreen bind path.
- **The exact identity of the frame-13 wedge**: the log localizes it to inside `DrawOTag#23` after
  `prim code=00 len=2 primLength=3` (`cache/ctr360.log:41959`), i.e. the primitive/split path, but whether the guest
  is spinning, blocked, or walking bad memory cannot be decided from the log alone (no fault line, no crash dump;
  the audio thread keeps running). `HANDOFF.md`/`RESEARCH.md` call this the F1 mesh/vertex frontier; this inventory
  confirms it and adds no root cause.
- **Whether any XDK-shipped documentation describes a *guest-callable* `OutputDebugString`-to-host channel beyond
  `DbgPrint`** — the CHM's `DbgPrint` page was not extractable by exact name from the archive listing I pulled
  (`7z e` reported the file missing); I read the Xenia implementation instead of the Microsoft page.
- **The `bin/xbox` payload's debug value**: `bin/xbox` contains only 10 entries (no `xbdm.xex` binary, no debug
  console) — the target-side debug monitor appears to live on the console/`xbdm.dll` side, so I could not inventory a
  local `xbdm.xex` image.
- **`xbperfview.exe` / other `xb*` tools' full option sets**: invoking `xbperfview /?` hung (it opened a GUI and had to
  be killed by the 180 s tool timeout). Only `xbmemdump /?` printed usage
  (`/X target` — IP or console name, `/?"`). No Xenia/emulator process was started; the hang was this one GUI tool and
  it was terminated by the harness, not by me.
- **XDK release notes / known issues**: `relnotes.htm` is an empty stub pointing at the dead GDN site; no local copy.
- **Whether `xbdm.lib`'s `xam.xex`-side reference (`xapilib.lib` strings include `xbdm.xex`) means a title linking
  `xbdm.lib` also gains an `xbdm.xex` import**: the built `default.xex` imports only `xam.xex` + `xboxkrnl.exe`
  (`imagexex /DUMP`, §2), so today it does not — but I did not test whether *calling* a `Dm*` function changes the
  import set (that would need a build, which was out of scope).
