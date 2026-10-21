"""Refuse silently changing the experimental compiler/runtime inputs."""
import subprocess,sys
if len(sys.argv)!=3:raise SystemExit('usage: verify_deps.py XSDK VULKAN4XENON')
pins=[('xsdk','49307c7b5fe6cc0e262da7b31af58e4e309aa18e'),('vulkan4xenon','05549ffd76f5c8c65e68b29d14ffb67183287116')]
for location,(name,expected) in zip(sys.argv[1:],pins):
 actual=subprocess.check_output(['git','-C',location,'rev-parse','HEAD'],text=True).strip()
 if actual!=expected: raise SystemExit(f'{name}: expected {expected}, got {actual}')
print('Pinned xSDK and vulkan4xenon revisions verified')
