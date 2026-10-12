"""Exercise actual XA preparation/cache/playback and raw reads on a user image.

The fixture uses the real ISO reader and XNF metadata. Only platform output,
asset override resolution and the mixer lock are stubbed. It never opens an
audio device, changes the image, or modifies player saves.
"""
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
out = root / 'build-360/results/xa-transition-contract'
out.mkdir(parents=True, exist_ok=True)
stubs = out / 'include'
stubs.mkdir(exist_ok=True)
(stubs / 'macros.h').write_text('''
#pragma once
#include <stdint.h>
#include <stddef.h>
typedef uint8_t u8; typedef int8_t s8; typedef uint16_t u16; typedef int16_t s16;
typedef uint32_t u32; typedef int32_t s32; typedef uint64_t u64; typedef int64_t s64;
typedef int b32;
#define internal static
#define global_variable static
#define local_persist static
#define CTR_PRINTF_FORMAT(a,b)
''', encoding='utf-8')
audio = (root / 'platform/native_audio.c').read_text()
archive = root / 'build-360/results/20261012-hardware-ripper-roo'


def function(text, name):
    match = re.search(r'^.*\b' + name + r'\([^;]*?\)\s*\n\{', text, re.M)
    assert match, name
    start = text.index('{', match.start())
    depth, end = 1, start + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end] + '\n'


def structure(name):
    return re.search(r'(?:struct|enum) ' + name + r'\s*\{.*?\};', audio, re.S)[0] + '\n'


c = r'''
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <macros.h>
#include <platform/native_audio.h>
#include <platform/native_assets.h>
static int seeks,reads,locked;
static int counted_seek(FILE *f,long off,int whence) {
 assert(!locked);seeks++;return fseek(f,off,whence);
}
static size_t counted_read(void *p,size_t size,size_t n,FILE *f) {
 assert(!locked);reads++;return fread(p,size,n,f);
}
#define fseek counted_seek
#define fread counted_read
#include "platform/native_disc_image.c"
static const char *overridePath;
int NativeAssets_ResolvePath(const char *p,char *resolved,size_t size) {
 if(overridePath && strcmp(p,"fixture.XA")==0) {
  assert(strlen(overridePath)<size);strcpy(resolved,overridePath);return 1;
 }
 return 0;
}
int NativeAssets_ReadBytes(const char *p,int mode,struct NativeAssetsByteBuffer *b) {
 return NativeDiscImage_ReadFileBytes(p,mode==NATIVE_ASSET_READ_RAW_CD_SECTORS,&b->data,&b->size);
}
void Platform_Log(const char *fmt,...) {assert(!locked);}
static void NativeAudio_LockOutput(void) {assert(!locked);locked=1;}
static void NativeAudio_UnlockOutput(void) {assert(locked);locked=0;}
s32 NativeAudio_SpuInit(void) {return 1;}
'''
for line in audio.splitlines():
    if re.match(r'^#define (?:XA_|NATIVE_AUDIO_(?:XA_|CHANNELS\b|FP_SHIFT\b|SAMPLE_RATE\b))', line):
        c += line + '\n'
for name in ['NativeAudioXaDecodeState', 'NativeAudioXA', 'NativeAudioXaSourceKind',
             'NativeAudioXaSource', 'NativeAudioXaPreparedStream', 'NativeAudioXaCacheEntry',
             'NativeAudioXaStream', 'NativeAudioByteBuffer', 'NativeAudioXaTrackInfo']:
    c += structure(name)
c += '''
static struct {SpuCommonAttr commonAttr;struct NativeAudioXA xa;
 struct NativeAudioXaStream xaStream;} s_audio;
static struct NativeAudioXaCacheEntry s_xaCache[NATIVE_AUDIO_XA_CACHE_SLOTS];
static size_t s_xaCacheBytes;
'''
for name in ['NativeAudio_ReadLE32', 'NativeAudio_ReadLE16Signed', 'NativeAudio_ReadFileBytes',
             'NativeAudio_FreeByteBuffer', 'NativeAudio_BuildXAPath', 'NativeAudio_LookupXATrackInfo',
             'NativeAudio_GetXASectorLayout', 'NativeAudio_IsXAAudioSector', 'NativeAudio_XaSourceClose',
             'NativeAudio_XaSourceOpen', 'NativeAudio_XaSourceReadSector',
             'NativeAudio_XaPreparedStreamClose', 'NativeAudio_PrepareXAStream',
             'NativeAudio_FindCachedXA', 'NativeAudio_ClearXACache', 'NativeAudio_PrepareXATrack',
             'NativeAudio_PreloadXATrack', 'NativeAudio_CloseXANoLock',
             'NativeAudio_XaStreamStartNoLock', 'NativeAudio_PlayXATrack']:
    c += function(audio, name)
old_audio = archive / 'native_audio-before.c'
old_disc = archive / 'native_disc_image-before.c'
if old_audio.exists() and old_disc.exists():
    c += '#define HAVE_LEGACY 1\n'
    c += function(old_disc.read_text(), 'NativeDiscImage_ReadRawSectors').replace(
        'NativeDiscImage_ReadRawSectors', 'LegacyRawSectors')
    c += function(old_audio.read_text(), 'NativeAudio_XaSourceReadSector').replace(
        'NativeAudio_XaSourceReadSector', 'LegacySourceReadSector')
    c += function(old_audio.read_text(), 'NativeAudio_PrepareXAStream').replace(
        'NativeAudio_PrepareXAStream', 'LegacyPrepareXAStream').replace(
        'NativeAudio_XaSourceReadSector', 'LegacySourceReadSector')

c += r'''
static void same(const struct NativeAudioXaPreparedStream *a,const struct NativeAudioXaPreparedStream *b) {
 assert(a->sectorSize==b->sectorSize && a->sectorBase==b->sectorBase);
 assert(a->sectorCount==b->sectorCount && a->frameCount==b->frameCount);
 assert(a->numChannels==b->numChannels && a->sampleRate==b->sampleRate);
 assert(memcmp(a->sectors,b->sectors,(size_t)a->sectorCount*a->sectorSize)==0);
}
int main(int argc,char **argv) {
 struct NativeDiscImageFile file;
 struct NativeAudioXaTrackInfo info;
 struct NativeAudioXaSource src;
 struct NativeAudioXaPreparedStream victory,defeat,baseline,host;
 assert(argc==3 && NativeDiscImage_Init(argv[1]));
 assert(NativeDiscImage_FindFile("XA/MUSIC/S00.XA",&file));
 assert(NativeAudio_LookupXATrackInfo(0,4,&info));
 assert(info.channelFilter==4 && info.fileNumber==0 && info.numSectors==10337);
 /* Check packing across batch boundaries and preserve all 2336 payload bytes. */
 u8 a[37*2336],b[37*2336];
 seeks=reads=0;
 assert(NativeDiscImage_ReadRawSectors(&file,3,37,a));
 assert(seeks==1 && reads==3);
#ifdef HAVE_LEGACY
 assert(LegacyRawSectors(&file,3,37,b));assert(memcmp(a,b,sizeof a)==0);
#endif
 seeks=reads=0;
 assert(NativeDiscImage_ReadRawSectors(&file,NativeDiscImage_RawSectorCount(file.size),0,a));
 assert(!seeks && !reads);
 assert(!NativeDiscImage_ReadRawSectors(&file,NativeDiscImage_RawSectorCount(file.size),1,a));
 assert(!NativeDiscImage_ReadRawSectors(NULL,0,1,a));
 assert(!NativeDiscImage_ReadRawSectors(&file,0,1,NULL));
 assert(!NativeAudio_PrepareXATrack(-1,4,&baseline,0));
 assert(NativeAudio_XaSourceOpen("XA/MUSIC/S00.XA",&src));
 seeks=reads=0;
 assert(NativeAudio_PrepareXAStream(&src,4,10337,&victory));
 assert(seeks==647 && reads==647);
 assert(victory.sectorCount==1292 && victory.sectorSize==2336);
 printf("PASS victory: %d sectors, %zu bytes, %d seek/read pairs instead of 10337\n",
        victory.sectorCount,(size_t)victory.sectorCount*victory.sectorSize,seeks);
#ifdef HAVE_LEGACY
 seeks=reads=0;
 assert(LegacyPrepareXAStream(&src,4,10337,&baseline));
 assert(seeks==10337 && reads==10337);same(&victory,&baseline);
 NativeAudio_XaPreparedStreamClose(&baseline);
#endif
 NativeAudio_XaSourceClose(&src);
 assert(NativeAudio_PrepareXATrack(0,5,&defeat,0));
 assert(defeat.sectorCount==1292);
 assert(NativeAudio_PreloadXATrack(0,4));
 assert(NativeAudio_PreloadXATrack(0,5));
 assert(s_xaCacheBytes==6036224);
 seeks=reads=0;
 assert(NativeAudio_PreloadXATrack(0,4));
 assert(!NativeAudio_PreloadXATrack(0,6));
 assert(NativeAudio_PlayXATrack(0,4,123,456));
 assert(s_audio.xa.active && s_audio.xa.categoryID==0 && s_audio.xa.xaID==4);
 assert(s_audio.xa.volumeLeft==123 && s_audio.xa.volumeRight==456);
 assert(s_audio.xaStream.sectors!=s_xaCache[0].prepared.sectors);
 assert(memcmp(s_audio.xaStream.sectors,victory.sectors,(size_t)victory.sectorCount*victory.sectorSize)==0);
 /* Stopping/replacing active playback must retain both immutable cached tracks. */
 NativeAudio_CloseXANoLock();
 assert(NativeAudio_PlayXATrack(0,5,321,654));
 assert(memcmp(s_audio.xaStream.sectors,defeat.sectors,(size_t)defeat.sectorCount*defeat.sectorSize)==0);
 assert(NativeAudio_PlayXATrack(0,4,123,456));
 assert(!seeks && !reads);
 NativeAudio_ClearXACache();
 assert(!s_xaCacheBytes && !s_xaCache[0].valid && !s_xaCache[1].valid);
 assert(s_audio.xa.active && s_audio.xaStream.sectors); /* active owns its copy */
 NativeAudio_CloseXANoLock();
 /* A budget failure leaves no partial cache entry and disc fallback works. */
 s_xaCacheBytes=NATIVE_AUDIO_XA_CACHE_BYTES;
 assert(!NativeAudio_PreloadXATrack(0,4));
 assert(!s_xaCache[0].valid);s_xaCacheBytes=0;
 assert(NativeAudio_PlayXATrack(0,4,123,456));
 assert(seeks && reads);NativeAudio_CloseXANoLock();
 /* Both host XA layouts retain identical payload/metadata across a partial batch. */
 for(int layout=0;layout<2;layout++) {
  FILE *f=fopen(argv[2],"wb");assert(f);
  for(int i=0;i<37;i++) {
   u8 raw[2352];assert(NativeDiscImage_ReadRawSector(file.lba+i,raw));
   assert(fwrite(raw+(layout?16:0),1,layout?2336:2352,f)==(layout?2336:2352));
  }
  fclose(f);overridePath=argv[2];
  assert(NativeAudio_XaSourceOpen("fixture.XA",&src));
  seeks=reads=0;assert(NativeAudio_PrepareXAStream(&src,4,35,&host));
  assert(seeks==3 && reads==3);
#ifdef HAVE_LEGACY
  assert(LegacyPrepareXAStream(&src,4,35,&baseline));same(&host,&baseline);
  NativeAudio_XaPreparedStreamClose(&baseline);
#endif
  NativeAudio_XaSourceClose(&src);NativeAudio_XaPreparedStreamClose(&host);
 }
 overridePath=NULL;
 /* Truncated source and invalid raw header fail closed and release partial output. */
 FILE *original=s_nativeDiscImageFile;
 s_nativeDiscImageFile=fopen(argv[2],"rb");assert(s_nativeDiscImageFile);
 struct NativeDiscImageFile bad={0,37*2048};
 assert(!NativeDiscImage_ReadRawSectors(&bad,0,1,a)); /* payload file has no raw sync */
 assert(!NativeDiscImage_ReadRawSectors(&bad,36,1,a)); /* end exceeds truncated file */
 fclose(s_nativeDiscImageFile);s_nativeDiscImageFile=original;
 NativeAudio_XaPreparedStreamClose(&victory);NativeAudio_XaPreparedStreamClose(&defeat);
 fclose(s_nativeDiscImageFile);s_nativeDiscImageFile=NULL;
 puts("PASS real XA bytes/metadata, bounded cache ownership, no disc I/O at cached playback, host layouts and failures");
 return 0;
}
'''
(out / 'fixture.c').write_text(c, encoding='utf-8')
exe = out / 'fixture.exe'
subprocess.run(['clang', '-O0', '-D_WIN32', '-Wno-everything', '-I', str(stubs),
                '-I', str(root / 'include'), '-I', str(root),
                str(out / 'fixture.c'), '-o', str(exe)], check=True)
assets = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'build-360/xex/dist/assets'
subprocess.run([str(exe), str(assets), str(out / 'host.XA')], check=True)
