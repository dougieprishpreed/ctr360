"""Check the shipped Xenos microcode against an independent PSX pixel model.

The xost simulator cannot establish console correctness or reproduce GPU timing.
It does catch numeric/lowering regressions in the actual bundled shaders.
"""
import argparse
import math
import re
import struct
import sys
from pathlib import Path


def bundle_program(source, name):
    raw = re.search(r'uint32_t ' + name + r'_container\[\] = \{(.*?)\};', source, re.S)[1]
    words = [int(x, 16) for x in re.findall(r'0x([0-9A-F]+)', raw)]
    constants = {}
    literals = re.search(name + r'_literals\[\] = \{(.*?)\};', source, re.S)
    if literals:
        for reg, values in re.findall(r'\{ (\d+), \{ (.*?) \} \}', literals[1]):
            constants[int(reg)] = [float(v.strip().removesuffix('f')) for v in values.split(',')]
    return struct.pack('>' + str(len(words)) + 'I', *words), constants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xsdk', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.xsdk / 'xenos-toolchain'))
    from xdis import simulate

    source = args.bundle.read_text()
    programs = [bundle_program(source, 'psx_%d_frag' % i) for i in range(7)]
    vram = [0] * (1024 * 512)
    palette = [((i * 1237 + 31) & 32767) | (32768 if i & 4 else 0) for i in range(256)]
    palette[0] = 0
    vram[480 * 1024 + 16:480 * 1024 + 272] = palette
    page = [64, 256, 16, 480]
    count = 0

    def read(x, y):
        return vram[(y % 512) * 1024 + x % 1024]

    def reference_word(fmt, x, y):
        x, y = math.floor(x) % 256, math.floor(y) % 256
        if fmt == 2:
            return read(64 + x, 256 + y)
        packed = read(64 + (x // (4 if fmt == 0 else 2)), 256 + y)
        index = (packed >> ((x % (4 if fmt == 0 else 2)) * (4 if fmt == 0 else 8))) & (15 if fmt == 0 else 255)
        return read(16 + index, 480)

    def color(word):
        return [(word >> shift & 31) / 31 for shift in (0, 5, 10)]

    def check(shader, uv, flags=(0, 0, 0, 0)):
        nonlocal count
        blob, constants = programs[shader]
        constants = dict(constants)
        constants.update({0: [0, 0, 512, 216], 1: [1, 256, 0, 0], 2: flags, 3: [0, 0, 0, 0]})
        fetch_count = 0

        def sample(slot, coords):
            nonlocal fetch_count
            fetch_count += 1
            word = read(math.floor(coords[0] * 1024), math.floor(coords[1] * 512))
            return [(word & 255) / 255, (word >> 8) / 255, 0, 1]

        got = simulate.run(blob, registers={0: [*uv, 1, 0], 1: [1, 1, 1, 1],
                                           2: [*uv, 0, 0], 3: page}, constants=constants, texture_fetch=sample)
        nearest = reference_word(shader // 2, *uv) if shader < 6 else 32767
        stp = bool(nearest & 32768)
        killed = shader < 6 and (nearest == 0 or (flags[0] == 1 and stp) or (flags[0] == 2 and not stp))
        assert got.killed == killed, (shader, uv, flags, nearest, got.killed)
        if not killed:
            expected = color(nearest)
            if shader < 6 and shader & 1:
                x, y = map(math.floor, uv)
                fx, fy = uv[0] - x, uv[1] - y
                taps = [reference_word(shader // 2, x + dx, y + dy) for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
                weights = [(1-fx)*(1-fy), fx*(1-fy), (1-fx)*fy, fx*fy]
                weights = [weight if word else 0 for weight, word in zip(weights, taps)]
                expected = [sum(color(word)[ch]*weight for word, weight in zip(taps, weights))/max(sum(weights), 0.0001) for ch in range(3)]
            expected += [float(bool(flags[1] or (shader < 6 and flags[2] and stp)))]
            assert max(abs(a-b) for a, b in zip(got.exports[0], expected)) < 0.0001, (shader, uv, flags, got.exports, expected)
            # Four filtering taps, two fetches each for indexed formats.
            if shader < 6 and shader & 1:
                assert fetch_count <= (8 if shader < 4 else 4)
        count += 1

    # All possible byte values in every nibble/byte lane. Palettes include zero,
    # opaque colors, STP colors, and nonzero texture-page/CLUT coordinates.
    for fmt in range(3):
        for byte in range(256):
            vram[256 * 1024 + 64] = byte | ((255-byte) << 8)
            for lane in range((4, 2, 1)[fmt]):
                check(fmt * 2, (lane + 0.25, 0.25))
        # Neighboring texels, wrap at both UV edges, and transparent filtering.
        for y in (0, 1, 255):
            for x in range(256):
                vram[(256+y)*1024 + 64+x] = ((x*733 + y*97) & 65535)
        for uv in ((0.5, 0.5), (1.25, 0.75), (2.5, 0.125), (255.75, 255.5), (-0.25, -0.5)):
            for filtering in range(2):
                for flags in ((0, 0, 0, 0), (1, 0, 0, 0), (2, 0, 1, 0), (0, 1, 0, 0)):
                    check(fmt*2 + filtering, uv, flags)
    for flags in ((0, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)):
        check(6, (4.5, 4.5), flags)
    print('PASS: %d actual bundled pixel-shader cases: all packed lanes, palette/STP, transparency, filtering, UV wrap, flat colors' % count)


if __name__ == '__main__':
    main()
