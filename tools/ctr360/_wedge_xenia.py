import collections

XL = r'F:/downloads/xenia_canary_windows/xenia.log'
lines = open(XL, 'r', errors='replace').read().splitlines()
print("xenia.log lines:", len(lines))

# ODS records look like: "d> F8000008 RtlInitAnsiString(7018E780, 7018E7E0([trace] walk#23 ..."
hits = [i for i, l in enumerate(lines) if 'walk#' in l and 'pkt=' in l]
print("lines containing walk# + pkt=:", len(hits))

per = collections.defaultdict(list)
for i in hits:
    l = lines[i]
    a = l.find('walk#')
    seg = l[a:]
    seg = seg.split('\\r')[0].rstrip(')')
    toks = seg.split(' ')
    try:
        walk = int(toks[0][5:])
        addr = int(toks[1][4:], 16)
        ln = int(toks[2][4:])
        code = int(toks[3][5:], 16)
        tag = int(toks[4][4:], 16)
    except Exception:
        continue
    per[walk].append((i, addr, ln, code, tag))

print("walks in xenia.log:", sorted(per.keys()))
print("counts:", {k: len(v) for k, v in sorted(per.items())})

# last walk and its final lines
lastwalk = max(per.keys())
w = per[lastwalk]
print("last walk #%d packets=%d" % (lastwalk, len(w)))
print("final 5 packets:")
for idx, a, ln, c, t in w[-5:]:
    print("   xline %d addr=%08x len=%d code=%02x tag=%08x" % (idx + 1, a, ln, c, t))

# what follows the last walk packet line?
li = w[-1][0]
print("context AFTER last walk packet line in xenia.log:")
for j in range(li, min(li + 30, len(lines))):
    s = lines[j]
    if 'pump callbacks' in s:
        print("   xline %d: <audio pump, first occurrence>" % (j + 1))
        break
    print("   xline %d: %s" % (j + 1, s[:150]))

# is the last packet's prim line present?
primlines = [i for i, l in enumerate(lines) if 'prim code=00 len=2 primLength=3' in l]
print("xenia.log lines with 'prim code=00 len=2 primLength=3':", len(primlines))
for i in primlines[:3]:
    print("   xline %d: %s" % (i + 1, lines[i][:160]))
print("context after FIRST such line:")
i0 = primlines[0] if primlines else None
if i0 is not None:
    for j in range(i0, min(i0 + 12, len(lines))):
        print("   xline %d: %s" % (j + 1, lines[j][:150]))

# any error text at all in xenia.log?
for s in ['did not output valid', 'invalid OT link', 'unregistered linked', 'got invalid tag length', 'Unhandled zero length', 'Unhandled tagless', 'MAX_DRAW_SPLITS']:
    print("xenia.log '%s': %d" % (s, sum(1 for l in lines if s in l)))

# does xenia.log end with audio pumps / when?
print("last 3 xenia.log lines:")
for l in lines[-3:]:
    print("   ", l[:150])
print("count of 'pump callbacks' in xenia.log:", sum(1 for l in lines if 'pump callbacks' in l))
print("last pump line idx:", max(i for i, l in enumerate(lines) if 'pump callbacks' in l) + 1)
