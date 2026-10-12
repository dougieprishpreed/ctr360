"""Line-wise fix: replace whatever the boot-trace insert line currently is with
a version that emits a real backslash-n escape into the generated C."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\tools\ctr360\build_360_mirror.py'
BS = chr(92)
s = io.open(P, encoding='utf-8', newline='').read()
NL = chr(13) + chr(10) if (chr(13) + chr(10)) in s else chr(10)
lines = s.split(NL)

hits = [i for i, ln in enumerate(lines) if 'lines.insert(at' in ln]
print('insert lines found:', len(hits))
for i in hits:
    print('  before:', repr(lines[i]))

new_line = ("            lines.insert(at, chr(9) + ('Platform_Log(\"[boot] ' + label + 'Qn\");').replace('Q', chr(92)))")
for i in hits:
    lines[i] = new_line

s2 = NL.join(lines)
io.open(P, 'w', encoding='utf-8', newline='').write(s2)
print('rewritten')

# sanity: import and check the generated text
import importlib.util
spec = importlib.util.spec_from_file_location('m', P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
lines = ['A', 'B']
lines.insert(1, chr(9) + ('Platform_Log("[boot] ' + 'X' + 'Qn");').replace('Q', chr(92)))
out = chr(10).join(lines)
print('sample:', repr(out))
assert chr(92) + 'n' in out
print('OK')
