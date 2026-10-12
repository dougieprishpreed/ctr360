import collections

LOG = r'F:/downloads/xenia_canary_windows/cache/ctr360.log'
MASK = 0xffffff
lines = open(LOG, 'r', errors='replace').read().splitlines()
per = collections.defaultdict(list)
for i, l in enumerate(lines):
    if l.startswith('[trace] walk#') and ' pkt=' in l:
        toks = l.split(' ')
        per[int(toks[1][5:])].append((i, int(toks[2][4:], 16), int(toks[3][4:]), int(toks[4][5:], 16), int(toks[5][4:], 16)))

w = per[23]
print("=== A. tag-vs-address identity (is the tag the node's OWN token?) ===")
own = sum(1 for _, a, _, _, t in w if (t & MASK) == (a & MASK))
print("  packets where (tag & 0xffffff) == (addr & 0xffffff): %d / %d" % (own, len(w)))
print("  => tag word is the node's own 24-bit token, NOT a link to the next node")

print("=== B. where the OT run starts (descending-by-4 chain) ===")
idx0 = next(i for i, (_, a, _, _, _) in enumerate(w) if 0x826EC000 <= a <= 0x826EE000)
seq = [a for _, a, _, _, _ in w[idx0:]]
print("  run start walk-index %d addr=%08x  run length %d" % (idx0, seq[0], len(seq)))
print("  strictly descending by 4:", all(seq[i] - seq[i + 1] == 4 for i in range(len(seq) - 1)))
print("  first addr %08x  last addr %08x  span %d words" % (seq[0], seq[-1], (seq[0] - seq[-1]) // 4 + 1))

print("=== C. the 3 packets OUTSIDE the OT window ===")
for idx, a, ln, c, t in w:
    if not (0x826EC000 <= a <= 0x826EE000):
        print("  walk-index %d line %d addr=%08x len=%d code=%02x tag=%08x" % (w.index((idx, a, ln, c, t)), idx + 1, a, ln, c, t))

print("=== D. link carried by the final packet's tag ===")
idx, a, ln, c, t = w[-1]
link = t & MASK
print("  final packet addr=%08x len=%d code=%02x tag=%08x" % (a, ln, c, t))
print("  tag>>24 = 0x%02x (len field)   tag & 0xffffff = 0x%06x (link token)" % (t >> 24, link))
print("  token 0x%06x vs OT-run token range: first=%06x last=%06x" % (link, seq[0] & MASK, seq[-1] & MASK))
print("  token is 4 BELOW the last-walked node token (%06x - 4 = %06x): %s" % (seq[-1] & MASK, (seq[-1] & MASK) - 4, link == (seq[-1] & MASK) - 4))
print("  => the link points at the NEXT OT slot down, which is the node we ALREADY visited")

print("=== E. endprim test on the final packet ===")
print("  isendprim = (token == 0xffffff): %s" % (link == 0xffffff))

print("=== F. walk#23 vs walk#22 (walk#22 completed) ===")
w22 = per[22]
print("  walk#22 packets=%d   walk#23 packets=%d   diff=%d" % (len(w22), len(w), len(w22) - len(w)))
print("  walk#22 final 3:", ["%08x/c=%02x/l=%d/tag=%08x" % (a, c, l, t) for _, a, l, c, t in w22[-3:]])
print("  walk#23 final 3:", ["%08x/c=%02x/l=%d/tag=%08x" % (a, c, l, t) for _, a, l, c, t in w[-3:]])

print("=== G. how many walk#23 packets have len>0 ===")
nz = [(idx, a, ln, c, t) for idx, a, ln, c, t in w if ln > 0]
print("  len>0 packets: %d" % len(nz))
for idx, a, ln, c, t in nz:
    print("    line %d addr=%08x len=%d code=%02x tag=%08x" % (idx + 1, a, ln, c, t))

print("=== H. walk#23 trace-line accounting (why the trace stops) ===")
tot = sum(1 for l in lines if l.startswith('[trace]'))
print("  total [trace] lines in log: %d" % tot)
print("  walk#23 trace lines emitted: %d" % sum(1 for l in lines if l.startswith('[trace] walk#23')))
print("  => budget is 60000 lines; log has %d trace lines, so the budget is NOT exhausted" % tot)
