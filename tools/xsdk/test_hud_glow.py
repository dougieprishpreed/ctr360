"""Execute glow routing through LIFO OT slots and HUD capture/replay.

Retail links the juiced shine into each player's front world-OT slot: after
the world, behind every UI slot (the 1P fruit model sits in UI slot 0), with the
player's viewport offset/clip. HD squeezes and replays only the UI pass, so the
shine must keep that order and environment inside the UI pass.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
weapon=(root/'game/UI/UI_Weapon.c').read_text();gpu=(root/'platform/native_gpu.c').read_text()
push=(root/'game/PushBuffer.c').read_text();libgpu=(root/'platform/native_libgpu.c').read_text()
def function(source,start):
 begin=source.index(start);op=source.index('{',begin);depth=1;end=op+1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[begin:end]+'\n'
body=function(weapon,'void UI_Weapon_DrawBG(')
constants='enum {'+''.join(re.findall(r'\bUI_WEAPON_BG_\w+\s*=\s*[^,;]+,',weapon))+'};\n'
color=re.search(r'static const u32 UI_WEAPON_BG_SHINE_COLOR[^;]+;',weapon)[0]
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
typedef struct {s16 x,y,page,clut;unsigned char rest[12];} GrVertex;
struct Icon {int identity;};struct PrimMem {void *cursor,*guardEnd;};
struct PushBuffer {RECT rect;u32 *ptrOT;};
struct DB {DRAWENV drawEnv;struct PrimMem primMem;};
struct GameTracker {struct Icon *ptrIcons[64];struct DB *backBuffer;struct PushBuffer pushBuffer[4],pushBuffer_UI;};
struct Driver {int driverID;struct {int juicedUpCooldown;} BattleHUD;};
static struct {struct GameTracker *gGT;int wumpaShineTheta;} state,*sdata=&state;
#define CTR_ReadU32LE(p) (*(const u32 *)(p))
#define CTR_WriteU32LE(p,v) (*(u32 *)(p)=(v))
#define setlen(p,n) ((void)(p),(void)(n))
static void CtrGpu_WriteControlWord(u32 *d,u32 c){*d=c;}
static int CtrGpu_PrimFits(const void *cursor,const void *guardEnd,u32 bytes){return (const u8 *)cursor+bytes<=(const u8 *)guardEnd;}
/* LIFO OT slots as AddPrim links them; slot values are node indices. */
static struct {void *prim;u32 next;} nodes[4096];static u32 nodeCount;
static void AddPrim(void *ot,void *p){assert(nodeCount<4096);nodes[nodeCount].prim=p;nodes[nodeCount].next=*(u32 *)ot;*(u32 *)ot=++nodeCount;}
enum {FAKE=0x46414b45,SHINE=1,ICON,FRUIT,ELIM};
struct Fake {u32 magic;int kind,player,layer;};
static struct Fake fakes[4096];static unsigned fakeCount;
static struct Fake *Fake(int kind,int player,int layer){struct Fake *f=&fakes[fakeCount++];f->magic=FAKE;f->kind=kind;f->player=player;f->layer=layer;return f;}
static int currentPlayer;static unsigned calls;
typedef struct {int uiPass;struct {int dfe;} drawenv;u16 startVertex,numVerts;} GPUDrawSplit;
enum {NATIVE_HD_HUD_VERTICES=24576,NATIVE_HD_HUD_SPLITS=1024};
static GrVertex s_hdHUDVertices[NATIVE_HD_HUD_VERTICES];static GPUDrawSplit s_hdHUDSplits[NATIVE_HD_HUD_SPLITS];
static int s_hdHUDVertexCount,s_hdHUDSplitCount,s_hdHUDCaptureEnabled,s_hdHUDValid;
static unsigned replays,uploads,captured;
void PushBuffer_SetDrawEnv_Pass(void *ot,struct PushBuffer *pb,struct DB *backBuffer,int uiPass);
'''+constants+color+function(libgpu,'void SetDrawEnv(')+envs+function(gpu,'static void NativeGpu_CaptureHUD(')+r'''
static void UI_WeaponBG_DrawShine(struct Icon *icon,s16 x,s16 y,struct PrimMem *mem,u32 *ot,char transparency,s16 sx,s16 sy,int color){
 assert(icon==sdata->gGT->ptrIcons[49] && sx==4096 && sy==3328 && transparency==2+(calls%2));calls++;
 for(int quad=0;quad<4;quad++)AddPrim(ot,Fake(SHINE,currentPlayer,transparency));
}
static void NativeRenderer_UpdateVertexBuffer(const GrVertex *v,int count){assert(count==(int)captured*3);uploads++;}
static void DrawSplit(const GPUDrawSplit *split){assert(split->uiPass && split->numVerts==3);replays++;}
'''+body+function(gpu,'void NativeGpu_ReplayHUD(')+r'''
/* Walk like the native parser: E3/E4 set the clip, E5 the offset and the
 * reserved UI-pass bit; primitives take the environment active when drawn. */
static struct {int ui,ofsX,ofsY;RECT16 clip;} env;
struct Drawn {struct Fake *fake;int ui,ofsX,ofsY;RECT16 clip;} drawn[4096];static unsigned drawnCount;
static s16 Sign11(u32 v){v&=0x7ff;return (s16)((v^0x400)-0x400);}
static void Visit(void *prim){
 struct Fake *f=prim;
 if(f->magic==FAKE){struct Drawn *d=&drawn[drawnCount++];d->fake=f;d->ui=env.ui;d->ofsX=env.ofsX;d->ofsY=env.ofsY;d->clip=env.clip;
  if(f->kind==SHINE && env.ui){GrVertex v[3]={{0}};GPUDrawSplit split={.uiPass=1,.drawenv={1},.numVerts=3};NativeGpu_CaptureHUD(&split,v);captured++;}
  return;}
 DR_ENV *e=prim;u32 a=e->code[0],b=e->code[1],o=e->code[2];
 assert((a>>24)==0xe3 && (b>>24)==0xe4 && (o>>24)==0xe5);
 env.clip.x=a&1023;env.clip.y=(a>>10)&1023;env.clip.w=(b&1023)-env.clip.x+1;env.clip.h=((b>>10)&1023)-env.clip.y+1;
 env.ofsX=Sign11(o);env.ofsY=Sign11(o>>11);env.ui=(o&0x00800000u)!=0;
}
static void Walk(u32 *slot){for(u32 n=*slot;n;n=nodes[n-1].next)Visit(nodes[n-1].prim);}
static unsigned char primBytes[1<<16];
static void Frame(int players,const RECT *rects){
 u32 world[4][0x400],ui[5];struct GameTracker gt={0};struct Icon icon={1};struct DB db={0};
 memset(world,0,sizeof(world));memset(ui,0,sizeof(ui));nodeCount=fakeCount=drawnCount=captured=0;
 db.drawEnv.clip=(RECT16){0,0,512,216};db.drawEnv.dfe=1;db.primMem.cursor=primBytes;db.primMem.guardEnd=primBytes+sizeof(primBytes);
 gt.backBuffer=&db;gt.ptrIcons[49]=&icon;gt.pushBuffer_UI.rect=(RECT){0,0,512,216};gt.pushBuffer_UI.ptrOT=ui;sdata->gGT=&gt;
 for(int i=0;i<4;i++){gt.pushBuffer[i].rect=rects[i];gt.pushBuffer[i].ptrOT=world[i];}
 s_hdHUDVertexCount=s_hdHUDSplitCount=0;s_hdHUDValid=s_hdHUDCaptureEnabled=1;
 AddPrim(&ui[4],Fake(ELIM,-1,0));                     /* ElimBG, linked at frame start */
 for(int player=0;player<players;player++){           /* UI_RenderFrame: icons, then shines */
  currentPlayer=player;AddPrim(&ui[0],Fake(ICON,player,0));
  struct Driver driver={.driverID=player,.BattleHUD={1}};unsigned theta=state.wumpaShineTheta;
  UI_Weapon_DrawBG(286,9,4096,&driver);UI_Weapon_DrawBG(209,-5,4096,&driver);
  assert(driver.BattleHUD.juicedUpCooldown==0 && state.wumpaShineTheta==theta+512);
 }
 for(int player=0;player<players;player++)AddPrim(&ui[0],Fake(FRUIT,player,0)); /* instances, later */
 for(int player=0;player<players;player++)PushBuffer_SetDrawEnv_Normal(&world[player][0x3ff],&gt.pushBuffer[player],&db,0,0);
 PushBuffer_SetDrawEnv_Normal(&ui[4],&gt.pushBuffer_UI,&db,0,0);  /* RenderDispEnv_UI, last */
 env.ui=0;for(int player=0;player<players;player++)for(int i=0x3ff;i>=0;i--)Walk(&world[player][i]);
 for(int i=4;i>=0;i--)Walk(&ui[i]);
 unsigned shines=0,lastShine=0,firstHUD=drawnCount;
 for(unsigned i=0;i<drawnCount;i++){
  struct Drawn *d=&drawn[i];
  if(d->fake->kind==SHINE){
   const RECT *r=&rects[d->fake->player];shines++;lastShine=i;
   assert(d->ui && d->ofsX==r->x && d->ofsY==r->y);
   assert(d->clip.x==r->x && d->clip.y==r->y && d->clip.w==r->w && d->clip.h==r->h);
  }else{
   if(i<firstHUD)firstHUD=i;
   assert(d->ui && d->ofsX==0 && d->ofsY==0 && d->clip.w==512 && d->clip.h==216);
  }
 }
 assert(shines==16u*players && lastShine<firstHUD);
 for(unsigned i=0;i+1<drawnCount;i++)if(drawn[i].fake->kind==SHINE && drawn[i+1].fake->kind==SHINE && drawn[i].fake->player==drawn[i+1].fake->player)
  assert(drawn[i].fake->layer>=drawn[i+1].fake->layer || (i+1)%8==0);
 assert(s_hdHUDSplitCount==(int)shines && captured==shines);
 unsigned theta=state.wumpaShineTheta,before=replays;NativeGpu_ReplayHUD();
 assert(state.wumpaShineTheta==theta && replays==before+shines);
}
int main(void){
 const RECT one[4]={{0,0,512,216},{0,0,512,216},{0,0,512,216},{0,0,512,216}};
 const RECT two[4]={{0,0,512,106},{0,110,512,106},{0,0,512,216},{0,0,512,216}};
 const RECT four[4]={{0,0,254,106},{258,0,254,106},{0,110,254,106},{258,110,254,106}};
 Frame(1,one);Frame(2,two);Frame(4,four);
 assert(calls==2u*2*(1+2+4) && uploads==3);
 puts("PASS: shines draw first in the UI pass, behind HUD icons and fruit, under each player's offset/clip; HUD environment restored; captured/replayed without animation ticks");
}
'''
def run(source,name,defines=('-D_XBOX',)):
 path=a.out/(name+'.c');path.write_text(source);exe=a.out/name
 subprocess.run(['cc','-std=c17',*defines,str(path),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'hud-glow');assert r.returncode==0,r.stderr;print(r.stdout.strip())
previous=body.replace('ot = &gGT->pushBuffer_UI.ptrOT[UI_WEAPON_BG_SHINE_HUD_SLOT];','ot = gGT->pushBuffer_UI.ptrOT;').replace(
 'PushBuffer_SetDrawEnv_Normal(ot, &gGT->pushBuffer_UI, gGT->backBuffer, 0, 0);','').replace(
 'PushBuffer_SetDrawEnv_Pass(ot, &gGT->pushBuffer[d->driverID], gGT->backBuffer, 1);','')
assert previous!=body and run(c.replace(body,previous),'hud-glow-ui-slot0-negative').returncode!=0
norestore=body.replace('PushBuffer_SetDrawEnv_Normal(ot, &gGT->pushBuffer_UI, gGT->backBuffer, 0, 0);','')
assert norestore!=body and run(c.replace(body,norestore),'hud-glow-no-restore-negative').returncode!=0
assert run(c,'hud-glow-world-negative',()).returncode!=0
print('PASS: UI slot 0 routing (shine over fruit, no player offset), missing HUD environment restore and retail world-OT routing rejected')
