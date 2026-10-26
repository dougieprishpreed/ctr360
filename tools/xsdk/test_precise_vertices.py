"""Execute the actual GTE, MTC2, SXY store and parser code on T-junctions.

A vertex on another triangle's edge, truncated to whole PSX pixels, leaves a
sliver that covers 720p pixel centres: the background shows through models as
small flecks. Random T-junctions (a fan of two triangles on one side of an edge,
one triangle on the other) are projected through the real RTPS/RTPT, stored
with the real CTR_GteStoreSXY helpers into registered primitive memory, read
back through the real parser conversion, and rasterised at 1280x720 with the
GPU's 1/16 pixel vertex snapping. Exact positions must remove nearly all the
uncovered pixels whole-pixel positions leave (snapping keeps about a pixel at
some junctions), and a vertex must get the same position whether projected
alone, in a triple or reused by a strip.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
gpu=(root/'platform/native_gpu.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
make=function(gpu,'static void MakeVertexPrecise(')
# Host pointers are 64-bit; everything else in the real header is kept.
macros=(root/'include/macros.h').read_text().replace('CTR_STATIC_ASSERT(sizeof(void *) == 4);','')
c=r'''
#define CTR_NATIVE 1
#include <macros.h>
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "platform/native_precise.c"
#include "platform/native_gte_core.c"
#include "platform/native_inline_c.c"
#include <ctr_gte.h>
#include <platform/native_renderer_types.h>
MAKE
typedef struct {double x,y;} P2;
static u32 prims[1<<14];
static u32 pack(int a,int b){return (u16)a|((u32)(u16)b<<16);}
static void load(int slot,const int v[3]){MTC2(pack(v[0],v[1]),slot*2);MTC2(pack(v[2],0),slot*2+1);}
static P2 position(u32 *field,int precise){
 GrVertex g;memset(&g,0,sizeof g);const s16 *xy=(const s16 *)field;g.x=xy[0];g.y=xy[1];
 if(precise)MakeVertexPrecise(&g,(VERTTYPE *)field);
 assert(g._p0>=-128&&g._p0<=127&&g._p1>=-128&&g._p1<=127);
 P2 r={g.x+g._p0/256.0,g.y+g._p1/256.0};return r;}
static int slotIndex;
static u32 *field(void){slotIndex=(slotIndex+1)%(1<<14);return &prims[slotIndex];}
static P2 rtps(const int v[3],int precise){load(0,v);GTE_operator(0x80001);u32 *f=field();CTR_GteStoreSXY(f);return position(f,precise);}
static void rtpt(const int a[3],const int b[3],const int c[3],int precise,P2 out[3]){
 load(0,a);load(1,b);load(2,c);GTE_operator(0x80030);u32 *f0=field(),*f1=field(),*f2=field();
 CTR_GteStoreSXY3(f0,f1,f2);out[0]=position(f0,precise);out[1]=position(f1,precise);out[2]=position(f2,precise);}
static void camera(double yaw,double pitch,int tx,int ty,int tz,int h){
 double cy=cos(yaw),sy=sin(yaw),cp=cos(pitch),sp=sin(pitch);
 double m[3][3]={{cy,0,sy},{sy*sp,cp,-cy*sp},{-sy*cp,sp,cy*cp}};int r[3][3];
 for(int i=0;i<3;i++)for(int j=0;j<3;j++)r[i][j]=(int)lround(m[i][j]*4096);
 CTC2(pack(r[0][0],r[0][1]),0);CTC2(pack(r[0][2],r[1][0]),1);CTC2(pack(r[1][1],r[1][2]),2);
 CTC2(pack(r[2][0],r[2][1]),3);CTC2((u32)(u16)r[2][2],4);CTC2(tx,5);CTC2(ty,6);CTC2(tz,7);
 CTC2(256<<16,24);CTC2(120<<16,25);CTC2(h,26);}
static int same(P2 p,P2 q){return p.x==q.x&&p.y==q.y;}
/* Coverage at 1280x720 pixel centres with 1/16 vertex snapping and a top-left
 * rule, as the console's rasteriser does. */
typedef struct {double x,y;} H;
static H hd(P2 p){H r={round(p.x*2.5*16)/16,round(p.y*3.0*16)/16};return r;}
static double edge(H a,H b,H q){return (b.x-a.x)*(q.y-a.y)-(b.y-a.y)*(q.x-a.x);}
static int topLeft(H a,H b){return (a.y==b.y&&b.x<a.x)||(b.y<a.y);}
static int covers(H a,H b,H c,H q){
 if(edge(a,b,c)<0){H t=b;b=c;c=t;}
 double e0=edge(a,b,q),e1=edge(b,c,q),e2=edge(c,a,q);
 return (e0>0||(e0==0&&topLeft(a,b)))&&(e1>0||(e1==0&&topLeft(b,c)))&&(e2>0||(e2==0&&topLeft(c,a)));}
static double inside(H a,H b,H q){double l=hypot(b.x-a.x,b.y-a.y);return l>0?edge(a,b,q)/l:-1;}
static long cracks(P2 A,P2 B,P2 C,P2 D,P2 T){
 H a=hd(A),b=hd(B),c=hd(C),d=hd(D),t=hd(T);H hull[4]={a,d,b,c};
 if(edge(a,d,b)<0){hull[1]=c;hull[3]=d;}
 double x0=fmin(fmin(a.x,b.x),fmin(c.x,d.x)),x1=fmax(fmax(a.x,b.x),fmax(c.x,d.x));
 double y0=fmin(fmin(a.y,b.y),fmin(c.y,d.y)),y1=fmax(fmax(a.y,b.y),fmax(c.y,d.y));
 long n=0;
 for(int y=(int)floor(y0);y<=(int)ceil(y1);y++)for(int x=(int)floor(x0);x<=(int)ceil(x1);x++){
  H q={x+0.5,y+0.5};int in=1;
  for(int i=0;i<4;i++)if(inside(hull[i],hull[(i+1)%4],q)<=0.5)in=0;
  if(!in)continue;
  if(!covers(a,t,c,q)&&!covers(t,b,c,q)&&!covers(a,b,d,q))n++;}
 return n;}
static int rnd(int lo,int hi){return lo+rand()%(hi-lo+1);}
int main(void){
 g_nativePreciseVertices=1;NativePrecise_SetRegion(0,prims,sizeof prims);NativePrecise_NewFrame();
 long gaps[2]={0,0},cases=0,gapCases[2]={0,0},moved=0;
 srand(12345);
 for(int k=0;k<4000;k++){
  camera(rnd(0,6283)/1000.0,rnd(-900,900)/1000.0,rnd(-400,400),rnd(-300,300),rnd(500,4000),rnd(240,420));
  int A[3]={rnd(-300,300)*2,rnd(-200,200)*2,rnd(-300,300)*2},dir[3]={rnd(-120,120)*2,rnd(-120,120)*2,rnd(-120,120)*2};
  int B[3]={A[0]+dir[0],A[1]+dir[1],A[2]+dir[2]},T[3]={A[0]+dir[0]/2,A[1]+dir[1]/2,A[2]+dir[2]/2};
  int n[3]={dir[1]-dir[2],dir[2]-dir[0],dir[0]-dir[1]};
  int C[3]={T[0]+n[0],T[1]+n[1],T[2]+n[2]},D[3]={T[0]-n[0],T[1]-n[1],T[2]-n[2]};
  for(int mode=0;mode<2;mode++){
   P2 pa=rtps(A,mode),pb=rtps(B,mode),pc=rtps(C,mode),pd=rtps(D,mode),pt=rtps(T,mode);
   if(fabs(pa.x-256)>240||fabs(pb.x-256)>240||fabs(pc.x-256)>240||fabs(pd.x-256)>240||fabs(pa.y-120)>110||fabs(pb.y-120)>110||
      fabs(pc.y-120)>110||fabs(pd.y-120)>110||hypot(pa.x-pb.x,pa.y-pb.y)<8){if(mode==0)break;else continue;}
   if(mode==1){
    /* The same vertex gets the same position alone, in a triple and when a
     * strip reuses it through the SXY0 -> SXY1 copy. */
    P2 tri[3];rtpt(A,T,C,1,tri);assert(same(tri[0],pa)&&same(tri[1],pt)&&same(tri[2],pc));
    load(0,C);GTE_operator(0x80001);load(0,A);GTE_operator(0x80001);load(0,T);GTE_operator(0x80001);
    MTC2(MFC2(12),13);load(0,B);GTE_operator(0x80001);u32 *f0=field(),*f1=field(),*f2=field();
    CTR_GteStoreSXY3(f0,f1,f2);assert(same(position(f0,1),pc)&&same(position(f1,1),pt)&&same(position(f2,1),pb));
    int far[3]={A[0]+30000,A[1],A[2]};rtpt(far,T,C,1,tri);assert(same(tri[1],pt)&&same(tri[2],pc));
    moved+=!same(position(f1,0),pt);
    cases++;}
   long g=cracks(pa,pb,pc,pd,pt);gaps[mode]+=g;gapCases[mode]+=g>0;
  }
 }
 /* Validity rules of the table. */
 int v[3]={10,20,600};camera(0.3,0.2,0,0,1500,300);u32 *f=field();load(0,v);GTE_operator(0x80001);CTR_GteStoreSXY(f);
 s16 dx,dy;assert(NativePrecise_Lookup(f,&dx,&dy));NativePrecise_NewFrame();assert(NativePrecise_Lookup(f,&dx,&dy));
 NativePrecise_NewFrame();assert(!NativePrecise_Lookup(f,&dx,&dy));
 CTR_GteStoreSXY(f);assert(NativePrecise_Lookup(f,&dx,&dy));((s16 *)f)[0]++;assert(!NativePrecise_Lookup(f,&dx,&dy));
 CTR_GteStoreSXY(f);NativePrecise_Suspend(1);CTR_GteStoreSXY(f);NativePrecise_Suspend(0);assert(!NativePrecise_Lookup(f,&dx,&dy));
 CTR_GteStoreSXY(f);g_nativePreciseVertices=0;assert(!NativePrecise_Lookup(f,&dx,&dy));g_nativePreciseVertices=1;
 u32 local;CTR_GteStoreSXY(&local);assert(!NativePrecise_Lookup(&local,&dx,&dy));
 /* Whole pixels move into the coordinate; the fraction stays within a byte. */
 for(int d=-32767;d<=32767;d+=7){
  u32 *g=field();((s16 *)g)[0]=-3;((s16 *)g)[1]=200;NativePreciseEntry *e=NativePrecise_Entry(g);
  e->x=-3;e->y=200;e->dx=(int16_t)d;e->dy=(int16_t)-d;e->generation=s_nativePreciseGeneration;
  P2 q=position(g,1);assert(q.x*256==-3*256+d&&q.y*256==200*256-d);}
 printf("RESULT cases=%ld integer_gaps=%ld integer_cases=%ld precise_gaps=%ld precise_cases=%ld moved=%ld\n",
  cases,gaps[0],gapCases[0],gaps[1],gapCases[1],moved);
 return 0;}
'''.replace('MAKE',make)
def run(source,name,gte=None):
 d=a.out/name;(d/'platform').mkdir(parents=True,exist_ok=True)
 (d/'macros.h').write_text(macros);path=d/(name+'.c');path.write_text(source);exe=d/name
 for f in ('native_precise.c','native_gte_core.c','native_inline_c.c'):
  text=(root/'platform'/f).read_text()
  if f=='native_gte_core.c' and gte:text=gte(text)
  (d/'platform'/f).write_text(text)
 subprocess.run(['cc','-std=gnu17','-O1','-I',str(d),'-I',str(root/'include'),'-I',str(root),str(path),'-o',str(exe),'-lm'],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'precise-vertices');assert r.returncode==0,r.stdout+r.stderr
v=dict((k,int(x)) for k,x in re.findall(r'(\w+)=(\d+)',r.stdout.split('RESULT')[1]))
# What exact positions leave is the rasteriser's 1/16 pixel snapping: about a
# pixel where a junction's sliver happens to cross a pixel centre.
assert v['cases']>=1000 and v['integer_gaps']>=20*max(1,v['precise_gaps']) and v['precise_gaps']<=3*v['precise_cases'] and        v['integer_gaps']>=10*v['integer_cases'],v
print('PASS: %(cases)d actual GTE T-junctions at 720p: whole pixels leave %(integer_gaps)d uncovered pixels in %(integer_cases)d cases, '
      'exact positions %(precise_gaps)d snapping-sized ones in %(precise_cases)d; RTPS, RTPT, strip reuse and a saturated neighbour agree; '
      'table validity rules hold'%v)
# FLAG accumulates over RTPT's vertices: validity read from it gives a vertex a
# different position in a triple with a saturated neighbour than alone.
guard='if (g_nativePreciseVertices && m_sf && !lm && mac3 > 0)'
assert (root/'platform/native_gte_core.c').read_text().count(guard)==1
r=run(c,'precise-vertices-flag',lambda t:t.replace(guard,guard[:-1]+' && C2_FLAG == 0)'));assert r.returncode!=0,r.stdout
print('PASS: FLAG-based validity that splits a shared vertex rejected')
