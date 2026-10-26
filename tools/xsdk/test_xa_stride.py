"""Execute the actual XA channel scan on synthetic interleaved files.

Files interleave channels at a fixed stride, so the scan reads only one
channel's sectors once two matches give the stride. It must prepare exactly
the sectors a sequential scan selects, including where a channel ends early,
pauses, or meets non-audio sectors, and read far fewer of them.
"""
import argparse,random,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
src=(root/'platform/native_audio.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
names=('internal int NativeAudio_IsXAAudioSector(','internal int NativeAudio_XaSourceReadSector(',
       'internal void NativeAudio_XaPreparedStreamClose(','internal int NativeAudio_PrepareXAStream(')
SECTOR=2336
def sector(channel,audio=True,stereo=False,tag=0):
 data=bytearray(SECTOR);data[0]=1;data[1]=channel;data[2]=0x64 if audio else 0x08;data[3]=(1 if stereo else 0)|(4 if channel&1 else 0)
 data[8:12]=tag.to_bytes(4,'little');return bytes(data)
cases=[]
rng=random.Random(7)
def build(name,layout):
 (a.out/name).write_bytes(b''.join(sector(*s) for s in layout));return name,len(layout)
for stride in (1,2,4,8,16,32):
 layout=[(i%stride,True,False,i) for i in range(stride*40)]
 for c in range(0,stride,max(1,stride//4)):
  layout2=list(layout)
  for i in range(len(layout2)):            # this channel ends early
   if layout2[i][0]==c and i>stride*25:layout2[i]=(c,False,False,i)
  cases.append((build('xa-%d-%d.bin'%(stride,c),layout2),c))
 cases.append((build('xa-full-%d.bin'%stride,layout),stride-1))
# A pause: the channel skips a few of its slots, then resumes on stride.
layout=[(i%8,True,False,i) for i in range(400)]
for i in range(96,160):
 if layout[i][0]==3:layout[i]=(9,True,False,i)
cases.append((build('xa-pause.bin',layout),3))
# A leading region without the channel, then a regular interleave.
layout=[(5,True,False,i) for i in range(37)]+[(i%4,True,True,i) for i in range(37,300)]
cases.append((build('xa-lead.bin',layout),2))
c=r'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
typedef uint8_t u8;typedef int16_t s16;typedef uint32_t u32;
#define internal static
struct NativeDiscImageFile {int unused;};
static int NativeDiscImage_ReadRawSectors(const struct NativeDiscImageFile *f,u32 s,u32 n,void *d){(void)f;(void)s;(void)n;(void)d;return 0;}
enum {NATIVE_AUDIO_XA_SOURCE_HOST_FILE=1,NATIVE_AUDIO_XA_SOURCE_DISC=2};
'''+''.join(l+'\n' for l in src.splitlines() if re.match(r'#define (XA_|NATIVE_AUDIO_XA_READ_BATCH)',l))+re.search(r'struct NativeAudioXaSource\s*\{.*?\};',src,re.S)[0]+'\n'+re.search(r'struct NativeAudioXaPreparedStream\s*\{.*?\};',src,re.S)[0]+r'''
static unsigned long reads;
static size_t counted_fread(void *p,size_t a,size_t b,FILE *f){reads+=b/XA_FORM2_SECTOR_SIZE;return fread(p,a,b,f);}
#define fread counted_fread
'''+''.join(function(src,n) for n in names)+r'''
int main(int argc,char **argv){
 for(int i=1;i+2<argc;i+=3){
  struct NativeAudioXaPreparedStream prepared;struct NativeAudioXaSource s;int total=atoi(argv[i+2]);
  memset(&s,0,sizeof(s));s.file=fopen(argv[i],"rb");s.kind=NATIVE_AUDIO_XA_SOURCE_HOST_FILE;s.sectorSize=XA_FORM2_SECTOR_SIZE;s.totalSectors=total;
  reads=0;int ok=NativeAudio_PrepareXAStream(&s,atoi(argv[i+1]),total,&prepared);fclose(s.file);free(s.readBuffer);
  printf("%d %lu",ok,reads);
  for(int k=0;ok && k<prepared.sectorCount;k++){u32 tag;memcpy(&tag,prepared.sectors+(size_t)k*XA_FORM2_SECTOR_SIZE+8,4);printf(" %u",tag);}
  printf("\n");if(ok)free(prepared.sectors);
 }
 return 0;
}
'''
path=a.out/'xa-stride.c';path.write_text(c);exe=a.out/'xa-stride'
subprocess.run(['cc','-std=c17','-O1',str(path),'-o',str(exe)],check=True)
args=[]
for (name,total),channel in cases:args+=[str(a.out/name),str(channel),str(total)]
r=subprocess.run([str(exe.resolve())]+args,capture_output=True,text=True,check=True)
lines=r.stdout.strip().splitlines();assert len(lines)==len(cases)
sequential=strided=0
for line,((name,total),channel) in zip(lines,cases):
 data=(a.out/name).read_bytes()
 expected=[int.from_bytes(data[i*SECTOR+8:i*SECTOR+12],'little') for i in range(total)
           if data[i*SECTOR]==1 and data[i*SECTOR+1]==channel and data[i*SECTOR+2]&4 and not (data[i*SECTOR+3]>>4)&3]
 fields=line.split();ok,count=int(fields[0]),int(fields[1]);got=[int(v) for v in fields[2:]]
 assert ok==(len(expected)>0) and got==expected,(name,channel,got[:8],expected[:8])
 sequential+=total;strided+=count
 if re.match(r'xa-full-(8|16|32)\.',name):assert count*3<total,(name,count,total)
print('PASS: actual strided XA scan prepares the sequential sector set for %d synthetic tracks (strides 1-32, full and early-ending channels, pauses, leading gaps); %d of %d sectors read'%(len(cases),strided,sequential))
# The first stride rule took one gap: after a pause it jumped by a multiple of
# the interleave, landed on matches and skipped the sectors between them.
naive=c.replace('if (gap == lastGap)','if (1)')
assert naive!=c
path=a.out/'xa-stride-naive.c';path.write_text(naive);exe=a.out/'xa-stride-naive'
subprocess.run(['cc','-std=c17','-O1',str(path),'-o',str(exe)],check=True)
r=subprocess.run([str(exe.resolve())]+args,capture_output=True,text=True,check=True)
def selected(line):return [int(v) for v in line.split()[2:]]
reference=[selected(l) for l in lines]
assert any(selected(l)!=g for l,g in zip(r.stdout.strip().splitlines(),reference))
print('PASS: single-gap stride rule that skipped sectors after a pause rejected')
