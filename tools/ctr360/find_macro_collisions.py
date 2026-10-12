"""ctr360: find XDK preprocessor macros that collide with identifiers used by
the mirrored ctr-native sources (e.g. far/near, s_addr, OpenEvent)."""
import os
import re
import sys

XDK = r"C:\Program Files (x86)\Microsoft Xbox 360 SDK\include\xbox"
MIRROR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build-360", "gen")

# Collect macro names defined by the XDK target headers.
macro_names = set()
for dirpath, dirnames, filenames in os.walk(XDK):
    for fn in filenames:
        if not fn.lower().endswith((".h", ".inl")):
            continue
        path = os.path.join(dirpath, fn)
        try:
            text = open(path, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in re.finditer(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.M):
            macro_names.add(m.group(1))

# Identifiers the mirror actually uses (word-boundary use, excluding #include).
used = {}
for top in ("include", "game", "platform"):
    root = os.path.join(MIRROR, top)
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith((".c", ".h", ".inc")):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, MIRROR)
            try:
                text = open(path, "r", encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for name in macro_names:
                if len(name) < 3:
                    continue
                # only names that look like identifiers used in code, not all-caps constants
                if name.isupper() and len(name) > 3:
                    continue
                if re.search(r"\b%s\b" % re.escape(name), text):
                    used.setdefault(name, set()).add(rel)

interesting = {}
for name, files in used.items():
    # Skip macros that are clearly XDK-internal type/attr helpers.
    if name.startswith("_") or name.endswith("_"):
        continue
    interesting[name] = sorted(files)

for name in sorted(interesting):
    files = interesting[name]
    if len(files) > 8:
        files = files[:8] + ["..."]
    print("%-24s %s" % (name, ", ".join(files)))
print("total:", len(interesting))
