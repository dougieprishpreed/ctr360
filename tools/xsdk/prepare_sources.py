#!/usr/bin/env python3
"""Prepare the audited console source patches, retaining GCC's C17 initializers.
No Microsoft compiler/headers or generated XDK mirror are used.
"""
import argparse, importlib.util, shutil, json
from source_snapshot import snapshot, INPUTS
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args(); root=a.root.resolve();out=a.out.resolve()
if out == root or root not in out.parents: raise SystemExit('output must be a build directory inside source root')
inputs=snapshot(root,INPUTS)
spec=importlib.util.spec_from_file_location('console_patches',root/'tools/ctr360/build_360_mirror.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out.mkdir(parents=True,exist_ok=True)
for name in ['game','include','platform']:
 shutil.copytree(root/name,out/name,dirs_exist_ok=True)
# Use the same numeric PSX command fixes. C89 AST flattening and startup
# fixups are deliberately not run: patched GCC understands C17 designators.
m.apply_all_patches(str(out),lambda message:None)
if inputs!=snapshot(root,INPUTS):raise SystemExit('source changed while preparing')
manifest={'input':inputs,'prepared':snapshot(out,['game','include','platform'])}
(out/'_xsdk_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Prepared C17 console sources:',out)
