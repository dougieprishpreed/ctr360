"""Fault injection against the actual xSDK write-through save adapter."""
import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--xsdk',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[2];a.out.mkdir(parents=True,exist_ok=True)
c=r"""
#include <assert.h>
#include <string.h>
#include <errno.h>
#include "platform/xsdk/native_xsdk_file.c"
static int mode,closes,writes;static unsigned options;static unsigned char stored[8];
int xsdk_path_resolve(int fd,const char *path,char out[XSDK_PATH_BYTES]) { (void)fd;if(mode==1)return EINVAL;strcpy(out,path);return 0; }
void xsdk_path_attributes(const char *path,ANSI_STRING *name,OBJECT_ATTRIBUTES *attrs) { (void)path;(void)name;(void)attrs; }
int xsdk_file_errno(NTSTATUS status) { (void)status;return EIO; }
NTSTATUS NtCreateFile(HANDLE *file,uint32_t access,const OBJECT_ATTRIBUTES *attrs,IO_STATUS_BLOCK *io,const uint64_t *size,uint32_t attributes,uint32_t share,uint32_t disposition,uint32_t flags) {
 (void)access;(void)attrs;(void)io;(void)size;(void)attributes;(void)share;
 assert(disposition==FILE_OVERWRITE_IF);options=flags;if(mode==2)return -1;*file=7;return 0;
}
NTSTATUS NtWriteFile(HANDLE file,HANDLE event,void *apc,void *context,IO_STATUS_BLOCK *io,const void *data,uint32_t size,const uint64_t *offset) {
 (void)event;(void)apc;(void)context;assert(file==7);assert(*offset+size<=sizeof(stored));writes++;
 if(mode==3)return -1;memcpy(stored+*offset,data,size);io->information=size-(mode==4);return 0;
}
NTSTATUS NtClose(HANDLE file) { assert(file==7);closes++;return mode==5?-1:0; }
int main(void) {
 const unsigned char header[]={1,2},data[]={3,4,5,6};
 for(mode=0;mode<=5;mode++) {
  closes=writes=0;memset(stored,0,sizeof(stored));
  int result=CtrXsdkWriteThrough("game:/memcards/test.tmp",header,2,data,4);
  assert((result==0)==(mode==0));
  assert(closes==(mode>=2 && mode!=2 || mode==0));
  if(mode==0){assert(options&2);assert(writes==2);assert(!memcmp(stored,"\1\2\3\4\5\6",6));}
 }
 return 0;
}
"""
source=a.out/'save.c';source.write_text(c);exe=a.out/'save-test'
subprocess.run(['cc','-std=gnu17','-I'+str(root),'-I'+str(a.xsdk/'include'),'-I'+str(a.xsdk/'src'),str(source),'-o',str(exe)],check=True)
subprocess.run([str(exe.resolve())],check=True)
print('PASS: write-through flag, ordered header/data, bad path/open, write failure/short write, close failure')
