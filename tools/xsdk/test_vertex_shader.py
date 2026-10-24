"""Execute the bundled vertex shader's color/dither/interface contract."""
import argparse,sys
from pathlib import Path
from test_shader_pixels import bundle_program
p=argparse.ArgumentParser();p.add_argument('--xsdk',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.xsdk/'xenos-toolchain'))
from xdis import simulate
blob,literals=bundle_program(a.bundle.read_text(),'psx_vert')
count=0
for bright in (1,2):
 for off in (0,1):
  for scale in (1,0.75):
   constants=dict(literals);constants.update({0:[0,0,512,216],1:[scale,256,off,0],2:[0]*4,3:[0]*4})
   attrs=[[-123,321,47,32767],[3,4,bright,1],[0.25,0.5,0.75,1],[-1,1,0,0]]
   got=simulate.run(blob,registers={0:[0,0,0,0]},constants=constants,vertex_fetch=lambda n,f,i:attrs[3-n])
   expected={0:[0.25*bright,0.5*bright,0.75*bright,321],1:[2.5,4.5,-123,off],2:[960,512,1008,511],
    62:[((-123-256)*scale+256)/512*2-1,321/216*2-1,0,1]}
   for reg,values in expected.items():
    assert reg in got.exports and max(abs(x-y) for x,y in zip(got.exports[reg],values))<0.0001,(reg,got.exports,expected)
   count+=1
print('PASS: %d actual vertex shader cases: brightness 1/2, unclipped modulation, signed UV correction, packed dither XY, UI scale, page/CLUT, three interpolators'%count)
