"""Verify the bundled shader really skips main-target dither arithmetic."""
import argparse,sys
from pathlib import Path
from test_shader_pixels import bundle_program

p=argparse.ArgumentParser();p.add_argument('--xsdk',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
p.add_argument('--baseline',type=Path);a=p.parse_args();sys.path.insert(0,str(a.xsdk/'xenos-toolchain'))
from xdis import simulate

def work(bundle,name,offscreen,legacy=False):
 blob,constants=bundle_program(bundle,name)
 constants.update({0:[0,0,512,216],1:[1,256,int(offscreen),0],2:[0,0,0,0],3:[0,0,0,0]})
 count=[0];execute=simulate._execute
 def tracked(rec,*args,**kwargs):
  if rec.kind=='alu':count[0]+=1
  return execute(rec,*args,**kwargs)
 simulate._execute=tracked
 try:
  inputs={0:[0.5,0.5,1,int(offscreen)],1:[0.7,0.5,0.3,1],2:[0,0,0,0],3:[0,0,16,128]} if legacy else {0:[0.7,0.5,0.3,0],1:[0.5,0.5,0,int(offscreen)],2:[0,0,16,128]}
  result=simulate.run(blob,registers=inputs,
    constants=constants,texture_fetch=lambda slot,coords:[1,127/255,0,1])
 finally:simulate._execute=execute
 assert not result.killed
 return count[0],result.exports[0]

current=a.bundle.read_text();baseline=a.baseline.read_text() if a.baseline else None
texture_budgets=(44,130,38,108,29,78,2)
for shader in range(7):
 name='psx_%d_frag'%shader
 main,main_pixel=work(current,name,False);off,off_pixel=work(current,'psx_%d_frag'%(shader+7),True)
 assert main<off,(name,'uniform arm did not skip ALU instructions',main,off)
 assert main<=texture_budgets[shader],(name,'packed texture ALU regression',main,texture_budgets[shader])
 if baseline:
  old_main,old_pixel=work(baseline,name,False,True);old_off,old_off_pixel=work(baseline,name,True,True)
  assert max(abs(x-y) for x,y in zip(main_pixel,old_pixel))<0.0001
  assert max(abs(x-y) for x,y in zip(off_pixel,old_off_pixel))<0.0001
  assert main<old_main,(name,'no main-target work reduction',main,old_main)
  print('%s executed ALU instructions: main %d -> %d; offscreen %d -> %d'%(name,old_main,main,old_off,off))
 else:print('%s executed ALU instructions: main=%d offscreen=%d'%(name,main,off))
print('PASS: actual bundled main variants omit dither arithmetic; offscreen variants preserve pixels; no hardware speed claim')
