"""Refuse silently changing the experimental compiler/runtime inputs."""
import subprocess,sys
if len(sys.argv)!=3:raise SystemExit('usage: verify_deps.py XSDK VULKAN4XENON')
pins=[('xsdk','5f6dc726f65f6d171493a3628c2415c03551f27b'),('vulkan4xenon','df25dc50e6296d89822626b433f4080db05bccc8')]
for location,(name,expected) in zip(sys.argv[1:],pins):
 actual=subprocess.check_output(['git','-C',location,'rev-parse','HEAD'],text=True).strip()
 if actual!=expected: raise SystemExit(f'{name}: expected {expected}, got {actual}')
print('Pinned xSDK and vulkan4xenon revisions verified')
