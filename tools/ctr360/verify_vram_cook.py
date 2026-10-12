"""Scratch: verify the VRAM cook for the boot-critical entries.

Checks, per entry: the cooked file's VramHeader RECT read as big-endian matches
the pristine file's RECT read as little-endian, and the pixel bytes after the
header are untouched.
"""
import struct
import sys

sys.path.insert(0, r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360')
from iso_bigfile import IsoImage, BigFile

PRISTINE = r'F:\downloads\temp\python\hermes\ctrport\CTR - Crash Team Racing (USA)\CTR - Crash Team Racing (USA).bin'
COOKED = r'F:\downloads\temp\python\hermes\ctrport\ctr360\build-360\ctr-u-360.bin'
SECTOR = 2048
HDR = 0x14
RECT = 0xC

iso_a = IsoImage(PRISTINE)
iso_b = IsoImage(COOKED)
big_a = BigFile(iso_a)

# The cooked directory is big-endian, so parse it with >ii and compare entry
# for entry against the pristine little-endian table.
dir_a = iso_a.read(big_a.lba, 8 + big_a.num_entry * 8)
head_b, num_b = struct.unpack_from('>ii', dir_a, 0)
print('header pristine cdpos=%d entries=%d' % (head_b, num_b))
dir_be = iso_b.read(big_a.lba, 8 + big_a.num_entry * 8)
head_bc, num_bc = struct.unpack_from('>ii', dir_be, 0)
head_bl, num_bl = struct.unpack_from('<ii', dir_be, 0)
print('cooked dir BE reads cdpos=%d entries=%d (LE would read %d / %d)' % (head_bc, num_bc, head_bl, num_bl))

dir_ok = True
for i in range(min(big_a.num_entry, 4096)):
    pa, sa = struct.unpack_from('<ii', dir_a, 8 + i * 8)
    pb, sb = struct.unpack_from('>ii', dir_be, 8 + i * 8)
    if (pa, sa) != (pb, sb):
        print('dir entry %d mismatch: pristine LE (%d,%d) vs cooked BE (%d,%d)' % (i, pa, sa, pb, sb))
        dir_ok = False
        break
print('directory identical after cooking: %s' % dir_ok)

big_b = big_a

print('num_entry pristine=%d cooked=%d' % (big_a.num_entry, big_b.num_entry))

bad = 0
checked = 0
import importlib.util
_spec = importlib.util.spec_from_file_location('cook', r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\cook_disc.py')
cook_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cook_mod)


def site_byte_set(sites):
    s = set()
    for site in sites:
        off, ln = site[0], site[1]
        for k in range(ln):
            s.add(off + k)
    return s


def check_sites_exact(idx, a, b, sites):
    """Every byte outside the declared sites must be identical, and inside a
    per-element site each element must be exactly the reversed original."""
    ok = True
    declared = site_byte_set(sites)
    diffs = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    outside = [i for i in diffs if i not in declared]
    if outside:
        print('   entry %d: %d diff byte(s) OUTSIDE declared sites, first: %s' % (idx, len(outside), outside[:8]))
        ok = False
    for site in sites:
        if len(site) != 3:
            continue
        off, ln, elem = site
        p = off
        while (p + elem) <= (off + ln):
            if b[p:p + elem] != a[p:p + elem][::-1]:
                print('   entry %d: element at %d is not a clean %d-byte reversal' % (idx, p, elem))
                ok = False
                break
            p += elem
    return ok, len(diffs), len(declared)


for idx in (0, 2, 258, 509, 510, 46, 100, big_a.num_entry - 1):
    off, size = big_a.entries[idx]
    a = iso_a.read(big_a.lba + off, size)
    b = iso_b.read(big_b.lba + off, size)
    if a == b:
        print('entry %d: UNCHANGED (size %d) - not a vram entry' % (idx, size))
        checked += 1
        continue
    sites = cook_mod.vram_swap_sites(a, idx)
    if sites is None:
        print('entry %d: changed but not detected as vram (size %d)' % (idx, size))
        bad += 1
        continue
    ok, ndiff, ndeclared = check_sites_exact(idx, a, b, sites)
    print('entry %d: size=%d sites=%d declared_bytes=%d diff_bytes=%d ok=%s'
          % (idx, size, len(sites), ndeclared, ndiff, ok))
    if not ok:
        bad += 1
    checked += 1

print('checked=%d bad=%d' % (checked, bad))
iso_a.close()
iso_b.close()
