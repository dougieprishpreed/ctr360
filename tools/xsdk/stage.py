"""Stage an independent xSDK console folder, preserving its saves/config."""
import argparse,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--xex',type=Path,required=True)
g=p.add_mutually_exclusive_group(required=True);g.add_argument('--assets',type=Path);g.add_argument('--cooked',type=Path)
p.add_argument('--out',type=Path,required=True);a=p.parse_args()
cooked=a.cooked if a.cooked else a.assets/'ctr-u.bin'
if not cooked.is_file():raise SystemExit('expected converted ctr-u.bin')
a.out.mkdir(parents=True,exist_ok=True);(a.out/'assets').mkdir(exist_ok=True);(a.out/'memcards').mkdir(exist_ok=True)
shutil.copytree(a.xex.parent/'licenses',a.out/'licenses',dirs_exist_ok=True)
root=Path(__file__).resolve().parents[2]
shutil.copy2(root/'LICENSE',a.out/'LICENSE.txt');shutil.copy2(root/'THIRD_PARTY_NOTICES.md',a.out/'THIRD_PARTY_NOTICES.txt')
shutil.copy2(a.xex,a.out/'default.xex');shutil.copy2(cooked,a.out/'assets/ctr-u.bin')
example=Path(__file__).resolve().parents[2]/'tools/ctr360/ctr360.example.ini'
shutil.copy2(example,a.out/'ctr360.example.ini')
if not (a.out/'ctr360.ini').exists():shutil.copy2(example,a.out/'ctr360.ini')
(a.out/'README.txt').write_text('CTR360 for Xbox 360, built with the open xSDK and vulkan4xenon.\nCopy this whole folder to writable USB/HDD storage and launch default.xex.\nBack+Start exits. Keep memcards/ and ctr360.ini when updating.\n')
print(a.out.resolve())
