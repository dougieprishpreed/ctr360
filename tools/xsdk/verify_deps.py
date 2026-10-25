"""Refuse silently changing the experimental compiler/runtime inputs."""
import subprocess,sys
if len(sys.argv)!=3:raise SystemExit('usage: verify_deps.py XSDK VULKAN4XENON')
pins=[('xsdk','6346a39e242c6dcc4e9a5a05cd9f9a602fd55f4b'),('vulkan4xenon','b79913b407504b1e1663e74b14579cd91d2e7040')]
for location,(name,expected) in zip(sys.argv[1:],pins):
 actual=subprocess.check_output(['git','-C',location,'rev-parse','HEAD'],text=True).strip()
 if actual!=expected: raise SystemExit(f'{name}: expected {expected}, got {actual}')
print('Pinned xSDK and vulkan4xenon revisions verified')
