"""CTR360 disc converter for the portable Windows package.

Converts your own Crash Team Racing (USA) disc image into the byte order the
Xbox 360 build reads and writes apps\\ctr360\\assets\\ctr-u.bin beside the
converter folder, in the app folder as it goes on the console. The original
image is only read.

Run "Convert disc image.bat" and choose the image, or drop its .cue or .bin
onto the .bat. package.py lays out the package; in the source tree the cooker
is found in tools/ctr360.
"""
import argparse
import contextlib
import ctypes
import hashlib
import os
import re
import shutil
import struct
import sys
import traceback
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
for tools in (HERE / 'tools', HERE.parent / 'ctr360'):
    if (tools / 'cook_disc.py').is_file():
        sys.path.insert(0, str(tools))
        break

SECTOR = 2352
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'
SERIAL = b'SCUS_944.26'
COMPRESSED = {'.chd', '.pbp', '.ecm', '.cso', '.7z', '.zip', '.rar'}
DIALOG_TITLE = 'Choose your Crash Team Racing (USA) disc image'
# SHA-256 of the converted image this release was tested with. Other good
# dumps can differ in sectors the game never reads; they are accepted when
# every conversion check passes.
TESTED_CONVERSION = '8409cc0c50916ab01b6b76bf822934f9b024377efda088c004b0a90adb76ffdd'


class Failure(Exception):
    pass


class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [('lStructSize', wintypes.DWORD), ('hwndOwner', wintypes.HWND),
                ('hInstance', wintypes.HINSTANCE), ('lpstrFilter', ctypes.c_void_p),
                ('lpstrCustomFilter', ctypes.c_void_p), ('nMaxCustFilter', wintypes.DWORD),
                ('nFilterIndex', wintypes.DWORD), ('lpstrFile', ctypes.c_void_p),
                ('nMaxFile', wintypes.DWORD), ('lpstrFileTitle', ctypes.c_void_p),
                ('nMaxFileTitle', wintypes.DWORD), ('lpstrInitialDir', ctypes.c_void_p),
                ('lpstrTitle', ctypes.c_void_p), ('Flags', wintypes.DWORD),
                ('nFileOffset', wintypes.WORD), ('nFileExtension', wintypes.WORD),
                ('lpstrDefExt', ctypes.c_void_p), ('lCustData', wintypes.LPARAM),
                ('lpfnHook', ctypes.c_void_p), ('lpTemplateName', ctypes.c_void_p),
                ('pvReserved', ctypes.c_void_p), ('dwReserved', wintypes.DWORD),
                ('FlagsEx', wintypes.DWORD)]


def wide(text):
    # Built per character so the filter's embedded NULs survive.
    return (ctypes.c_wchar * len(text))(*text)


def browse():
    """Show the standard Windows open dialog; None when cancelled."""
    with contextlib.suppress(Exception):
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    ctypes.windll.ole32.CoInitializeEx(None, 2)
    filters = wide('Disc images (*.cue, *.bin)\0*.cue;*.bin\0All files (*.*)\0*.*\0\0')
    title = wide(DIALOG_TITLE + '\0')
    name = ctypes.create_unicode_buffer(32768)
    dialog = OPENFILENAMEW()
    dialog.lStructSize = ctypes.sizeof(dialog)
    dialog.lpstrFilter = ctypes.addressof(filters)
    dialog.nFilterIndex = 1
    dialog.lpstrFile = ctypes.addressof(name)
    dialog.nMaxFile = len(name)
    dialog.lpstrTitle = ctypes.addressof(title)
    # FILEMUSTEXIST | PATHMUSTEXIST | HIDEREADONLY | NOCHANGEDIR | EXPLORER | DONTADDTORECENT
    dialog.Flags = 0x1000 | 0x800 | 0x4 | 0x8 | 0x80000 | 0x2000000
    open_dialog = ctypes.windll.comdlg32.GetOpenFileNameW
    open_dialog.argtypes = [ctypes.POINTER(OPENFILENAMEW)]
    if open_dialog(ctypes.byref(dialog)):
        return Path(name.value)
    error = ctypes.windll.comdlg32.CommDlgExtendedError()
    if error:
        raise Failure('The file dialog could not open (error 0x%x). Drop the image onto "Convert disc image.bat" instead.' % error)
    return None


def resolve_cue(cue):
    """The data track's .bin named by a cue sheet."""
    lines = cue.read_text(errors='replace').splitlines()
    files = [line.strip()[5:].strip() for line in lines if line.strip().upper().startswith('FILE ')]
    tracks = [line.split()[2:3] for line in lines if line.strip().upper().startswith('TRACK ')]
    if not files or not tracks:
        raise Failure('The cue sheet names no disc image.')
    if tracks[0] != ['MODE2/2352']:
        raise Failure('The cue sheet\'s first track is not a 2352-byte PlayStation data track.')
    entry = files[0]
    name = entry[1:entry.index('"', 1)] if entry.startswith('"') else entry.rsplit(' ', 1)[0]
    disc = cue.parent / name
    if not disc.is_file():
        raise Failure('The cue sheet refers to "%s", which is not beside it.' % name)
    return disc


def check_disc(disc):
    """Reject anything but an original NTSC-U raw dump, with a reason."""
    from iso_bigfile import IsoImage
    if disc.suffix.lower() in COMPRESSED:
        raise Failure('%s files are compressed. Extract or convert the image back to .cue/.bin first.' % disc.suffix)
    with open(disc, 'rb') as f:
        head = f.read(len(SYNC))
    if head != SYNC or disc.stat().st_size % SECTOR:
        raise Failure('This is not a raw disc image with 2352-byte sectors. Choose the .cue or .bin of a '
                      'full disc dump; .iso files with 2048-byte sectors cannot be converted.')
    try:
        iso = IsoImage(str(disc))
    except ValueError:
        raise Failure('The image has no readable PlayStation data track.') from None
    try:
        cnf = iso.find('SYSTEM.CNF')
        boot = iso.read(cnf.lba, min(cnf.size, 2048)).upper() if cnf and not cnf.is_dir else b''
        big = iso.find('BIGFILE.BIG')
        header = iso.read(big.lba, 8) if big else b''
    finally:
        iso.close()
    if SERIAL not in boot:
        serial = re.search(rb'[A-Z]{4}_\d{3}\.\d{2}', boot)
        raise Failure('This is not the USA release of Crash Team Racing (SCUS-94426)%s. '
                      'Other regions are not supported.' % (' but %s' % serial.group().decode() if serial else ''))
    if len(header) < 8:
        raise Failure('BIGFILE.BIG is missing; the image is incomplete.')
    if not 0 < struct.unpack_from('<i', header, 4)[0] < 0x10000:
        if 0 < struct.unpack_from('>i', header, 4)[0] < 0x10000:
            raise Failure('This image has already been converted. Choose your original disc dump instead.')
        raise Failure('BIGFILE.BIG is damaged.')


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def ask(question):
    try:
        return input(question + ' [y/N] ').strip().lower() in ('y', 'yes')
    except EOFError:
        return False


def convert(disc, game, replace):
    if disc.suffix.lower() == '.cue':
        disc = resolve_cue(disc)
    target = game / 'assets' / 'ctr-u.bin'
    if target.exists() and target.resolve() == disc.resolve():
        raise Failure('That is the converted image. Choose your original disc dump instead.')
    print('Image: %s' % disc)
    check_disc(disc)
    work = HERE / 'work'
    work.mkdir(exist_ok=True)
    need = disc.stat().st_size + (64 << 20)
    if shutil.disk_usage(work).free < need:
        raise Failure('Not enough free space: about %d MB is needed on this drive.' % (need >> 20))
    if target.exists() and not replace and not ask('%s already exists. Replace it?' % target):
        raise Failure('Kept the existing converted image.')
    partial = work / 'ctr-u.bin.partial'
    log = work / 'convert.log'
    print('Converting. This takes a few minutes...')
    try:
        import cook_disc
        argv = sys.argv
        with open(log, 'w', encoding='utf-8') as out, contextlib.redirect_stdout(out):
            sys.argv = ['cook_disc.py', '--disc', str(disc), '--out', str(partial)]
            try:
                cook_disc.main()
            except SystemExit as e:
                if e.code not in (None, 0):
                    print(e.code)
                    raise Failure('The conversion failed: %s\nDetails: %s' % (e.code, log)) from None
            except Exception:
                traceback.print_exc()
                raise Failure('The conversion failed unexpectedly. Details: %s' % log) from None
            finally:
                sys.argv = argv
        tested = digest(partial) == TESTED_CONVERSION
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(partial, target)
        except OSError:
            shutil.move(str(partial), str(target))
    finally:
        with contextlib.suppress(OSError):
            partial.unlink()
    print('\nConverted image: %s' % target)
    if tested:
        print('It matches the image this release was tested with.')
    else:
        print('Your dump differs from the one this release was tested with, but every conversion check passed.')
    print('\nNext, copy the apps folder to the root of your Xbox 360\'s hard drive (Hdd1 over FTP)\n'
          'and start apps\\%s\\default.xex. If the Homebrew App Store installed CTR360, copy\n'
          'only assets\\ctr-u.bin to hdd:\\apps\\%s\\assets\\ on the console.' % (game.name, game.name))


def main():
    ap = argparse.ArgumentParser(description='Convert your Crash Team Racing (USA) disc image for CTR360.')
    ap.add_argument('image', nargs='?', type=Path, help='.cue or raw .bin; a file dialog opens when omitted')
    ap.add_argument('--game', type=Path, default=HERE.parent / 'apps' / 'ctr360',
                    help='game folder that receives assets/ctr-u.bin')
    ap.add_argument('--yes', action='store_true', help='replace an existing converted image without asking')
    a = ap.parse_args()
    print('CTR360 disc converter\n')
    try:
        disc = a.image
        if disc is None:
            print('Choose your disc image in the window that opened.')
            disc = browse()
            if disc is None:
                print('No image chosen.')
                return 1
        if not disc.is_file():
            raise Failure('%s does not exist.' % disc)
        convert(disc.resolve(), a.game.resolve(), a.yes)
    except Failure as e:
        print('\n%s' % e)
        return 1
    except KeyboardInterrupt:
        print('\nCancelled.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
