import collections

LOG = r'F:/downloads/xenia_canary_windows/cache/ctr360.log'
MASK = 0xffffff
lines = open(LOG, 'r', errors='replace').read().splitlines()

# backslash-free parse: "[trace] walk#23 pkt=826ED938 len=0 code=00 tag=00edec68"
per = collections.defaultdict(list)
for i, l in enumerate(lines):
    if l.startswith('[trace] walk#') and ' pkt=' in l:
        toks = l.split(' ')
        try:
            walk = int(toks[1][5:])
            addr = int(toks[2][4:], 16)
            ln = int(toks[3][4:])
            code = int(toks[4][5:], 16)
            tag = int(toks[5][4:], 16)
        except Exception:
            continue
        per[walk].append((i, addr, ln, code, tag))

print("walks present:", sorted(per.keys()))
print("per-walk packet counts:", {k: len(v) for k, v in sorted(per.items())})
w = per[23]
print("walk#23 packets:", len(w))

print("-- first 14 --")
for idx, a, ln, c, t in w[:14]:
    print("  line %d addr=%08x len=%d code=%02x tag=%08x" % (idx + 1, a, ln, c, t))

print("-- last 24 --")
for idx, a, ln, c, t in w[-24:]:
    print("  line %d addr=%08x len=%d code=%02x tag=%08x" % (idx + 1, a, ln, c, t))

print("-- link mapping: host(next) - (tag(cur) & 0xffffff) --")
diffs = collections.Counter()
for (i1, a1, l1, c1, t1), (i2, a2, l2, c2, t2) in zip(w, w[1:]):
    diffs[(a2 - (t1 & MASK)) & 0xffffffff] += 1
print("  top values:", [(hex(k), v) for k, v in diffs.most_common(8)])

addrs = [a for _, a, _, _, _ in w]
print("-- address census --")
print("  min=%08x max=%08x" % (min(addrs), max(addrs)))
inot = [a for a in addrs if 0x826EC000 <= a <= 0x826EE000]
print("  in window 826EC000..826EE000: %d   outside: %d" % (len(inot), len(addrs) - len(inot)))
idx0 = next(i for i, (_, a, _, _, _) in enumerate(w) if 0x826EC000 <= a <= 0x826EE000)
print("  first OT-window packet at walk index %d addr=%08x" % (idx0, w[idx0][1]))
print("  transition:", ["%08x/c=%02x/l=%d" % (a, c, l) for _, a, l, c, _ in w[max(0, idx0 - 2):idx0 + 4]])
seq = addrs[idx0:]
print("  OT run strictly descending by 4 (len %d): %s" % (len(seq), all(seq[i] - seq[i + 1] == 4 for i in range(len(seq) - 1))))

print("-- ALL packets before the OT run (index 0..%d) --" % (idx0 - 1))
for idx, a, ln, c, t in w[:idx0]:
    print("  line %d addr=%08x len=%d code=%02x tag=%08x link=%06x" % (idx + 1, a, ln, c, t, t & MASK))

print("-- log lines around OT-run start --")
for i in range(w[idx0][0] - 2, min(w[idx0][0] + 6, len(lines))):
    print("  line %d: %s" % (i + 1, lines[i]))

w22 = per.get(22, [])
if w22:
    a22 = [a for _, a, _, _, _ in w22]
    print("-- walk#22 packets=%d min=%08x max=%08x" % (len(w22), min(a22), max(a22)))
    print("  walk#22 first 6:", ["%08x/c=%02x/l=%d" % (a, c, l) for _, a, l, c, _ in w22[:6]])
    print("  walk#22 last 6:", ["%08x/c=%02x/l=%d" % (a, c, l) for _, a, l, c, _ in w22[-6:]])

print("-- tail of walk#23 detail lines (all non-pkt lines after last packet) --")
lastpkt_line = w[-1][0]
for i in range(lastpkt_line, min(lastpkt_line + 6, len(lines))):
    print("  line %d: %s" % (i + 1, lines[i]))
