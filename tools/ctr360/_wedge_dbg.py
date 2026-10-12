import re
LOG = r'F:/downloads/xenia_canary_windows/cache/ctr360.log'
lines = open(LOG, 'rb').read().split(b'\n')
s = lines[39899]
print([hex(b) for b in s[:40]])
print([chr(b) for b in s[:40]])
t = s.decode('ascii')
print("len", len(t))
# try progressively
for pat in ['walk#23', 'walk#', '#23', 'pkt=826ED938', 'len=0', 'code=00', 'tag=00edec68']:
    print(pat, '->', pat in t)
print(repr(t.split(' ')))
