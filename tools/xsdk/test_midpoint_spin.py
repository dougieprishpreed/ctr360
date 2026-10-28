"""Interpolate spinning models with the actual midpoint matrix blend.

The hub warp pad's beam turns a random 45 to 270 degrees every other update. Halving
the sum of two rotations shortens each axis by the cosine of half the turn, so on
midpoints the beam shrank or collapsed (180 degrees: to a line) and flickered at
60 FPS. Blends keep each axis's average length; past a quarter turn the midpoint
keeps the current rotation.
"""
import argparse,os,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',default='cc')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
hd=(root/'game/MAIN/MainHD.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
blend=function(hd,'static void NativeHD_InterpolateMatrix(')
c=r'''
#define _USE_MATH_DEFINES
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int16_t s16;typedef int32_t s32;typedef uint16_t u16;typedef uint8_t u8;
typedef struct {s16 m[3][3];s16 pad;s32 t[3];} MATRIX;
/* Instance rotation halfwords keep the PSX little-endian image. */
static u16 CTR_ReadU16LE(const void *p){const u8 *b=p;return (u16)(b[0]|b[1]<<8);}
static void CTR_WriteU16LE(void *p,u16 v){u8 *b=p;b[0]=(u8)v;b[1]=(u8)(v>>8);}
BLEND
/* A model turning about Y (the beam, wisps, prizes), scaled per axis like a squashed kart. */
static MATRIX Pose(int angle,float sx,float sy,float sz,int tx){
 MATRIX m;memset(&m,0,sizeof(m));double r=angle*2*M_PI/4096,c=cos(r),s=sin(r);
 double v[3][3]={{c*sx,0,s*sz},{0,sy,0},{-s*sx,0,c*sz}};
 for(int i=0;i<3;i++)for(int j=0;j<3;j++)CTR_WriteU16LE(&m.m[i][j],(u16)(s16)lround(v[i][j]*4096));
 m.t[0]=tx;m.t[1]=100;m.t[2]=-50;return m;
}
static double At(const MATRIX *m,int i,int j){return (s16)CTR_ReadU16LE(&m->m[i][j])/4096.0;}
static double Axis(const MATRIX *m,int j){return sqrt(At(m,0,j)*At(m,0,j)+At(m,1,j)*At(m,1,j)+At(m,2,j)*At(m,2,j));}
int main(void){
 unsigned blended=0,kept=0;double worst[2]={0,0};
 for(int from=0;from<4096;from+=0x155)for(int step=-0xc00;step<=0xc00;step+=0x80){
  float scale=(step&0x100)?0.9f:1.0f;
  MATRIX previous=Pose(from,1,1,scale,0),current=Pose(from+step,1,1,1,40),mid;
  NativeHD_InterpolateMatrix(&mid,&previous,&current);
  assert(mid.t[0]==20 && mid.t[1]==100 && mid.t[2]==-50);
  int turn=((step+0x800)&0xfff)-0x800;
  /* No axis ever shrinks below its two poses' lengths: no collapse, no flicker. */
  for(int j=0;j<3;j++)assert(Axis(&mid,j)>=fmin(Axis(&previous,j),Axis(&current,j))-0.002);
  if(turn>=-0x3ff && turn<=0x3ff){
   /* Up to a quarter turn: half the turn, average scale. */
   MATRIX half=Pose(from+turn/2,1,1,(scale+1)/2,0);
   for(int i=0;i<3;i++)for(int j=0;j<3;j++){double e=fabs(At(&mid,i,j)-At(&half,i,j));if(e>worst[scale<1])worst[scale<1]=e;assert(e<(scale<1?0.06:0.01));}
   blended++;
  }else if(turn>0x400 || turn<-0x400){
   assert(!memcmp(mid.m,current.m,sizeof(mid.m)));kept++;
  }
 }
 printf("PASS: %u spins blended at half the turn with full-length axes (worst element %.3f, %.3f with a squash), %u turns past a quarter keep the current rotation; translations halve\n",
  blended,worst[0],worst[1],kept);
}
'''.replace('BLEND',blend)
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=a.out/(name+'.exe')
 subprocess.run([a.cc,'-std=gnu17','-w',str(source),'-o',str(exe)]+(['-lm'] if os.name!='nt' else []),check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'midpoint-spin');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip())
old=r'''static void NativeHD_InterpolateMatrix(MATRIX *out, const MATRIX *previous, const MATRIX *current)
{
    int row, col;
    *out = *current;
    for (row = 0; row < 3; row++)
    {
        out->t[row] = current->t[row] + (previous->t[row] - current->t[row]) / 2;
        for (col = 0; col < 3; col++)
        {
            int a = (s16)CTR_ReadU16LE(&previous->m[row][col]);
            int b = (s16)CTR_ReadU16LE(&current->m[row][col]);
            CTR_WriteU16LE(&out->m[row][col], (u16)(b + (a - b) / 2));
        }
    }
}
'''
assert run(c.replace(blend,old),'midpoint-spin-average').returncode!=0
print('PASS: the previous element average (beam collapsed to a line at 180 degrees) rejected')
