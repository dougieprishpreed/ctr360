"""Actual banner lifecycle and GT3 writer with LE/BE palette storage proxies.

Uses Tiger Temple's retail banner, commands, vertex bytes, UVs and the engine's
trig table. Only native palette pointer accesses use a four-byte storage proxy
to exercise Xenon's memory order on the host. GTE projection is a register
fixture; this does not certify rendered pixels or console performance.
"""
from pathlib import Path
import argparse
import json
import re
import struct
import subprocess

import cook_disc as cook
from audit_endian_assets import model_roots

root = Path(__file__).resolve().parents[2]
out = root/'build-360/results/banner-palette'
out.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--old-palette', action='store_true', help='negative control: restore the old byte writes')
args = parser.parse_args()

def function(path, name):
    text = (root/path).read_text()
    match = re.search(r'^.*\b'+name+r'\([^;]*?\)\s*\n\{', text, re.M)
    assert match, name
    begin = text.index('{', match.start())
    end, depth = begin+1, 1
    while depth:
        depth += (text[end]=='{')-(text[end]=='}')
        end += 1
    return text[match.start():end]+'\n'

image = cook.IsoImage(str(root.parent/'CTR - Crash Team Racing (USA)/CTR - Crash Team Racing (USA).bin'))
big = cook.BigFile(image)
sector, size = big.entries[33]  # Single-player Tiger Temple LEV.
raw = image.read(big.lba+sector, size)
image.close()
mapped = {site[0]-4 for site in cook.dram_swap_sites(raw,33,set()) if site[0]>=4}
word = lambda p: struct.unpack_from('<I',raw,p)[0]
model = next(r+4 for r in model_roots(raw,mapped) if struct.unpack_from('<h',raw,r+20)[0]==166)
header = word(model+20)+4
cmd, frame, tex, colors = [word(header+i)+4 for i in (32,36,40,44)]
commands=[]
for i in range(0x4000):
    commands.append(word(cmd+i*4))
    if commands[-1]==0xffffffff: break
assert commands[0]==64 and commands[-1]==0xffffffff
palette = [word(colors+i*4) for i in range(64)]
uv = raw[word(tex+79*4)+4:word(tex+79*4)+16]  # Texture 80 matches the first bad packet.
assert word(word(tex+79*4)+4)==0x74feff69
frame_bytes=raw[frame:tex]
vertex_offset=word(frame+24)
table_text=(root/'game/zGlobal_DATA.c').read_text().split('.trigApprox =',1)[1]
trig=[int(a,16)|(int(b,16)<<16) for a,b in re.findall(r'\{(0x[0-9a-f]+),\s*(0x[0-9a-f]+)\}',table_text)[:1024]]
assert len(trig)==1024 and trig[0]==0x10000000

def array(name, ctype, values):
    return f'static const {ctype} {name}[]={{'+','.join(hex(v) for v in values)+'};\n'

prefix=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define CTR_NATIVE 1
#define CTR_STATIC_ASSERT(x) static_assert(x, #x)
typedef uint8_t u8;typedef int8_t s8;typedef uint16_t u16;typedef int16_t s16;
typedef uint32_t u32;typedef int32_t s32;typedef int b32;typedef s16 VERTTYPE;
template<bool Big> struct EncodedWord {
 u8 bytes[4];
 operator u32() const {u32 n=0;for(int i=0;i<4;i++)n|=(u32)bytes[i]<<(8*(Big?3-i:i));return n;}
 EncodedWord& operator=(u32 n){for(int i=0;i<4;i++)bytes[i]=(u8)(n>>(8*(Big?3-i:i)));return *this;}
};
using PaletteWord=EncodedWord<BE_PALETTE>;
static_assert(sizeof(PaletteWord)==4,"palette stride");
struct ModelFrame {u8 header[24];u32 vertexOffset;};
struct ModelHeader {ModelFrame*ptrFrameData;u32*ptrCommandList;PaletteWord*ptrColors;};
struct Model {ModelHeader*headers;};
struct StartBanner {s16 unused,numVertices;};
struct Instance {struct Thread*thread;Model*model;};
struct Thread {StartBanner*object;Instance*inst;void(*funcThTick)(Thread*);};
static struct {int numPlyrCurrGame;Model*modelPtr[256];} gt;
#define GAME_TRACKER (&gt)
#define STATIC_STARTBANNERWAVE 166
#define SIZE_RELATIVE_POOL_BUCKET(a,b,c,d) (a)
static StartBanner bannerObject;static Thread bannerThread;
static Thread* PROC_BirthWithObject(int,void(*cb)(Thread*),const char*,void*){
 bannerThread.object=&bannerObject;bannerThread.funcThTick=cb;return &bannerThread;
}
static u8 scratch[4096];
#define CTR_SCRATCHPAD_PTR(t,n) ((t*)(scratch+(n)))
static struct {u32 trigApprox[1024];} data;
static u32 CTR_TrigApproxWord(const u32*p){return *p;}
#define ANG_QUADRANT_MASK 1023
#define ANG_QUADRANT_BIT 1024
#define ANG_SIGN_BIT 2048
typedef struct {u32 tag;u8 r0,g0,b0,code;s16 x0,y0;u8 u0,v0;u16 clut;
 u8 r1,g1,b1,pad1;s16 x1,y1;u8 u1,v1;u16 tpage;
 u8 r2,g2,b2,pad2;s16 x2,y2;u8 u2,v2;u16 pad3;} POLY_GT3;
typedef struct {u32 tag;u8 r0,g0,b0,code;s16 x0,y0;u8 r1,g1,b1,pad1;s16 x1,y1;u8 r2,g2,b2,pad2;s16 x2,y2;} POLY_G3;
struct PrimMem {void*cursor,*guardEnd;};
struct IDPP {s16 alphaScale;};
struct RenderBucketDrawContext {PrimMem*primMem;IDPP*idpp;u32 tempColor[4];};
struct TextureLayout {u8 bytes[12];};
#define RENDER_BUCKET_TEX_WORD0_OFFSET 0
#define RENDER_BUCKET_TEX_WORD1_OFFSET 4
#define RENDER_BUCKET_TEX_WORD2_OFFSET 8
static u32 regs[32];
#define MTC2(v,n) (regs[n]=(u32)(v))
#define MFC2(n) (regs[n])
static int RenderBucket_OTEntryPassesDpctGate(const u32*){return 1;}
static void gte_dpct(void){abort();} // Fixture uses the unfaded palette (alpha zero).
static u32 CTR_ReadU32LE(const void*p){const u8*b=(const u8*)p;return b[0]|((u32)b[1]<<8)|((u32)b[2]<<16)|((u32)b[3]<<24);}
static u32 RenderBucket_ReadTextureWord(TextureLayout*t,int n){return CTR_ReadU32LE(t->bytes+n);}
static void CTR_GteStoreSXY3(s16*a,s16*b,s16*c){
 s16*xy[]={a,b,c};for(int i=0;i<3;i++){xy[i][0]=(s16)regs[12+i];xy[i][1]=(s16)(regs[12+i]>>16);}
}
static void RenderBucket_LinkPrimRaw(u32*ot,void*p,u32 tag){*(u32*)p=tag|(*ot&0xffffff);*ot=1;}
'''
source=(root/'game/231/RB_Banner.c').read_text().replace('#include <common.h>','')
if args.old_palette:
    source=source.replace('u32 *color = inst->model->headers->ptrColors;', 'u8 *color = (u8 *)inst->model->headers->ptrColors;')
    fixed='*color = (*color & 0xff000000u) | ((u32)(u8)value * 0x00010101u);\n\t\t\tcolor++;'
    assert fixed in source
    source=source.replace(fixed,'color[2] = (u8)value; color[1] = (u8)value; color[0] = (u8)value; color += 4;')
# Adapt only native palette memory accesses and 64-bit host pointer comparisons.
source=re.sub(r'u32 \*(color|colors|palette)\b',r'PaletteWord *\1',source)
source=source.replace('*(u32 *)cursor','*(PaletteWord *)cursor')
source=source.replace('(u32)cursor','(uintptr_t)cursor').replace('(u32)vertex','(uintptr_t)vertex')
source=source.replace('u32 end;', 'uintptr_t end;')
source+=''.join(function('include/gpu.h',n) for n in ('CtrGpu_WriteColorCode','CtrGpu_WritePackedUVWord'))
source+=function('game/RenderBucket/RenderBucket_QueueExecute.c','RenderBucket_LoadPrimColors')
source+=function('game/RenderBucket/RenderBucket_QueueExecute.c','RenderBucket_DrawInstPrim_NormalAtOTEntry')
# C's implicit void-pointer conversions need explicit casts in this C++ proxy fixture.
source=source.replace('POLY_G3 *p = ctx->primMem->cursor;', 'POLY_G3 *p = (POLY_G3 *)ctx->primMem->cursor;')
source=source.replace('p = ctx->primMem->cursor;', 'p = (POLY_GT3 *)ctx->primMem->cursor;')
source+=array('originalCommands','u32',commands)+array('originalPalette','u32',palette)
source+=array('originalFrame','u8',frame_bytes)+array('originalUV','u8',uv)+array('originalTrig','u32',trig)
tests=r'''
int main(void){
 memcpy(data.trigApprox,originalTrig,sizeof originalTrig);unsigned bad=0,packets=0,matched=0;
 for(int players=1;players<=4;players++){
  gt.numPlyrCurrGame=players;memset(scratch,0,sizeof scratch);
  u32 commands[sizeof originalCommands/4];memcpy(commands,originalCommands,sizeof commands);
  alignas(4) u8 frameBytes[sizeof originalFrame];memcpy(frameBytes,originalFrame,sizeof frameBytes);
  ModelFrame*frame=(ModelFrame*)frameBytes;frame->vertexOffset=VERTEX_OFFSET;
  PaletteWord colors[64];for(int i=0;i<64;i++)colors[i]=originalPalette[i];
  ModelHeader header={frame,commands,colors};Model model={&header};Instance inst={nullptr,&model};
  gt.modelPtr[166]=&model;RB_Banner_LInB(&inst);
  assert(inst.thread==&bannerThread&&bannerObject.numVertices>0);
  u32 expected[64];
  for(int i=0;i<64;i++){
   int angle=i*128;u32 p=data.trigApprox[angle&1023];if(!(angle&1024))p<<=16;
   s32 v=(s32)p>>16;if(angle&2048)v=-v;v=(v>>6)+128;if(players>=4)v=128;
   expected[i]=(originalPalette[i]&0xff000000u)|((u32)(u8)v*0x010101u);
   bad+=(u32)colors[i]!=expected[i];
  }
  for(int tick=0;tick<128;tick++){
   if(players<4){
    RB_Banner_ThTick(&bannerThread);u32 first=expected[0];memmove(expected,expected+1,63*4);expected[63]=first;
   }
   for(int i=0;i<64;i++){
    POLY_GT3 packet={};u8 arena[sizeof(POLY_GT3)+64]={};PrimMem pm={arena,arena+sizeof arena};
    IDPP idpp={0};RenderBucketDrawContext ctx={&pm,&idpp,{0,(u32)colors[i],(u32)colors[i],(u32)colors[i]}};
    TextureLayout texture;memcpy(&texture,originalUV,12);u32 ot=0;
    regs[12]=0xfff5000d;regs[13]=0x00260020;regs[14]=0x00180015;
    assert(RenderBucket_DrawInstPrim_NormalAtOTEntry(&ctx,0,&texture,&ot)==0);
    memcpy(&packet,arena,sizeof packet);packets++;
    bad+=packet.code!=0x34 || packet.r0!=(u8)expected[i] || packet.g0!=(u8)(expected[i]>>8) || packet.b0!=(u8)(expected[i]>>16);
    assert(packet.tag>>24==9&&packet.clut==0x74fe&&packet.tpage==0x007b&&packet.u0==0x69&&packet.v0==0xff);
    assert(packet.x0==13&&packet.y0==-11&&(u8*)pm.cursor==arena+sizeof packet);
    /* This is exactly the console's native word dump for its first overshoot. */
    u32 logged=((u32)packet.r0<<24)|((u32)packet.g0<<16)|((u32)packet.b0<<8)|packet.code;
    matched+=logged==0x00676777;
   }
  }
 }
 printf("palette storage=%s, %u actual GT3 packets, mismatches=%u, old-log-word matches=%u\n",BE_PALETTE?"BE":"LE",packets,bad,matched);
 if(bad)return 1;
 puts("PASS actual banner init/rotation/GT3 emission: numeric RGB and command preserved through 128 ticks, 1/2/3/4 players; Tiger Temple UV/CLUT and native XY verified");
}
'''.replace('VERTEX_OFFSET',str(vertex_offset))
evidence={'entry':33,'model_id':166,'texture_index':80,'uv_words':[f'{x:08x}' for x in struct.unpack('<III',uv)],
          'palette_storage_proxy':'four bytes with target-endian numeric read/write; remaining engine arithmetic and functions unchanged',
          'gte':'fixed projected XY; alpha zero avoids depth-fade operation','old_palette':args.old_palette,'runs':[]}
for big_endian in (False, True):
    name=('old-' if args.old_palette else '')+('be' if big_endian else 'le')
    path=out/(name+'.cpp')
    path.write_text('#define BE_PALETTE '+str(int(big_endian))+'\n'+prefix+source+tests)
    subprocess.run(['clang++','-std=c++17','-O2','-fno-strict-aliasing','-Wno-pointer-to-int-cast',str(path),'-o',str(out/(name+'.exe'))],check=True)
    run=subprocess.run([str(out/(name+'.exe'))],capture_output=True,text=True)
    (out/(name+'.log')).write_text(run.stdout+run.stderr)
    print(run.stdout+run.stderr,end='')
    evidence['runs'].append({'storage':'BE' if big_endian else 'LE','returncode':run.returncode,'output':run.stdout})
    assert run.returncode==(1 if args.old_palette and big_endian else 0), evidence['runs'][-1]
    if args.old_palette and big_endian:
        match = re.search(r'old-log-word matches=(\d+)', run.stdout)
        assert match and int(match.group(1)) > 0, 'negative control must reproduce the logged color/opcode word'
(out/('negative.json' if args.old_palette else 'positive.json')).write_text(json.dumps(evidence,indent=2)+'\n')
