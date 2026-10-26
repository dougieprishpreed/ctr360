"""Lay out the portable Windows package: the game folder and a disc converter.

    Convert disc image.bat   opens a file dialog and converts the chosen dump
    READ ME FIRST.txt
    converter/               convert.py, the cooker, embeddable CPython
    ctr360-xsdk/             default.xex, ctr360.ini, notices; assets/ gets ctr-u.bin

--dist is the build's dist/ folder (default.xex, licenses/, LICENSE.txt,
THIRD_PARTY_NOTICES.txt, ctr360.example.ini, shipped as ctr360.ini). The pinned Python embeddable
archive is downloaded unless --python supplies it; either way its hash must
match. --zip also writes the package as one archive.
"""
import argparse
import hashlib
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

PYTHON_URL = 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip'
PYTHON_SHA256 = '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
COOKER = ('cook_disc.py', 'iso_bigfile.py', 'audit_endian_assets.py', 'audit_endian_levels.py')
GAME = 'ctr360-xsdk'
DIST = ('default.xex', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.txt', 'ctr360.example.ini')
# The release ships the example settings ready to use.
RENAME = {'ctr360.example.ini': 'ctr360.ini'}

LAUNCHER = r'''@echo off
rem Converts your own Crash Team Racing (USA) disc image for CTR360.
title CTR360 disc converter
"%~dp0converter\python\python.exe" -I -X utf8 "%~dp0converter\convert.py" %*
echo.
pause
'''

READ_ME = r'''CTR360 for Xbox 360

You need your own Crash Team Racing disc image: the USA release
(SCUS-94426), dumped as .cue/.bin with 2352-byte sectors.

1. Double-click "Convert disc image.bat" and choose the .cue or .bin file,
   or drop the file onto the .bat. Your image is only read; the converted
   copy is written to ctr360-xsdk\assets\ctr-u.bin. Conversion takes a few
   minutes and about 700 MB of free space.
2. Copy the whole ctr360-xsdk folder to writable USB or HDD storage on your
   Xbox 360, then launch default.xex from your dashboard.

Updating an existing installation: convert your image with the new package
too, then copy its ctr360-xsdk folder over the old one. Your saves
(memcards) are kept. To keep your own settings, skip replacing ctr360.ini
when Windows asks.

Back + Start exits the game. Settings are in ctr360-xsdk\ctr360.ini; each
one is described there.

The converter runs on 64-bit Windows 10 or 11 without installation. It
includes the official Python embeddable package; see
converter\python\LICENSE.txt.
'''

GAME_README = ('CTR360 for Xbox 360, built with the open xSDK and vulkan4xenon.\n'
               'Copy this whole folder to writable USB/HDD storage and launch default.xex.\n'
               'Back+Start exits. Keep memcards/ and ctr360.ini when updating.\n')


def crlf(text):
    return text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8')


def python_archive(path):
    data = path.read_bytes() if path else urllib.request.urlopen(PYTHON_URL, timeout=120).read()
    if hashlib.sha256(data).hexdigest() != PYTHON_SHA256:
        raise SystemExit('Python embeddable archive does not match the pinned SHA-256')
    return zipfile.ZipFile(io.BytesIO(data))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dist', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True, help='package folder to create (must not exist)')
    ap.add_argument('--python', type=Path, help='local copy of the pinned embeddable archive')
    ap.add_argument('--zip', type=Path, help='also write the package as this .zip')
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    missing = [n for n in DIST + ('licenses',) if not (a.dist / n).exists()]
    if missing:
        raise SystemExit('dist folder lacks: ' + ', '.join(missing))
    a.out.mkdir(parents=True)

    (a.out / 'Convert disc image.bat').write_bytes(crlf(LAUNCHER))
    (a.out / 'READ ME FIRST.txt').write_bytes(crlf(READ_ME))
    converter = a.out / 'converter'
    (converter / 'tools').mkdir(parents=True)
    shutil.copy2(root / 'tools/xsdk/convert.py', converter / 'convert.py')
    for name in COOKER:
        shutil.copy2(root / 'tools/ctr360' / name, converter / 'tools' / name)
    shutil.copy2(root / 'LICENSE', converter / 'LICENSE.txt')
    python_archive(a.python).extractall(converter / 'python')

    game = a.out / GAME
    (game / 'assets').mkdir(parents=True)
    for name in DIST:
        shutil.copy2(a.dist / name, game / RENAME.get(name, name))
    shutil.copytree(a.dist / 'licenses', game / 'licenses')
    (game / 'README.txt').write_bytes(crlf(GAME_README))

    if a.zip:
        with zipfile.ZipFile(a.zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for path in sorted(a.out.rglob('*')):
                z.write(path, path.relative_to(a.out).as_posix())
        print('%s  %s' % (hashlib.sha256(a.zip.read_bytes()).hexdigest(), a.zip))
    print(a.out.resolve())


if __name__ == '__main__':
    main()
