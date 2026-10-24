"""Specialize packed formats and full-screen operations before xost compilation.

No per-pixel format dispatch: a flat primitive must not execute palette fetches.
The generated files live in the build directory, never in the source tree.
"""
import argparse
from pathlib import Path

def prepare(out):
    source = Path(__file__).resolve().parents[2] / 'platform/xsdk/shaders'
    out.mkdir(parents=True, exist_ok=True)
    for name in ('psx.vert', 'quad.vert'):
        (out / name).write_text((source / name).read_text(), newline='\n')
    for index in range(14):
        kind = index % 7
        text = (source / 'psx.frag').read_text()
        text = text.replace('#version 450', '#version 450\n#define XV_FORMAT %d\n#define XV_FILTER %d\n#define XV_DITHER %d' %
                            (kind // 2 if kind < 6 else 3, kind % 2 if kind < 6 else 0, index >= 7), 1)
        (out / ('psx_%d.frag' % index)).write_text(text, newline='\n')
    for mode in range(4):
        text = (source / 'quad.frag').read_text()
        text = text.replace('#version 450', '#version 450\n#define XV_MODE %d' % mode, 1)
        (out / ('quad_%d.frag' % mode)).write_text(text, newline='\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    prepare(parser.parse_args().out)
