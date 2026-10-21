/* The pinned xSDK has synchronous file IO but no fsync. Save through a
 * write-through kernel handle, then let the caller atomically rename the
 * completed temporary file. Path helpers are from the pinned xSDK runtime.
 * FILE_WRITE_THROUGH is NT's public 0x2 create option (XboxDev/nxdk).
 */
#include <xsdk/kernel.h>
#include "path_private.h"
#include <fcntl.h>
#include <errno.h>
static int CtrXsdkWriteThrough(const char *path,const void *header,unsigned headerBytes,const void *data,unsigned bytes)
{
    char resolved[XSDK_PATH_BYTES];
    int error=xsdk_path_resolve(AT_FDCWD,path,resolved);
    if(error){errno=error;return -1;}
    ANSI_STRING name;OBJECT_ATTRIBUTES attrs;xsdk_path_attributes(resolved,&name,&attrs);
    IO_STATUS_BLOCK io;HANDLE file=0;
    NTSTATUS status=NtCreateFile(&file,GENERIC_WRITE|SYNCHRONIZE,&attrs,&io,NULL,FILE_ATTRIBUTE_NORMAL,FILE_SHARE_READ,
        FILE_OVERWRITE_IF,0x2u|FILE_SYNCHRONOUS_IO_NONALERT|FILE_NON_DIRECTORY_FILE);
    if(!NT_SUCCESS(status)){errno=xsdk_file_errno(status);return -1;}
    uint64_t offset=0;int result=0;
    const void *parts[]={header,data};unsigned lengths[]={headerBytes,bytes};
    for(unsigned i=0;i<2;i++){
        if(!lengths[i])continue;
        status=NtWriteFile(file,0,NULL,NULL,&io,parts[i],lengths[i],&offset);
        if(!NT_SUCCESS(status) || io.information!=lengths[i]){errno=NT_SUCCESS(status)?EIO:xsdk_file_errno(status);result=-1;break;}
        offset+=lengths[i];
    }
    status=NtClose(file);if(!NT_SUCCESS(status)){errno=xsdk_file_errno(status);result=-1;}return result;
}
