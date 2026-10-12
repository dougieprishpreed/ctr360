"""ctr360: enable the two Xenia debug options that help this phase.
- [General] debug: retain debug information so the debugger UI is useful.
- [General] allow_game_relative_writes: game:\ becomes writable under Xenia,
  giving the build a second log/file target (real hardware cannot do this).
Backs the file up first."""
import io
import shutil

P = r'F:\downloads\xenia_canary_windows\xenia-canary.config.toml'
shutil.copyfile(P, P + '.bak-ctr360-2')

s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)

pairs = [
    ('debug = false                                    \t', 'debug = true                                     \t'),
    ('allow_game_relative_writes = false               \t', 'allow_game_relative_writes = true                \t'),
]

for old, new in pairs:
    hits = [i for i, line in enumerate(s.split(NL)) if line.startswith(old.split('  ')[0])]
    print('%-38s line hits=%d' % (old.split(' = ')[0], len(hits)))
    assert len(hits) == 1, (old, len(hits))
    lines = s.split(NL)
    lines[hits[0]] = new + lines[hits[0]][len(old):]
    s = NL.join(lines)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('config updated (backup: xenia-canary.config.toml.bak-ctr360-2)')
for line in s.split(NL):
    if line.startswith('debug = ') or line.startswith('allow_game_relative_writes = '):
        print('  ', line.split('#')[0].rstrip())
