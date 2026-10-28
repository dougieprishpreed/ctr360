"""Draw the actual pause background through LIFO OT slots and decode its environments.

Pausing redraws the frame from the PSX draw area as 56 tiles in UI OT slot 4. The
draw area holds the whole widescreen frame packed to 512 wide, so the tiles must draw
full width, not squeezed into the HUD's 4:3 middle, and the pause menu and HUD drawn
after them must stay in the HUD environment. (4:3 squeezes both alike.)
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',default='cc')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
elim=(root/'game/ElimBG.c').read_text();push=(root/'game/PushBuffer.c').read_text();libgpu=(root/'platform/native_libgpu.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
enums=elim[elim.index('enum ElimBGPauseState'):elim.index('void ElimBG_SaveScreenshot_Chunk(')]
body=function(elim,'void ElimBG_HandleState(')
envs=function(push,'void PushBuffer_SetDrawEnv_Normal(')+function(push,'void PushBuffer_SetDrawEnv_Pass(')
c=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef int16_t s16;typedef uint16_t u16;typedef uint32_t u32;typedef uint8_t u8;
typedef struct {s16 x,y,w,h;} RECT16;typedef RECT16 RECT;
typedef struct {RECT16 clip;s16 ofs[2];RECT16 tw;u16 tpage;u8 dtd,dfe,isbg,r0,g0,b0;u32 pad[4];} DRAWENV;
typedef struct {u32 tag;u32 code[15];} DR_ENV;
typedef struct {u32 tag;u8 r0,g0,b0,code;s16 x0,y0;u8 u0,v0;u16 clut;s16 x1,y1;u8 u1,v1;u16 tpage;s16 x2,y2;u8 u2,v2;u16 pad1;s16 x3,y3;u8 u3,v3;u16 pad2;} POLY_FT4;
struct PrimMem {void *cursor,*guardEnd,*end;};
struct PushBuffer {RECT rect;u32 *ptrOT;};
struct DB {DRAWENV drawEnv;struct PrimMem primMem;};
struct GameTracker {struct DB db[2],*backBuffer;struct PushBuffer pushBuffer_UI;u32 renderFlags,hudFlags;};
static struct {struct GameTracker *gGT;int pause_state;char *PausePtrsVRAM[6];} state,*sdata=&state;
enum {RENDER_FLAG_CHECKERED_FLAG=0x1000,RENDER_FLAG_RENDER_BUCKET=0x20,HUD_FLAG_PAUSE_SCREENSHOT_MASK=0xfe,TEXPAGE_COLOR_4BIT=0,TRANS_50=0};
#define CTR_ReadU32LE(p) (*(const u32 *)(p))
#define CTR_WriteU32LE(p,v) (*(u32 *)(p)=(v))
#define setlen(p,n) ((void)(p),(void)(n))
#define setPolyFT4(p) ((p)->code=0x2c)
#define setRGB0(p,r,g,b) ((p)->r0=(r),(p)->g0=(g),(p)->b0=(b))
#define setXY4(p,a,b,c,d,e,f,g,h) ((p)->x0=(a),(p)->y0=(b),(p)->x1=(c),(p)->y1=(d),(p)->x2=(e),(p)->y2=(f),(p)->x3=(g),(p)->y3=(h))
static u16 getTPage(int tp,int abr,int x,int y){return (u16)((tp<<7)|(abr<<5)|((y&0x100)>>4)|((x&0x3ff)>>6));}
static void CtrGpu_WriteControlWord(u32 *d,u32 c){*d=c;}
static int CtrGpu_PrimFits(const void *cursor,const void *guardEnd,u32 bytes){return (const u8 *)cursor+bytes<=(const u8 *)guardEnd;}
static void LoadImage(RECT *r,u32 *p){(void)r;(void)p;}
static void DrawSync(int m){(void)m;}
static void ElimBG_SaveScreenshot_Full(struct GameTracker *g){(void)g;}
static void ElimBG_ToggleAllInstances(struct GameTracker *g,int paused){(void)g;(void)paused;}
/* LIFO OT slots as AddPrim links them; slot values are node indices. */
static struct {void *prim;u32 next;} nodes[4096];static u32 nodeCount;
static void AddPrim(void *ot,void *p){assert(nodeCount<4096);nodes[nodeCount].prim=p;nodes[nodeCount].next=*(u32 *)ot;*(u32 *)ot=++nodeCount;}
enum {FAKE=0x46414b45};
struct Fake {u32 magic;int kind;};static struct Fake menu={FAKE,1},hud={FAKE,2};
void PushBuffer_SetDrawEnv_Pass(void *ot,struct PushBuffer *pb,struct DB *backBuffer,int uiPass);
ENUMS
'''+function(libgpu,'void SetDrawEnv(')+envs+body+r'''
/* Walk like the native parser: E3/E4 set the clip, E5 the offset and the reserved UI-pass
 * bit; primitives take the environment active when drawn. */
static struct {int ui,ofsX,ofsY;RECT16 clip;} env;
static unsigned tiles,tilesUI,fakes,fakesUI,minX=512,maxX;
static s16 Sign11(u32 v){v&=0x7ff;return (s16)((v^0x400)-0x400);}
static void Visit(void *prim){
 if(((struct Fake *)prim)->magic==FAKE){fakes++;fakesUI+=env.ui;assert(env.ofsX==0 && env.clip.w==512);return;}
 if(((u8 *)prim)[7]==0x2c){POLY_FT4 *t=prim;tiles++;tilesUI+=env.ui;
  assert(env.ofsX==0 && env.ofsY==0 && env.clip.x==0 && env.clip.w==512 && env.clip.h==216);
  if(t->x0<(int)minX)minX=t->x0;if(t->x3>(int)maxX)maxX=t->x3;return;}
 DR_ENV *e=prim;u32 a=e->code[0],b=e->code[1],o=e->code[2];
 assert((a>>24)==0xe3 && (b>>24)==0xe4 && (o>>24)==0xe5);
 env.clip.x=a&1023;env.clip.y=(a>>10)&1023;env.clip.w=(b&1023)-env.clip.x+1;env.clip.h=((b>>10)&1023)-env.clip.y+1;
 env.ofsX=Sign11(o);env.ofsY=Sign11(o>>11);env.ui=(o&0x00800000u)!=0;
}
static void Walk(u32 *slot){for(u32 n=*slot;n;n=nodes[n-1].next)Visit(nodes[n-1].prim);}
static unsigned char primBytes[1<<16];
int main(void){
 u32 ui[5]={0};struct GameTracker gt;memset(&gt,0,sizeof(gt));
 struct DB *db=&gt.db[0];gt.backBuffer=db;
 db->drawEnv.clip=(RECT16){0,0,512,216};db->drawEnv.dfe=1;db->primMem.cursor=primBytes;db->primMem.guardEnd=primBytes+sizeof(primBytes);
 gt.pushBuffer_UI.rect=(RECT){0,0,512,216};gt.pushBuffer_UI.ptrOT=ui;sdata->gGT=&gt;
 sdata->pause_state=ELIM_BG_PAUSE_STATE_DRAW;
 ElimBG_HandleState(&gt);                                /* the paused frame's tiles, slot 4 */
 AddPrim(&ui[0],&menu);AddPrim(&ui[2],&hud);             /* pause menu and HUD, later slots */
 PushBuffer_SetDrawEnv_Normal(&ui[4],&gt.pushBuffer_UI,db,0,0);  /* RenderDispEnv_UI, last */
 for(int i=4;i>=0;i--)Walk(&ui[i]);
 printf("tiles=%u full-width=%u x=%u..%u; menu/HUD=%u in the HUD environment=%u\n",tiles,tiles-tilesUI,minX,maxX,fakes,fakesUI);fflush(stdout);
 assert(tiles==56 && tilesUI==0 && minX==0 && maxX==512);
 assert(fakes==2 && fakesUI==2);
 puts("PASS: the pause background draws its 56 tiles full width over the whole frame; the pause menu and HUD after it keep the HUD's 4:3 environment");
}
'''
c=c.replace('ENUMS',enums)
def run(source,name):
 path=a.out/(name+'.c');path.write_text(source);exe=a.out/(name+'.exe')
 subprocess.run([a.cc,'-std=gnu17','-w','-D_XBOX',str(path),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'pause-background');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip().splitlines()[-1])
fullWidth='PushBuffer_SetDrawEnv_Pass(&gGT->pushBuffer_UI.ptrOT[4], &gGT->pushBuffer_UI, gGT->backBuffer, 0);'
restore='PushBuffer_SetDrawEnv_Pass(&gGT->pushBuffer_UI.ptrOT[4], &gGT->pushBuffer_UI, gGT->backBuffer, 1);'
assert fullWidth in body and restore in body
squeezed=c.replace(fullWidth,'').replace(restore,'')
r=run(squeezed,'pause-background-squeezed');assert r.returncode!=0 and 'full-width=0' in r.stdout,r.stdout
assert run(c.replace(restore,''),'pause-background-no-restore').returncode!=0
print('PASS: the squeezed 4:3 background and a full-width environment left on for the pause menu rejected')
