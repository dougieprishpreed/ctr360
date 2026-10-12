"""Read-only comparison with the reference's annotated frame-rate expressions.

Matches whole macro arguments in aligned function tokens; never imports a
reference function or overwrites port-specific repairs. Emits proposed sites
for review; applying them is a separate explicit operation.
"""
import difflib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT.parent / 'repos/CTR-in-C/src/decompile/General'
TOKEN = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b0[xX][\da-fA-F]+\b|\b\d+\b|[a-zA-Z_]\w*|>>|<<|->|\+\+|--|==|!=|<=|>=|&&|\|\||\S', re.S)
FPS = {'FPS_DOUBLE', 'FPS_HALF', 'FPS_LEFTSHIFT', 'FPS_RIGHTSHIFT'}

def tokens(text):
    out = []
    for m in TOKEN.finditer(text):
        value = m.group()
        if value.startswith(('//', '/*')):
            continue
        if value.startswith('DECOMP_'):
            value = value[7:]
        if re.fullmatch(r'0[xX][\da-fA-F]+|\d+', value):
            value = str(int(value, 0) if value.lower().startswith('0x') else int(value))
        out.append((value, m.start(), m.end()))
    return out

def functions(text):
    result = {}
    for m in re.finditer(r'^\s*(?:[\w*]+\s+)+(?P<name>\w+)\s*\([^;{}]*\)\s*\{', text, re.M):
        start = m.end() - 1
        depth = 0
        for value, a, b in tokens(text[start:]):
            if value == '{': depth += 1
            elif value == '}': depth -= 1
            if depth == 0:
                name = m['name'].removeprefix('DECOMP_')
                result[name] = (start, text[start:start+b])
                break
    return result

def baseline(ts):
    out, calls = [], []
    i = 0
    while i < len(ts):
        if ts[i][0] in FPS and i + 1 < len(ts) and ts[i+1][0] == '(':
            j, depth = i + 2, 1
            while j < len(ts):
                if ts[j][0] == '(': depth += 1
                elif ts[j][0] == ')': depth -= 1
                if depth == 0: break
                j += 1
            first = len(out)
            out.extend(t[0] for t in ts[i+2:j])
            calls.append((ts[i][0], first, len(out)))
            i = j + 1
        else:
            out.append(ts[i][0])
            i += 1
    return out, calls

current = {}
for p in (ROOT/'game').rglob('*.c'):
    text = p.read_text(encoding='utf-8', errors='replace')
    for name, (start, body) in functions(text).items():
        current[name] = (p, start, body, text)

matched, unmatched, absent = [], [], []
for p in REF.rglob('*.c'):
    ref = p.read_text(encoding='utf-8', errors='replace')
    if not any(word in ref for word in FPS): continue
    for name, (_, body) in functions(ref).items():
        a, calls = baseline(tokens(body))
        if not calls: continue
        if name not in current:
            absent.append({'function': name, 'reference': str(p.relative_to(REF)), 'count': len(calls)})
            continue
        target, start, curbody, full = current[name]
        ts = tokens(curbody)
        b = [t[0] for t in ts]
        blocks = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks()
        for macro, first, last in calls:
            hit = next((blk for blk in blocks if blk.a <= first and last <= blk.a+blk.size and blk.size >= (last-first)+8), None)
            item = {'function': name, 'macro': macro, 'arg': ' '.join(a[first:last]), 'reference': str(p.relative_to(REF)), 'file': str(target.relative_to(ROOT))}
            if hit is None:
                unmatched.append(item)
                continue
            lo, hi = hit.b + first - hit.a, hit.b + last - hit.a
            begin, end = start + ts[lo][1], start + ts[hi-1][2]
            item.update(start=begin, end=end, original=full[begin:end], line=full[:begin].count('\n')+1, aligned_tokens=hit.size)
            matched.append(item)

report = {'matched': matched, 'unmatched': unmatched, 'absent': absent}
out = ROOT/'build-360/results/20261011-fps-annotation-audit.json'
out.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'matched':len(matched),'unmatched':len(unmatched),'absent_calls':sum(x['count'] for x in absent),'files':len(set(x['file'] for x in matched)), 'report':str(out)}))
