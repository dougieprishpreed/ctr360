"""Packed VRAM is data: verify the actual microcode always fetches level zero."""
import argparse,sys
from pathlib import Path
from test_shader_pixels import bundle_program
p=argparse.ArgumentParser();p.add_argument('--xsdk',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.xsdk/'xenos-toolchain'))
from xdis import container,xenos_ucode as xu
source=a.bundle.read_text();count=0
for name in ['psx_%d_frag'%i for i in range(14) if i%7<6]+['quad_2_frag']:
    blob,_=bundle_program(source,name);c=container.Container(blob)
    fetches=[xu.TextureFetchInstruction(*rec.raw) for rec in xu._decode_program(c.ucode_dwords,c.shader_type)[0] if rec.kind=='tfetch']
    assert fetches,name
    for fetch in fetches:
        assert not fetch.use_computed_lod() and not fetch.use_register_lod() and fetch.lod_bias()==0,(name,'packed data fetch is not explicit level zero')
        assert not fetch.use_register_gradients(),name
        count+=1
print('PASS: %d actual packed VRAM fetches explicitly use level zero, independent of neighboring pixel gradients'%count)
