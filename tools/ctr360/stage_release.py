"""Refresh releases/ctr360 without touching its memcards or player settings."""
from pathlib import Path
import hashlib
import json
import os
import re
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
         'ctr360.example.ini']
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

# Existing user INIs are never replaced. Migrate valid legacy graphics choices
# when creating the general configuration for the first time.
config = release / 'ctr360.ini'
if not config.exists():
    text = (release / 'ctr360.example.ini').read_text(encoding='utf-8')
    legacy = release / 'assets/ctr360_graphics.txt'
    if legacy.is_file():
        for key, value in re.findall(r'(?m)^\s*(interpolation|texture_filter|edge_aa)\s+([01])\s*$', legacy.read_text()):
            text = re.sub(r'(?m)^' + key + r' = [01]$', key + ' = ' + value, text)
    with config.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
(release / 'memcards').mkdir(exist_ok=True)
assert cards() == before, 'release save files changed'
report = {'directory': str(release), 'memcards_unchanged': True,
          'config_preserved_or_created': True,
          'memcard_files': len(before),
          'files': {name: {'size': (release / name).stat().st_size,
                           'sha256': digest(release / name)} for name in files}}
(root / 'build-360/results/release-current.json').write_text(
    json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
