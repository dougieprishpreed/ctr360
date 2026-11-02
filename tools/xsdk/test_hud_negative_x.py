"""The actual HUD sprite helpers (game/DecalHUD.c) at the widened 3/4-player weapon slots.

Widescreen moves each 3/4-player outer HUD element past the authored layout's
edge (NativeHD_WidenSplitScreenHud): player 1's and player 3's weapon slots land
at x -45. The helpers pack a corner as x | y << 16, and retail never passed a
negative x: its sign bits filled the y half, every corner sat at y -1 and the
weapon was never drawn. Checks: the weapon and an FT4 icon keep their place and
size at x -45, -10 and 470, in both turns of the weapon; unmasked packing is
rejected.
"""
import argparse, subprocess
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); p.add_argument('--cc', default='cc')
a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
s = (root / 'game/DecalHUD.c').read_text().replace('\r\n', '\n')
def function(source, start):
    begin = source.index(start); op = source.index('{', begin); depth = 1; end = op + 1
    while depth: depth += (source[end] == '{') - (source[end] == '}'); end += 1
    return source[begin:end] + '\n'
define = s[s.index('#define DECAL_HUD_X'):s.index('\n', s.index('#define DECAL_HUD_X')) + 1]
code = define + function(s, 'void DecalHUD_DrawPolyFT4(') + function(s, 'void DecalHUD_DrawWeapon(')
c = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef int32_t s32;typedef uint32_t u32;typedef s16 VERTTYPE;
#define CTR_PSX_REGISTER(r)
#define CTR_PSX_OBSERVE_VALUE(v) (void)(v)
struct TextureLayout {u8 u0,v0;u16 clut;u8 u1,v1;u16 tpage;u8 u2,v2;u8 u3,v3;};
struct Icon {char name[16];int index;struct TextureLayout texLayout;};
struct PrimMem {void *cursor;};
typedef struct {u32 tag;u8 r0,g0,b0,code;VERTTYPE x0,y0;u8 u0,v0;u16 clut;VERTTYPE x1,y1;u8 u1,v1;u16 tpage;
 VERTTYPE x2,y2;u8 u2,v2;u16 pad1;VERTTYPE x3,y3;u8 u3,v3;u16 pad2;} POLY_FT4;
enum {DECAL_HUD_TPAGE_TRANSPARENCY_MASK=0xff9fffffu};
static u32 CTR_ReadU32LE(const void *p){const u8 *b=p;return b[0]|b[1]<<8|b[2]<<16|(u32)b[3]<<24;}
static u16 CTR_ReadU16LE(const void *p){const u8 *b=p;return (u16)(b[0]|b[1]<<8);}
static void CtrGpu_WritePackedXY(VERTTYPE *xy,u32 v){xy[0]=(s16)(v&0xffff);xy[1]=(s16)(v>>16);}
static void CtrGpu_WritePackedUVWord(u8 *uv,u32 v){(void)uv;(void)v;}
static void CtrGpu_WritePackedUV(u8 *uv,u32 v){(void)uv;(void)v;}
static u32 CtrGpu_PrimToOTLink24(void *p){(void)p;return 0;}
'''+code+r'''
static POLY_FT4 prims[4];
static void Corners(const POLY_FT4 *q,int x,int y,int w,int h){
 int xs[4]={q->x0,q->x1,q->x2,q->x3},ys[4]={q->y0,q->y1,q->y2,q->y3},minX=xs[0],maxX=xs[0],minY=ys[0],maxY=ys[0];
 for(int i=1;i<4;i++){if(xs[i]<minX)minX=xs[i];if(xs[i]>maxX)maxX=xs[i];if(ys[i]<minY)minY=ys[i];if(ys[i]>maxY)maxY=ys[i];}
 assert(minX==x && maxX==x+w && minY==y && maxY==y+h);
}
int main(void){
 /* A 32x24 icon. */
 struct Icon icon;memset(&icon,0,sizeof(icon));icon.texLayout.u1=32;icon.texLayout.v2=24;icon.texLayout.u3=32;icon.texLayout.v3=24;
 struct PrimMem mem;u32 ot=0;
 int xs[]={-45,-10,470};
 for(int i=0;i<3;i++){
  mem.cursor=prims;DecalHUD_DrawWeapon(&icon,xs[i],5,&mem,&ot,1,4096,0);Corners(&prims[0],xs[i],5,32,24);
  mem.cursor=prims;DecalHUD_DrawWeapon(&icon,xs[i],112,&mem,&ot,1,4096,1);Corners(&prims[0],xs[i],112,24,32);
  mem.cursor=prims;DecalHUD_DrawPolyFT4(&icon,xs[i],77,&mem,&ot,0,4096);Corners(&prims[0],xs[i],77,32,24);
 }
 /* Three-quarter scale, as the 4-player tables give the weapon. */
 mem.cursor=prims;DecalHUD_DrawWeapon(&icon,-45,5,&mem,&ot,1,3072,0);Corners(&prims[0],-45,5,24,18);
 puts("PASS: actual HUD weapon and icon sprites keep their place and size at x -45, -10 and 470, both weapon turns and 3/4 scale");
 return 0;
}
'''
def run(text, name):
    source = a.out / (name + '.c'); source.write_text(text); exe = a.out / name
    subprocess.run([a.cc, '-std=gnu17', '-w', str(source), '-o', str(exe)], check=True)
    return subprocess.run([str(exe.resolve())], capture_output=True, text=True)
r = run(c, 'hud-negative-x'); assert r.returncode == 0, r.stdout + r.stderr; print(r.stdout.strip())
unmasked = c.replace('#define DECAL_HUD_X(x) ((u32)(x) & 0xffffu)', '#define DECAL_HUD_X(x) ((u32)(x))')
assert unmasked != c and run(unmasked, 'hud-negative-x-unmasked').returncode != 0
print('PASS: unmasked packing (every corner at y -1 for a negative x) rejected')
