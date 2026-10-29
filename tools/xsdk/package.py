"""Lay out CTR360's release: the Homebrew App Store package and the zip for installing by hand.

    CTR360-Xbox360-<version>.zip    for installing by hand, with the disc converter:
        README.txt                  what the player supplies, where it goes and what to start
        Convert disc image.bat      opens a file dialog and converts the chosen dump
        converter/                  convert.py, the cooker, embeddable CPython
        apps/ctr360/                the app folder, as it goes at the root of the console's hard drive;
                                    the converter writes assets/ctr-u.bin into it
    ctr360-<version>.zip            the store package: the app folder's files at the zip's root, made by
                                    xsdk's tools/store_catalogue.py pack (--xsdk), which fills in the entry
    catalogue/                      catalogue.json holding that entry from tools/xsdk/store.json and
                                    ctr360-entry.json, the entry alone, for the catalogue's pull request

--dist is the build's dist/ folder (default.xex, licenses/, LICENSE.txt, THIRD_PARTY_NOTICES.txt,
ctr360.example.ini). The app folder holds no ctr360.ini: the store replaces every packaged file on
an update, so the game makes ctr360.ini from the example on its first start and keeps it. With --screenshot (a 1280x720 PNG or JPEG of
2 MB at most, taken on the console) the catalogue is checked as the store's maintainer checks it.
The pinned Python embeddable archive is downloaded unless --python supplies it; either way its
hash must match.
"""
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PYTHON_URL = 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip'
PYTHON_SHA256 = '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
COOKER = ('cook_disc.py', 'iso_bigfile.py', 'audit_endian_assets.py', 'audit_endian_levels.py')
DIST = ('default.xex', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.txt', 'ctr360.example.ini')
# The store's category for games played from the player's own copy, as its catalogue lists it.
PORTS = {'id': 'ports', 'name': 'Ports',
         'sentence': 'Games whose source is open, brought to the Xbox 360, played with your own copy of the game.'}
CATALOGUE_URL = 'https://xenosworks.github.io/homebrew-app-catalogue/catalogue.json'
ZIP_TIME = (2026, 1, 1, 0, 0, 0)

LAUNCHER = r'''@echo off
rem Converts your own Crash Team Racing (USA) disc image for CTR360.
title CTR360 disc converter
"%~dp0converter\python\python.exe" -I -X utf8 "%~dp0converter\convert.py" %*
echo.
pause
'''

READ_ME = r'''CTR360 for Xbox 360

You need an Xbox 360 that runs unsigned code (RGH or JTAG) and your own
Crash Team Racing disc image: the USA release (SCUS-94426), dumped as
.cue/.bin with 2352-byte sectors.

1. Double-click "Convert disc image.bat" and choose the .cue or .bin file,
   or drop the file onto the .bat. Your image is only read; the converted
   copy is written to apps\ctr360\assets\ctr-u.bin. Conversion takes a few
   minutes and about 700 MB of free space.
2. Copy the apps folder to the root of the console's hard drive, the drive
   FTP shows as Hdd1. If an apps folder is already there, copy ctr360 into
   it instead. A folder on USB storage works too.
3. Start apps\ctr360\default.xex from your dashboard.

If the Homebrew App Store installed CTR360, convert your image here and
copy only apps\ctr360\assets\ctr-u.bin to hdd:\apps\ctr360\assets\ on the
console.

Updating: copy the new ctr360 folder over the old one. Your saves
(memcards) and settings (ctr360.ini) are kept, and you only need to convert
your image again when the release notes say so.

Back + Start exits the game. Settings are in ctr360.ini beside
default.xex, which the game creates on its first start; each setting is
described there.

The converter runs on 64-bit Windows 10 or 11 without installation. It
includes the official Python embeddable package; see
converter\python\LICENSE.txt.
'''

GAME_README = r'''CTR360 for Xbox 360, built with the open xSDK and vulkan4xenon.

It needs assets\ctr-u.bin beside default.xex: your own Crash Team Racing
(USA, SCUS-94426) disc image, converted on a PC by the converter in the
CTR360-Xbox360 release zip.

Back + Start exits. Settings are in ctr360.ini, which the game creates
from ctr360.example.ini on its first start. Saves are kept in memcards\.
'''


def crlf(text):
    return text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8')


def python_archive(path):
    data = path.read_bytes() if path else urllib.request.urlopen(PYTHON_URL, timeout=120).read()
    if hashlib.sha256(data).hexdigest() != PYTHON_SHA256:
        raise SystemExit('Python embeddable archive does not match the pinned SHA-256')
    return zipfile.ZipFile(io.BytesIO(data))


def write_zip(folder, path):
    """Files only, in a fixed order and time, so the same folder always zips the same."""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for file in sorted((p for p in folder.rglob('*') if p.is_file()), key=lambda p: p.as_posix()):
            info = zipfile.ZipInfo(file.relative_to(folder).as_posix(), date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, file.read_bytes(), compresslevel=9)
    print('%s  %s' % (hashlib.sha256(path.read_bytes()).hexdigest(), path))


def app_folder(dist, folder):
    folder.mkdir(parents=True)
    for name in DIST:
        shutil.copy2(dist / name, folder / name)
    shutil.copytree(dist / 'licenses', folder / 'licenses')
    (folder / 'README.txt').write_bytes(crlf(GAME_README))
    long = [p for p in folder.rglob('*') if len(p.name) > 37]
    if long:
        raise SystemExit('names over the store\'s 37 characters: %s' % long)


def store(args, root, store_json, app, out):
    """The store package, made and described by xsdk's own tool, and the catalogue it goes in."""
    tool = args.xsdk / 'tools' / 'store_catalogue.py'
    entry = dict(store_json['entry'])
    version = store_json['version']
    package = out / ('%s-%s.zip' % (entry['id'], version))
    url = '%s/%s/%s' % (store_json['release_base'], store_json['release_tag'], package.name)
    catalogue_dir = out / 'catalogue'
    catalogue_dir.mkdir()
    catalogue = catalogue_dir / 'catalogue.json'
    if args.screenshot:
        shot = catalogue_dir / entry['screenshot']
        shot.parent.mkdir(parents=True)
        shutil.copy2(args.screenshot, shot)
        entry['screenshot_sha256'] = hashlib.sha256(shot.read_bytes()).hexdigest()
    catalogue.write_text(json.dumps({'format': 1, 'serial': 0, 'url': CATALOGUE_URL, 'categories': [PORTS],
                                     'apps': [entry]}, indent=2) + '\n')
    subprocess.run([sys.executable, str(tool), 'pack', str(catalogue), entry['id'], str(app), str(package),
                    '--url', url], check=True)
    packed = json.loads(catalogue.read_text())['apps'][0]
    if (packed['title_id'], packed['version']) != (store_json['title_id'], version):
        raise SystemExit('default.xex is %s %s, not store.json\'s %s %s' % (
            packed['title_id'], packed['version'], store_json['title_id'], version))
    (catalogue_dir / ('%s-entry.json' % entry['id'])).write_text(json.dumps(packed, indent=2) + '\n')
    if args.screenshot:
        subprocess.run([sys.executable, str(tool), 'check', str(catalogue), '--packages', str(out)], check=True)
    else:
        print('No --screenshot: the entry has no screenshot_sha256 yet, so the catalogue is not checked.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dist', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True, help='folder to create for the release (must not exist)')
    ap.add_argument('--python', type=Path, help='local copy of the pinned embeddable archive')
    ap.add_argument('--xsdk', type=Path, help='xsdk checkout, for the store package and its catalogue entry')
    ap.add_argument('--screenshot', type=Path, help='the store screenshot, 1280x720 PNG or JPEG from the console')
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    store_json = json.loads((root / 'tools/xsdk/store.json').read_text())
    version = store_json['version']
    missing = [n for n in DIST + ('licenses',) if not (a.dist / n).exists()]
    if missing:
        raise SystemExit('dist folder lacks: ' + ', '.join(missing))
    a.out.mkdir(parents=True)
    work = a.out / 'work'

    app = work / 'app'
    app_folder(a.dist, app)

    manual = work / 'manual'
    (manual / 'converter' / 'tools').mkdir(parents=True)
    (manual / 'Convert disc image.bat').write_bytes(crlf(LAUNCHER))
    (manual / 'README.txt').write_bytes(crlf(READ_ME))
    shutil.copy2(root / 'tools/xsdk/convert.py', manual / 'converter' / 'convert.py')
    for name in COOKER:
        shutil.copy2(root / 'tools/ctr360' / name, manual / 'converter' / 'tools' / name)
    shutil.copy2(root / 'LICENSE', manual / 'converter' / 'LICENSE.txt')
    python_archive(a.python).extractall(manual / 'converter' / 'python')
    shutil.copytree(app, manual / 'apps' / store_json['entry']['id'])
    write_zip(manual, a.out / ('CTR360-Xbox360-%s.zip' % version))

    if a.xsdk:
        store(a, root, store_json, app, a.out)
    print(a.out.resolve())


if __name__ == '__main__':
    main()
