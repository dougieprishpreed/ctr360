"""Exercise the real Win32/XDK card file path with isolated temporary saves.

Requires Windows and clang. Uses separate writer/reader processes, then tests
failed writes/replacements, CRC rejection, slot isolation and ghost enumeration.
Never opens or removes the player's staged memcards directory.
"""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--xbox-paths", action="store_true", help="compile the real Xbox backslash path policy")
args = parser.parse_args()
OUT = ROOT / ("build-360/results/20261011-memcard-xbox-path-contract" if args.xbox_paths
              else "build-360/results/20261011-memcard-contract")
OUT.mkdir(exist_ok=True)

PRELUDE = r'''
#include <assert.h>
#include <direct.h>
#include <stdio.h>
#include <string.h>
#include <macros.h>
#include <platform/native_win32.h>
#pragma comment(lib, "kernel32.lib")
enum {MC_RETURN_IOE=0,MC_RETURN_TIMEOUT=1,MC_RETURN_PENDING=7,MEMCARD_STATUS_SYNC_CHECKSUM=8};
static struct {int crc16_checkpoint_status,crc16_checkpoint_byteIndex,memcardStatusFlags;} state,*sdata=&state;
#include "platform/native_memcard.c"
'''

TESTS = r'''
static unsigned char icon[256], a[0x1680], b[0x1680], loaded[0x1680];
static void prepare(void) {
 int i; unsigned short header[2]={0xffee,0x1600};
 memset(icon,0,sizeof icon);icon[0]='S';icon[1]='C';icon[2]=0x11;icon[3]=2;
 for(i=0;i<sizeof a;i++){a[i]=(unsigned char)(i*13+7);b[i]=(unsigned char)(i*9+3);}
 memcpy(a,header,4);MEMCARD_ChecksumSave(a,sizeof a);MEMCARD_ChecksumSave(b,sizeof b);
}
static void verify(const char *name,const unsigned char *expected) {
 assert(NativeMemcard_ReadSaveData(name,loaded,sizeof loaded,256)==NATIVE_MEMCARD_OK);
 assert(memcmp(loaded,expected,sizeof loaded)==0);
 sdata->crc16_checkpoint_byteIndex=0;sdata->crc16_checkpoint_status=0;
 int r;do {r=MEMCARD_ChecksumLoad(loaded,sizeof loaded);}while(r==MC_RETURN_PENDING);
 assert(r==MC_RETURN_IOE);
}
int main(int argc,char **argv) {
 char path[1024],temporary[1024],name[64];HANDLE lock;FILE*f;
 assert(argc==3);prepare();assert(NativeMemcard_SetRoot(argv[2])==NATIVE_MEMCARD_OK);
 /* An absolute root continues to work after the launcher's CWD changes. */
 assert(_chdir("C:/") == 0);
 if(strcmp(argv[1],"write")==0) {
  assert(NativeMemcard_ReadSaveData("bu00:BASCUS-94426-SLOTS",loaded,sizeof loaded,256)==NATIVE_MEMCARD_NOT_FOUND);
  assert(NativeMemcard_WriteSaveData("bu00:BASCUS-94426-SLOTS",icon,sizeof icon,a,sizeof a)==NATIVE_MEMCARD_OK);
  assert(NativeMemcard_WriteSaveData("bu10:BASCUS-94426-SLOTS",icon,sizeof icon,b,sizeof b)==NATIVE_MEMCARD_OK);
  verify("bu00:BASCUS-94426-SLOTS",a);verify("bu10:BASCUS-94426-SLOTS",b);
 } else if(strcmp(argv[1],"read")==0) {
  verify("bu00:BASCUS-94426-SLOTS",a);verify("bu10:BASCUS-94426-SLOTS",b);
  assert(NativeMemcard_FileExists("bu00:BASCUS-94426-SLOTS"));
 } else {
  strcpy(path,NativeMemcard_PathFromDeviceName("bu00:BASCUS-94426-SLOTS",0));
  snprintf(temporary,sizeof temporary,"%s.tmp",path);
  /* A locked pending file must never truncate the last good save. */
  lock=CreateFileA(temporary,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
  assert(lock!=INVALID_HANDLE_VALUE);
  assert(NativeMemcard_WriteSaveData("bu00:BASCUS-94426-SLOTS",icon,256,b,sizeof b)==NATIVE_MEMCARD_OPEN_FAILED);
  verify("bu00:BASCUS-94426-SLOTS",a);CloseHandle(lock);DeleteFileA(temporary);
  /* A failed final rename also retains the previous save and cleans temp. */
  lock=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
  assert(lock!=INVALID_HANDLE_VALUE);
  assert(NativeMemcard_WriteSaveData("bu00:BASCUS-94426-SLOTS",icon,256,b,sizeof b)==NATIVE_MEMCARD_IO_ERROR);
  verify("bu00:BASCUS-94426-SLOTS",a);CloseHandle(lock);
  assert(GetFileAttributesA(temporary)==INVALID_FILE_ATTRIBUTES);
  assert(NativeMemcard_WriteSaveData("bu00:BASCUS-94426-SLOTS",icon,256,b,sizeof b)==NATIVE_MEMCARD_OK);
  verify("bu00:BASCUS-94426-SLOTS",b);
  assert(NativeMemcard_WriteSaveData("bu00:BASCUS-94426G000002",icon,256,a,sizeof a)==NATIVE_MEMCARD_OK);
  assert(NativeMemcard_WriteSaveData("bu00:BASCUS-94426G000001",icon,256,b,sizeof b)==NATIVE_MEMCARD_OK);
  strcpy(path,NativeMemcard_PathFromDeviceName("bu00:BASCUS-94426G000000.tmp",0));
  f=fopen(path,"wb");assert(f);fputs("interrupted",f);fclose(f);
  assert(NativeMemcard_FindFirstFile("bu00:BASCUS-94426G*",name,sizeof name));
  assert(strcmp(name,"BASCUS-94426G000001")==0);
  assert(NativeMemcard_FindNextFile(name,sizeof name));assert(strcmp(name,"BASCUS-94426G000002")==0);
  assert(!NativeMemcard_FindNextFile(name,sizeof name));
  assert(NativeMemcard_RemoveFile("bu00:BASCUS-94426G000001")==NATIVE_MEMCARD_OK);
  assert(!NativeMemcard_FileExists("bu00:BASCUS-94426G000001"));
  loaded[35]^=1;sdata->crc16_checkpoint_byteIndex=0;sdata->crc16_checkpoint_status=0;
  int r;do {r=MEMCARD_ChecksumLoad(loaded,sizeof loaded);}while(r==MC_RETURN_PENDING);assert(r==MC_RETURN_TIMEOUT);
  assert(NativeMemcard_ReadSaveData("bu00:BASCUS-94426G000000.tmp",loaded,sizeof loaded,256)==NATIVE_MEMCARD_IO_ERROR);
  assert(NativeMemcard_WriteSaveData("bu00:BASCUS-94426-SLOTS",icon,256,NULL,sizeof b)==NATIVE_MEMCARD_IO_ERROR);
  verify("bu00:BASCUS-94426-SLOTS",b);
 }
 puts("PASS");return 0;
}
'''

source = OUT / "test.c"
source.write_text(PRELUDE + (ROOT / "game/MEMCARD/MEMCARD_Checksum.c").read_text(encoding="utf-8").replace("#include <common.h>", "") + TESTS, encoding="utf-8")
exe = OUT / "test.exe"
subprocess.run(["clang", "--target=i686-pc-windows-msvc", "-O2", "-DCTR_NATIVE", "-D_CRT_SECURE_NO_WARNINGS",
                *(["-D_XBOX"] if args.xbox_paths else []),
                "-I" + str(ROOT), "-I" + str(ROOT / "include"), str(source), "-o", str(exe)], check=True)
results = []
with tempfile.TemporaryDirectory(prefix="card-", dir=OUT) as temporary:
    assert Path(temporary).resolve().is_relative_to(OUT.resolve())
    card = Path(temporary) / "memcards"
    for phase in ("write", "read", "failure-and-ghosts"):
        run = subprocess.run([str(exe), phase, str(card)], capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(f"{phase} exit={run.returncode}: {run.stdout} {run.stderr}")
        results.append({"phase": phase, "result": run.stdout.strip()})
(OUT / "result.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps(results))
