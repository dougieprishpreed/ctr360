"""Compare actual FXAA microcode with an independent CPU filter reference.

The pinned compiler uses selects for per-pixel control flow, so even flat
regions take all nine samples. Do not claim a GLSL early return saves them.
"""
import argparse,math,sys
from pathlib import Path
from test_shader_pixels import bundle_program

p=argparse.ArgumentParser();p.add_argument('--xsdk',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.xsdk/'xenos-toolchain'))
from xdis import simulate
blob,literals=bundle_program(a.bundle.read_text(),'quad_3_frag')
patterns=[lambda x,y:(0.75,0.25,0.125),lambda x,y:(0.75+x*0.00001,0.25,0.125),
 lambda x,y:(1,0.375,0.125) if x%9<2 else (0,0,0),
 lambda x,y:(1,1,1) if (x+y)%2 else (0,0,0),
 lambda x,y:(1,0.375,0.125) if x>=640 and y>=360 else (0.0625,0.0625,0.0625)]
def dot(c):return sum(x*y for x,y in zip(c,(0.299,0.587,0.114)))
count=0;early=0
for pattern in patterns:
 def sample(uv):
  x=uv[0]*1280-0.5;y=uv[1]*720-0.5;ix=math.floor(x);iy=math.floor(y);fx=x-ix;fy=y-iy
  taps=[pattern(max(0,min(1279,ix+dx)),max(0,min(719,iy+dy))) for dx,dy in ((0,0),(1,0),(0,1),(1,1))]
  weights=((1-fx)*(1-fy),fx*(1-fy),(1-fx)*fy,fx*fy)
  return [sum(t[c]*w for t,w in zip(taps,weights)) for c in range(3)]
 for x,y in ((638,358),(639,359),(640,360),(641,361),(650,400),(0,0),(1279,719)):
  uv=((x+0.5)/1280,(y+0.5)/720);center=sample(uv)
  corners=[sample((uv[0]+dx/1280,uv[1]+dy/720)) for dx,dy in ((-1,-1),(1,-1),(-1,1),(1,1))]
  m=dot(center);nw,ne,sw,se=map(dot,corners);lo=min(m,nw,ne,sw,se);hi=max(m,nw,ne,sw,se)
  flat=hi-lo<max(0.03125,hi*0.125)
  if flat:expected=center;early+=1
  else:
   direction=[-((nw+ne)-(sw+se)),(nw+sw)-(ne+se)]
   reduce=max((nw+ne+sw+se)*0.03125,0.0078125)
   denom=min(map(abs,direction))+reduce
   direction=[max(-8,min(8,v/denom))/size for v,size in zip(direction,(1280,720))]
   taps=[sample(tuple(u+d*t for u,d in zip(uv,direction))) for t in (-1/6,1/6,-0.5,0.5)]
   A=[(taps[0][c]+taps[1][c])*0.5 for c in range(3)]
   B=[A[c]*0.5+(taps[2][c]+taps[3][c])*0.25 for c in range(3)]
   expected=A if dot(B)<lo or dot(B)>hi else B
  fetches=[0]
  def fetch(slot,coords):fetches[0]+=1;return sample(coords)+[1]
  got=simulate.run(blob,registers={0:[*uv,0,0]},constants=literals,texture_fetch=fetch)
  assert not got.killed and max(abs(v-e) for v,e in zip(got.exports[0],expected+[1]))<0.0003,(x,y,got.exports,expected)
  assert fetches[0]==9,(flat,fetches)
  count+=1
assert early and early<count
print('PASS: %d actual FXAA pixel cases (orange strokes, edges, checkerboard, boundaries); flat/edge paths use 9 fetches as pinned compiler lowers them'%count)
