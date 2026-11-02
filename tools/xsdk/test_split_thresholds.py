"""Multiplayer level drawers seed every threshold retail bakes into its 2P/3P/4P code.

Retail's 1P level drawer reads its depth thresholds from scratch, where the frame
setup (MainFrame_RenderFrame) writes them; the 2P, 3P and 4P drawers bake them into
their code as immediates. Native reuses the 1P helpers for every mode, so each
multiplayer drawer has to seed the same scratch slots itself. 2P left the far-block
fade start (scratch 0x2c) unseeded: it held about 1100 instead of retail's 5760,
every far block faded fully to its far colour with its split vertices folded in,
and 2P races showed dark checkered patches until the camera moved on.

Checks, against the retail templates (game/RenderLevel/psx): every scratch slot
the 1P drawer reads that 2P replaces with an immediate is seeded by the 2P drawer,
and the seeded values are exactly 2P's immediates; the 3P/4P immediates are the
values the split-ground seed writes. A 2P drawer without the fade seed is rejected.
"""
import argparse, re
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path); a = p.parse_args()
root = Path(__file__).resolve().parents[2]
def text(path): return (root / path).read_text().replace('\r\n', '\n')
full = text('game/RenderLevel/psx/DrawLevelOvr_full.inc').splitlines()
split = text('game/RenderLevel/psx/DrawLevelOvr_split.inc')
main_h = text('include/namespace_Main.h')
ovr1p = text('game/226/226_00_DrawLevelOvr1P.c')
ovr2p = text('game/227/227_00_DrawLevelOvr2P.c')

# Retail full template: scratch reads only 1P makes, and the immediates 2P uses instead.
reads, immediates, state = set(), set(), None
for line in full:
    s = line.strip()
    if s.startswith('.if') and 'players == 1' in s: state = '1p'; continue
    if s.startswith('.else'): state = '2p' if state == '1p' else None; continue
    if s.startswith('.endif'): state = None; continue
    m = re.match(r'lw\s+\$\d+,(\d+)\(\$1\)$', s)
    if state == '1p' and m and int(m.group(1)) < 0x30: reads.add(int(m.group(1)))
    m = re.match(r'addiu\s+\$\d+,\$\d+,-(\d+)$', s)
    if state == '2p' and m and int(m.group(1)) >= 0x100: immediates.add(int(m.group(1)))

offsets = {f: int(o, 16) for f, o in re.findall(r'offsetof\(struct MainRenderLevelGeometryScratch, (\w+)\) == (0x[0-9a-fA-F]+)', main_h)}

def seeded_2p(source):
    enum = {n: int(v, 16) for n, v in re.findall(r'(OVR227_\w+) = (0x[0-9a-fA-F]+)', source)}
    body = source[source.index('static void DrawLevelOvr2P_SeedSharedHelperThresholdScratch(void)'):]
    body = body[:body.index('\n}\n')]
    return {offsets[f]: enum[n] for f, n in re.findall(r'->(\w+) = (OVR227_\w+);', body)}

def check_2p(source):
    seeded = seeded_2p(source)
    assert reads <= set(seeded), ('1P scratch reads 2P leaves unseeded', sorted(hex(r) for r in reads - set(seeded)))
    assert set(seeded.values()) == immediates, (sorted(map(hex, seeded.values())), sorted(map(hex, immediates)))

assert reads == {0x14, 0x1c, 0x20, 0x24, 0x28, 0x2c}, sorted(map(hex, reads))
check_2p(ovr2p)
seeded = seeded_2p(ovr2p)
assert seeded[offsets['fullDynamicFadeDepthStart']] == 0x1540 + 0x140
print('PASS: 2P seeds every threshold retail bakes (depth scale, three texture LODs, near and recursive near, far fade 0x1680)')

# 3P/4P: one seed for all of them; its values are the split template's immediates.
body = ovr1p[ovr1p.index('static void DrawLevelOvr1P_SetSplitGroundThresholdScratch(void)'):]
body = body[:body.index('\n}\n')]
values = {int(v, 16) for v in re.findall(r'= (0x[0-9a-fA-F]+);', body)}
split_imm = {int(v) for v in re.findall(r'addiu\s+\$\d+,\$\d+,-(\d+)\n', split)}
assert values == {0x780, 0x640, 0x500, 0x280, 0x140} and values <= split_imm, (sorted(map(hex, values)), sorted(split_imm))
assert '.Lrender_full' not in split and '-5760' not in split
print('PASS: 3P/4P seed the split template\'s thresholds (0x780, 0x640, 0x500, 0x280, 0x140) and have no far fade')

unseeded = re.sub(r'\n\tDrawLevelOvr1P_RenderScratch\(\)->fullDynamicFadeDepthStart = OVR227_FULL_DYNAMIC_FADE_DEPTH_START;', '', ovr2p)
assert unseeded != ovr2p
try:
    check_2p(unseeded)
except AssertionError:
    print('PASS: a 2P drawer without the far fade seed rejected')
else:
    raise SystemExit('FAIL: unseeded fade accepted')
