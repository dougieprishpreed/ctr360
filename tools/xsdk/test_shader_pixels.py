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
    programs = [bundle_program(source, 'psx_%d_frag' % i) for i in range(14)]
    vram = [0] * (1024 * 512)
    palette = [((i * 1237 + 31) & 32767) | (32768 if i & 4 else 0) for i in range(256)]
    palette[0] = 0
    vram[480 * 1024 + 16:480 * 1024 + 272] = palette
    page = [64, 256, 16, 480]
    count = 0

    def read(x, y):
        return vram[(y % 512) * 1024 + x % 1024]

    def reference_word(fmt, x, y):
        x, y = (min(255, max(0, math.floor(c))) for c in (x, y))
        if fmt == 2:
            return read(page[0] + x, page[1] + y)
        packed = read(page[0] + (x // (4 if fmt == 0 else 2)), page[1] + y)
        index = (packed >> ((x % (4 if fmt == 0 else 2)) * (4 if fmt == 0 else 8))) & (15 if fmt == 0 else 255)
        return read(page[2] + index, page[3])

    def color(word):
        return [(word >> shift & 31) / 31 for shift in (0, 5, 10)]

    def check(shader, uv, flags=(0, 0, 0, 0), rgba=(1, 1, 1, 1), dither=0, dc=None, bounds=(0, 0, 255, 255)):
        nonlocal count
        blob, constants = programs[shader+bank]
        constants = dict(constants)
        constants.update({0: [0, 0, 512, 216], 1: [1, 256, 1 if bank else 0, 0], 2: flags, 3: [0, 0, 0, 0]})
        fetch_count = 0

        def sample(slot, coords):
            nonlocal fetch_count
            fetch_count += 1
            word = read(math.floor(coords[0] * 1024), math.floor(coords[1] * 512))
            return [(word & 255) / 255, (word >> 8) / 255, 0, 1]

        dc = uv if dc is None else dc
        got = simulate.run(blob, registers={0: [*rgba[:3],dc[1]], 1: [*uv,dc[0],dither],
                                           2: page, 3: list(bounds)}, constants=constants, texture_fetch=sample)
        sample_uv=tuple(min(255,max(0,c+1/4096)) for c in uv)
        if shader < 6 and shader & 1:
            # Filtered taps keep inside the triangle's texel range, whose
            # maximum is exclusive (the next image in the page starts there).
            sample_uv=tuple(min(max(lo,hi-1),max(lo,c)) for c,lo,hi in zip(sample_uv,bounds[:2],bounds[2:]))
        nearest = reference_word(shader // 2, *sample_uv) if shader < 6 else 32767
        stp = bool(nearest & 32768)
        killed = shader < 6 and (nearest == 0 or (flags[0] == 1 and stp) or (flags[0] == 2 and not stp))
        assert got.killed == killed, (shader, uv, flags, nearest, got.killed)
        if not killed:
            expected = color(nearest)
            if shader < 6 and shader & 1:
                x, y = map(math.floor, sample_uv)
                fx, fy = sample_uv[0] - x, sample_uv[1] - y
                taps = [reference_word(shader // 2, x + dx, y + dy) for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
                weights = [(1-fx)*(1-fy), fx*(1-fy), (1-fx)*fy, fx*fy]
                weights = [weight if word else 0 for weight, word in zip(weights, taps)]
                expected = [sum(color(word)[ch]*weight for word, weight in zip(taps, weights))/max(sum(weights), 0.0001) for ch in range(3)]
            matrix = ((-4,0,-3,1),(2,-2,3,-1),(-3,1,-4,0),(3,-1,2,-2))
            noise = matrix[math.floor(dc[0]) % 4][math.floor(dc[1]) % 4]
            expected = [min(1,max(0,value*rgba[ch]+noise*dither*(bank!=0)/255)) for ch,value in enumerate(expected)]
            expected += [float(bool(flags[1] or (shader < 6 and flags[2] and stp)))]
            assert max(abs(a-b) for a, b in zip(got.exports[0], expected)) < 0.0001, (shader, uv, flags, got.exports, expected)
            # Four filtering taps, two fetches each for indexed formats.
            if shader < 6 and shader & 1:
                assert fetch_count <= (8 if shader < 4 else 4)
        count += 1

    for bank in (0,7):
        # The nearest nonzero texel remains visible even when transparent
        # neighbors make its filtered weight smaller than 0.0001.
        for fmt in range(3):
            vram[:] = [0] * len(vram)
            vram[480*1024+17] = 31
            vram[256*1024+64] = 31 if fmt == 2 else 1
            for uv in ((0.9995,0.9995),(0.999,0.999),(0.9995,0.5)):
                for flags in ((0,0,0,0),(1,1,0,0),(2,0,1,0)):
                    check(fmt*2+1,uv,flags)
            # Fully transparent nearest texels still discard.
            check(fmt*2+1,(1.5,1.5))
        vram[:] = [0] * len(vram)
        vram[480*1024+16:480*1024+272] = palette
        # All possible byte values in every nibble/byte lane. Palettes include zero,
        # opaque colors, STP colors, and nonzero texture-page/CLUT coordinates.
        for fmt in range(3):
            for byte in range(256):
                vram[256 * 1024 + 64] = byte | ((255-byte) << 8)
                for lane in range((4, 2, 1)[fmt]):
                    check(fmt * 2, (lane + 0.25, 0.25))
            # Neighboring texels, clamp at both UV edges, and transparent filtering.
            for y in (0, 1, 255):
                for x in range(256):
                    vram[(256+y)*1024 + 64+x] = ((x*733 + y*97) & 65535)
            for uv in ((0.5, 0.5), (1.25, 0.75), (2.5, 0.125), (255.75, 255.5), (-0.25, -0.5)):
                for filtering in range(2):
                    for flags in ((p,m,o,0) for p in range(3) for m in range(2) for o in range(2)):
                        check(fmt*2 + filtering, uv, flags)
        for flags in ((0, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)):
            check(6, (4.5, 4.5), flags)
        for shader in range(7):
            for dither in (0,1):
                for x in range(4):
                    for y in range(4):
                        for rgba in ((0.5,0.25,0.75,1),(2,1,0.5,1)):
                            check(shader,(2.5,0.5),rgba=rgba,dither=dither,dc=(x,y))
        # Physical VRAM wrap is now done by the repeat sampler. UV drift past
        # a 0/255 vertex byte (or the filtered sprite half-texel offset) clamps
        # to the page edge texel; it must not wrap to the opposite page edge.
        vram[:] = [(i*1237+31)&65535 for i in range(len(vram))]
        for page in ([960,256,1008,511],[960,512,1008,511],[0,0,0,0]):
            for shader in range(6):
                for uv in ((0.25,0.75),(255.75,255.5),(-0.25,-0.5),(256.5,256.5),
                           (-0.001,0.5),(0.5,-0.01),(-0.3,-0.3),(255.2,0.5),(-0.5,255.25)):
                    for flags in ((0,0,1,0),(1,1,0,0),(2,0,1,0)):
                        check(shader,uv,flags)
        page=[64,256,16,480]
        # A constant integer UV may arrive one float ULP below its intended
        # value after raster interpolation. The small sampling bias, as used
        # by the XDK path, must prevent selecting the preceding texel/mask.
        for n in (1,2,3,4,15,31,32,63,64,127,128,254,255):
            bits=struct.unpack('>I',struct.pack('>f',n))[0]
            below=struct.unpack('>f',struct.pack('>I',bits-1))[0]
            for shader in range(6):
                for uv in ((below,0.75),(0.5,below),(below,below)):
                    check(shader,uv)
        # Filtered far edges, corners and single-texel ranges never blend in
        # the texel at a range's exclusive maximum; a filtered sprite's first
        # column samples its own first texel rather than the one before it.
        vram[:] = [0] * len(vram)
        vram[480*1024+16:480*1024+272] = palette
        for y in range(48):
            for x in range(64):
                vram[(256+y)*1024 + 64+x] = ((x*733 + y*97) & 65535) | 1
        for fmt in range(3):
            for bounds in ((16,16,32,32),(20,8,21,40),(16,16,16,16),(3,5,9,6)):
                for uv in ((31.9,20.5),(20.5,31.9),(31.99,31.99),(15.7,20.2),(16.2,15.6),(20.9,8.5),(8.75,5.25),(3.0,5.0)):
                    check(fmt*2+1,uv,bounds=bounds)
                    check(fmt*2,uv,bounds=bounds)
        # Color carries at every five-bit boundary, including STP black.
        for word in sorted({0,32768,65535} | {max(0,min(65535,(n<<shift)+delta))
                          for shift in (5,10,15) for n in range(33) for delta in (-1,0,1)}):
            vram[256*1024+64]=word
            check(4,(0.25,0.75),(0,0,1,0))
    print('PASS: %d actual bundled pixel-shader cases: all packed lanes, palette/STP, transparency, filtering inside triangle texel ranges, UV edge clamp, flat colors' % count)


if __name__ == '__main__':
    main()
