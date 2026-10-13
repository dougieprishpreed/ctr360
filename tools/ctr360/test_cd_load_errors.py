"""Actual native CD facade and LOAD_ReadFile_ex retry/ownership failure paths."""
from pathlib import Path
import re
import subprocess
root=Path(__file__).resolve().parents[2]
out=root/'build-360/results/cd-load-error-contract'
out.mkdir(parents=True,exist_ok=True)

def function(path,name):
    s=(root/path).read_text();m=re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{',s,re.M);assert m,name
    start=s.index('{',m.start());end=start+1;depth=1
    while depth:
        depth+=(s[end]=='{')-(s[end]=='}');end+=1
    return s[m.start():end]+'\n'

c=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <setjmp.h>
typedef uint8_t u8;typedef uint32_t u32;typedef int32_t s32;
typedef struct {u8 bytes[4];} CdlLOC;
typedef void (*CdlCB)(u8,u8*);
enum {CdlSetloc=2,CdlSetmode=14,CdlComplete=2,CdlDiskError=5,CdlModeSpeed=128};
enum {NATIVE_CD_FILE_NONE,NATIVE_CD_FILE_HOST,NATIVE_CD_FILE_DISC};
#define NATIVE_CD_SECTOR_SIZE 2048
#define internal static
#define CTR_NATIVE 1
#define LOAD_CD_DATA_SECTOR_ROUND_MASK 2047
#define LOAD_CD_DATA_SECTOR_SHIFT 11
#define LT_MEMPACK 256
#define LT_SETADDR 1
struct NativeDiscImageFile {u32 lba,size;};
struct NativeCDOpenFile {int source;FILE*hostFile;struct NativeDiscImageFile discFile;};
static struct NativeCDOpenFile s_nativeCdFiles[8];
static int s_nativeCdFileCount=1,s_nativeCdCurrentFile=-1,s_nativeCdCurrentSector,s_nativeCdReadError,boolDecodeXaDuringVsyncCallback;
static CdlCB s_nativeCdReadCallback;
static int failedReads,readCalls,callbacks,errors,allocations,pops,flushes,exitStatus;
static jmp_buf failureJump;
static size_t injectedRead(void*dst,size_t size,size_t count,FILE*f){
 readCalls++;
 if(failedReads>0){failedReads--;return fread(dst,size,count>64?64:count,f);}
 return fread(dst,size,count,f);
}
#define fread injectedRead
static int NativeDiscImage_ReadDataSectors(struct NativeDiscImageFile*f,u32 sector,u32 count,void*dst){return 0;}
static void NativeCD_SetLastCom(int com){}
static void Platform_LogError(const char*fmt,...){}
static void Platform_LogFlush(void){flushes++;}
static void fixtureExit(int status){exitStatus=status;longjmp(failureJump,1);}
#define Platform_Exit fixtureExit
struct BigEntry {int offset,size;};
struct BigHeader {int numEntry,cdpos;struct BigEntry entries[1];};
#define BIG_GETENTRY(x) ((x)->entries)
struct Mempack {void*firstFreeByte;void*lastFreeByte;s32 sizeOfPrevAllocation;};
static u8 arena[8192];static struct Mempack pool;
#define MEMPACK_ACTIVE (&pool)
struct LoadQueueSlot {u32 flags;void*ptrDestination;u32 size_UNUSED;};
static struct {struct LoadQueueSlot currSlot;} data;
static struct {struct BigHeader*ptrBigfile1;void(*callbackCdReadSuccess)(struct LoadQueueSlot*);int queueRetry;} state,*sdata=&state;
static void CDSYS_SetMode_StreamData(void){}
static int MEMPACK_GetFreeBytes(void){return (u8*)pool.lastFreeByte-(u8*)pool.firstFreeByte;}
static void*MEMPACK_AllocMem(int size,const char*name){assert(size<=MEMPACK_GetFreeBytes());void*p=pool.firstFreeByte;pool.firstFreeByte=(u8*)p+size;pool.sizeOfPrevAllocation=size;allocations++;return p;}
static void*MEMPACK_ReallocMem(int size){pool.firstFreeByte=(u8*)pool.firstFreeByte-pool.sizeOfPrevAllocation+size;pool.sizeOfPrevAllocation=size;return pool.firstFreeByte;}
static void MEMPACK_PopState(void){pops++;}
static void successCallback(struct LoadQueueSlot*slot){assert(slot->ptrDestination && slot->size_UNUSED==3000);callbacks++;}
static void cdCallback(u8 status,u8*unused){if(status==CdlComplete)callbacks++;else{assert(status==CdlDiskError);errors++;}}
'''
for n in ('NativeCD_PosToInt','NativeCD_IntToPos','NativeCD_SetLoc','NativeCD_ReadSectors','CdReadCallback','CdIntToPos','CdControl','CdRead','CdReadSync'):
    c+=function('platform/native_cd.c',n)
for n in ('LOAD_NativeReadFailure','LOAD_ReadFileASyncCallback','LOAD_ReadFile_ex'):
    c+=function('game/LOAD/LOAD_File.c',n)
c+=r'''
static void reset(void){
 memset(arena,0x7a,sizeof arena);pool.firstFreeByte=arena+16;pool.lastFreeByte=arena+sizeof arena;pool.sizeOfPrevAllocation=12;
 memset(&data,0,sizeof data);callbacks=errors=readCalls=allocations=pops=flushes=exitStatus=0;CdReadCallback(NULL);
}
int main(void){
 FILE*f=tmpfile();assert(f);for(int i=0;i<4096;i++)assert(fputc(i&255,f)!=EOF);fflush(f);
 s_nativeCdFiles[0].source=NATIVE_CD_FILE_HOST;s_nativeCdFiles[0].hostFile=f;
 CdlLOC loc;u32 buffer[1024];CdIntToPos(0,&loc);CdReadCallback(cdCallback);
 assert(CdControl(CdlSetloc,(u8*)&loc,NULL));assert(CdRead(2,buffer,0)&&CdReadSync(0,NULL)==0&&callbacks==1);
 CdIntToPos(1<<24,&loc);assert(!CdControl(CdlSetloc,(u8*)&loc,NULL));assert(!CdRead(1,buffer,0)&&CdReadSync(0,NULL)==-1&&errors==1);
 assert(!CdControl(CdlSetloc,NULL,NULL));
 CdIntToPos(1,&loc);assert(CdControl(CdlSetloc,(u8*)&loc,NULL));assert(!CdRead(2,buffer,0)&&errors==2);
 assert(!CdRead(-1,buffer,0)&&errors==3);assert(!CdRead(1,NULL,0)&&errors==4);
 assert(CdRead(0,NULL,0));
 struct BigHeader big={1,0,{{0,3000}}};u32 size=0;sdata->ptrBigfile1=&big;
 reset();failedReads=1;
 void*dst=LOAD_ReadFile_ex(NULL,0,0,NULL,&size,successCallback);
 assert(dst==arena+16&&size==3000&&callbacks==1&&readCalls==2&&allocations==1&&!pops);
 assert(pool.firstFreeByte==arena+3016 && pool.sizeOfPrevAllocation==3000);
 for(int i=0;i<3000;i++)assert(((u8*)dst)[i]==(i&255));
 reset();failedReads=99;
 if(!setjmp(failureJump)){LOAD_ReadFile_ex(&big,0,0,NULL,&size,successCallback);assert(0);}
 assert(exitStatus==EXIT_FAILURE&&flushes==1&&readCalls==3&&!callbacks&&!pops);
 assert(pool.firstFreeByte==arena+16&&pool.sizeOfPrevAllocation==12&&size==0&&data.currSlot.ptrDestination==NULL);
 reset();failedReads=0;pool.lastFreeByte=arena+1024;
 if(!setjmp(failureJump)){LOAD_ReadFile_ex(&big,0,0,NULL,&size,successCallback);assert(0);}
 assert(exitStatus==EXIT_FAILURE&&flushes==1&&!readCalls&&!allocations&&!callbacks);
 reset();
 if(!setjmp(failureJump)){LOAD_ReadFile_ex(&big,0,1,NULL,&size,successCallback);assert(0);}
 assert(exitStatus==EXIT_FAILURE&&!readCalls&&!callbacks);
 reset();failedReads=1;dst=LOAD_ReadFile_ex(&big,0,0,buffer,&size,NULL);
 assert(dst==buffer&&!allocations&&readCalls==2&&!callbacks);
 fclose(f);
 puts("PASS actual CD/load path: SetLoc/short/invalid reads, status/error callbacks, transient retry retains allocation, 3-attempt permanent failure rolls back and stops before relocation, allocation/index failures, caller-owned buffer");
}
'''
(out/'fixture.c').write_text(c)
subprocess.run(['clang','-O2',str(out/'fixture.c'),'-o',str(out/'fixture.exe')],check=True)
subprocess.run([str(out/'fixture.exe')],check=True)
