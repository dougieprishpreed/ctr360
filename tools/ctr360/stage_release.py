"""Refresh releases/ctr360 without touching its memcards or player settings."""
from pathlib import Path
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parents[2]
source = root / 'build-360/xex/dist'
release_root = (root / 'build-360/releases').resolve()
release = release_root / 'ctr360'
release.mkdir(parents=True, exist_ok=True)
assert release.resolve().is_relative_to(release_root)

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def cards():
    return {str(p.relative_to(release / 'memcards')):
            {'size': p.stat().st_size, 'sha256': digest(p)}
            for p in (release / 'memcards').rglob('*') if p.is_file()}

before = cards()
files = ['default.xex', 'README.txt', 'assets/ctr-u.bin',
         'assets/ctr360_graphics.example.txt']
for name in files:
    src, dst = source / name, release / name
    assert src.is_file(), src
    assert dst.resolve().is_relative_to(release_root), dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_file() and digest(src) == digest(dst):
        continue
    pending = dst.with_name(dst.name + '.release-new')
    assert not pending.exists(), pending
    # Replace the directory entry, rather than overwriting a possible hardlink.
    try:
        shutil.copy2(src, pending)
        os.replace(pending, dst)
    finally:
        pending.unlink(missing_ok=True)

(release / 'memcards').mkdir(exist_ok=True)
assert cards() == before, 'release save files changed'
report = {'directory': str(release), 'memcards_unchanged': True,
          'memcard_files': len(before),
          'files': {name: {'size': (release / name).stat().st_size,
                           'sha256': digest(release / name)} for name in files}}
(root / 'build-360/results/release-current.json').write_text(
    json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
