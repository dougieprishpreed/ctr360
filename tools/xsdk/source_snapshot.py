"""Reject source or prepared-tree edits during an open SDK build."""
import argparse,hashlib,json
from pathlib import Path

def snapshot(root,groups):
 result={}
 for group in groups:
  path=root/group
  files=path.rglob('*') if path.is_dir() else [path]
  for file in files:
   if file.is_file() and '__pycache__' not in file.parts:
    result[file.relative_to(root).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
 return result

INPUTS=['game','include','platform','tools/xsdk','tools/ctr360/build_360_mirror.py','tools/ctr360/audit_endian_source.py']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--prepared',type=Path,required=True);a=p.parse_args()
 manifest=json.loads((a.prepared/'_xsdk_manifest.json').read_text())
 if manifest['input']!=snapshot(a.root,INPUTS):raise SystemExit('source changed during build; rebuild')
 if manifest['prepared']!=snapshot(a.prepared,['game','include','platform']):raise SystemExit('prepared source changed during build; rebuild')
 print('Open SDK source snapshot verified')
