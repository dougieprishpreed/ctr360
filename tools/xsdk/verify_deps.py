"""Refuse silently changing the experimental compiler/runtime inputs."""
import subprocess,sys
if len(sys.argv)!=3:raise SystemExit('usage: verify_deps.py XSDK VULKAN4XENON')
pins=[('xsdk','57b02f1e60667e37d22c3aa613d23d2486514ff8'),('vulkan4xenon','3992a14945f5852e6fc5a3ee62f6fa860d0aa13b')]
for location,(name,expected) in zip(sys.argv[1:],pins):
 actual=subprocess.check_output(['git','-C',location,'rev-parse','HEAD'],text=True).strip()
 if actual!=expected: raise SystemExit(f'{name}: expected {expected}, got {actual}')
print('Pinned xSDK and vulkan4xenon revisions verified')
