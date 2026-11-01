"""Convert disc images with the actual console converter (platform/native_disc_cook.c).

Synthetic images check the recipe's replay where it is hardest: fields across a
sector's end and across the converter's 1 MB reads, folded repeats, the last
sector, and the refusals (another image, another size, a damaged recipe), plus
finding the player's .bin. With --disc, --recipe and --expect, the player's
real image is converted too and must hash to the PC converter's image.
"""
import argparse
import hashlib
import os
import random
import subprocess
import sys
import zlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
p.add_argument('--cc', default='cc')
p.add_argument('--disc', type=Path)
p.add_argument('--recipe', type=Path)
p.add_argument('--expect')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'tools' / 'xsdk'))
from make_cook_recipe import apply, encode  # noqa: E402

OK, BAD_RECIPE, WRONG_SIZE, READ_FAILED, WRITE_FAILED, MISMATCH = range(6)
SECTOR, DATA = 2352, 2048
main = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "platform/native_disc_cook.h"
static unsigned calls, lastDone, lastTotal;
static void Progress(void *context, uint32_t done, uint32_t sectors){(void)context;calls++;lastDone=done;lastTotal=sectors;}
int main(int argc, char **argv){
 if (!strcmp(argv[1], "find")) {
  char out[512]; uint64_t bytes = 0;
  int found = NativeDiscCook_FindImage(argv[2], strtoull(argv[3], 0, 10), out, sizeof(out), &bytes);
  if (found) printf("%s %llu\n", out + strlen(argv[2]), (unsigned long long)bytes); else puts("none");
  return 0;
 }
 FILE *f = fopen(argv[2], "rb"); static unsigned char recipe[1 << 24]; size_t n = fread(recipe, 1, sizeof(recipe), f); fclose(f);
 struct NativeDiscCookRecipe r;
 if (!NativeDiscCook_OpenRecipe(&r, recipe, n)) { puts("result 1"); return 0; }
 int result = NativeDiscCook_Convert(&r, argv[3], argv[4], Progress, NULL);
 printf("result %d calls %u done %u of %u\n", result, calls, lastDone, lastTotal);
 return 0;
}
'''


def build(source, name):
    (a.out / (name + '.c')).write_text(source)
    exe = (a.out / name).resolve()
    subprocess.run([a.cc, '-std=gnu17', '-O2', '-w', '-I' + str(root / 'include'), '-I' + str(a.out),
                    str(a.out / (name + '.c')), str(a.out / (name + '-cook.c')), '-o', str(exe)], check=True)
    return exe


def convert(exe, recipe, image, out):
    r = subprocess.run([str(exe), 'convert', str(recipe), str(image), str(out)], capture_output=True, text=True,
                       check=True)
    words = r.stdout.split()
    return int(words[1]), words


converter = (root / 'platform/native_disc_cook.c').read_text()
(a.out / 'cook-cook.c').write_text(converter)
exe = build(main, 'cook')

# A disc of 1000 sectors: the converter reads 448 at a time and holds the last one back.
rng = random.Random(360)
sectors = 1000
image = bytearray(rng.getrandbits(8) for _ in range(sectors * SECTOR))
runs = [(100, 2, 10),                    # inside a sector
        (DATA * 5 - 2, 4, 1),            # a word across a sector's end
        (DATA * 6 - 1, 2, 1),            # a halfword across one, on an odd byte
        (DATA * 440 + 4, 2, DATA * 3),   # three sectors of halfwords
        (DATA * 448 - 2, 4, 1),          # across the sector the first read holds back
        (DATA * 448 + 10, 4, 3)]
# Quads: one field layout every 0x5c bytes, folded into a repeat.
base = DATA * 500 + 8
for q in range(200):
    at = base + q * 0x5c
    runs += [(at, 2, 10), (at + 0x14, 4, 1), (at + 0x2c, 2, 6), (at + 0x3c, 2, 1), (at + 0x48, 2, 10)]
runs += [(DATA * 700 - 6, 4, 5),         # words before, across and after a sector's end
         (DATA * 895 - 2, 4, 1),         # across the second read's held-back sector
         (DATA * sectors - 4, 4, 1)]     # the last word of the disc
runs.sort()
merged = []
for start, elem, count in runs:
    if merged and merged[-1][0] + merged[-1][1] * merged[-1][2] == start and merged[-1][1] == elem:
        merged[-1] = (merged[-1][0], elem, merged[-1][2] + count)
    else:
        merged.append((start, elem, count))
runs = merged
expected = bytearray(image)
straddling = apply(expected, runs)
assert straddling >= 5
crc = zlib.crc32(expected) & 0xffffffff
recipe = encode(runs, len(image), crc)
assert b'\0' in recipe[20:]  # the quads folded
(a.out / 'disc.bin').write_bytes(image)
(a.out / 'recipe.bin').write_bytes(recipe)
out = a.out / 'ctr-u.bin.part'

result, words = convert(exe, a.out / 'recipe.bin', a.out / 'disc.bin', out)
assert result == OK, words
assert out.read_bytes() == bytes(expected), 'converted bytes differ'
assert words[3] == '3' and words[5:] == [str(sectors), 'of', str(sectors)], words
print('PASS: %d runs (%d across a sector end, folded quads) convert exactly, in 3 reads' % (len(runs), straddling))

other = bytearray(image)
other[DATA * 300 + 7 + 24] ^= 1
(a.out / 'other.bin').write_bytes(other)
result, words = convert(exe, a.out / 'recipe.bin', a.out / 'other.bin', out)
assert result == MISMATCH and not out.exists(), words
(a.out / 'short.bin').write_bytes(image[:-SECTOR])
result, words = convert(exe, a.out / 'recipe.bin', a.out / 'short.bin', out)
assert result == WRONG_SIZE and not out.exists(), words
(a.out / 'damaged.bin').write_bytes(recipe[:-3])
result, words = convert(exe, a.out / 'damaged.bin', a.out / 'disc.bin', out)
assert result == BAD_RECIPE and not out.exists(), words
past = encode(runs + [(DATA * sectors, 2, 1)], len(image), crc)
(a.out / 'past.bin').write_bytes(past)
result, words = convert(exe, a.out / 'past.bin', a.out / 'disc.bin', out)
assert result == BAD_RECIPE and not out.exists(), words
print('PASS: another image, another size and damaged recipes are refused, leaving no file')

folder = a.out / 'app'
folder.mkdir(exist_ok=True)
for f in folder.iterdir():
    f.unlink()
(folder / 'notes.txt').write_bytes(b'x' * len(image))
finder = [str(exe), 'find', str(folder) + '/', str(len(image))]
assert subprocess.run(finder, capture_output=True, text=True).stdout.strip() == 'none'
(folder / 'small.BIN').write_bytes(b'x' * 100)
assert subprocess.run(finder, capture_output=True, text=True).stdout.strip() == 'small.BIN 100'
(folder / 'CTR - Crash Team Racing (USA).bin').write_bytes(image)
assert subprocess.run(finder, capture_output=True, text=True).stdout.strip() == \
    'CTR - Crash Team Racing (USA).bin %d' % len(image)
print('PASS: the .bin of the disc image\'s size is found, else any .bin, never another file')

# Writing every sector as read (no sector held back) loses the words across a read's end.
held = 'writeSectors = last ? held : held - 1;'
assert held in converter
(a.out / 'unheld-cook.c').write_text(converter.replace(held, 'writeSectors = held;').replace('carried = 1;', 'carried = 0;'))
unheld = build(main, 'unheld')
result, words = convert(unheld, a.out / 'recipe.bin', a.out / 'disc.bin', out)
assert result != OK, words
print('PASS: writing each read whole (words across a read\'s end lost) rejected')

if a.disc:
    exe_real = exe
    out_real = a.out / 'real-ctr-u.bin.part'
    result, words = convert(exe_real, a.recipe, a.disc, out_real)
    assert result == OK, words
    digest = hashlib.sha256()
    with open(out_real, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            digest.update(block)
    os.remove(out_real)
    assert digest.hexdigest() == a.expect.lower(), digest.hexdigest()
    print('PASS: the player\'s image converts to %s, the PC converter\'s image' % digest.hexdigest())
