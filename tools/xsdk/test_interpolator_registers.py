"""Check that every bundled pixel shader declares a register for each interpolator its vertex shader exports.

xsdk links GLSL shaders by location without trimming a vertex shader's exports, and Xenos writes every exported
interpolator into a pixel group's registers. A pixel shader declaring fewer registers spills the rest into another
group's: on the console the flat variant (one register, behind psx.vert's four interpolators) turned the tails of
textured draws before it pure blue or black.
"""
import argparse
import re
import struct
import sys
from pathlib import Path

# SQ_PROGRAM_CNTL's fields (xenia:src/xenia/gpu/registers.h:136-150): registers less one, interpolators less one.
PS_REGS_SHIFT, REGS_MASK = 8, 0x3F
VS_EXPORT_COUNT_SHIFT, EXPORT_COUNT_MASK = 20, 0xF


def interpolators(vertex_control):
    return (vertex_control >> VS_EXPORT_COUNT_SHIFT & EXPORT_COUNT_MASK) + 1


def pixel_registers(pixel_control):
    return (pixel_control >> PS_REGS_SHIFT & REGS_MASK) + 1


def covered(vertex_control, pixel_control):
    return pixel_registers(pixel_control) >= interpolators(vertex_control)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xsdk', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.xsdk / 'xenos-toolchain'))
    from xdis import container

    source = args.bundle.read_text()
    programs = {}
    for name, raw in re.findall(r'uint32_t (\w+)_container\[\] = \{(.*?)\};', source, re.S):
        words = [int(x, 16) for x in re.findall(r'0x([0-9A-F]+)', raw)]
        programs[name] = container.Container(struct.pack('>%dI' % len(words), *words))
    # Broken on purpose: the flat variant as it was, one register behind four interpolators.
    assert not covered(0x00310006, 0x10000000) and covered(0x00310006, 0x10000300)
    pairs = 0
    for family in ('psx', 'quad'):
        vertex = [n for n in programs if n.startswith(family + '_vert')]
        pixel = [n for n in programs if n.startswith(family + '_') and n.endswith('_frag')]
        assert vertex and pixel, family
        for v in vertex:
            assert programs[v].shader_type == 'vertex', v
            for p in pixel:
                assert programs[p].shader_type == 'pixel', p
                vc, pc = programs[v].program_control, programs[p].program_control
                assert covered(vc, pc), '%s declares %d registers behind %s exporting %d interpolators' % (
                    p, pixel_registers(pc), v, interpolators(vc))
                pairs += 1
    print('PASS: %d bundled vertex/pixel pairings: each pixel shader declares a register for every exported '
          'interpolator (the flat variant no longer spills into textured pixel groups)' % pairs)


if __name__ == '__main__':
    main()
