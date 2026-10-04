"""Stage 2 (lock released): re-read the stage-A windows, report pointer fields that changed, flagging pointees that look like a ChrIns (position via +0x3b0 -> +0x68 -> +0x1e0)."""
import sys, struct, time, pickle, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
ok = lambda v: 0x200000000 <= v < 0x400000000 and v % 8 == 0
A = pickle.load(open(workpath("lockA.pkl"), "rb")); wa, par, roots = A["wins"], A["par"], A["roots"]
rn = {v: k for k, v in roots.items()}
def path(a):
    out = []
    while a in par: pa, o = par[a]; out.append("%#x" % o); a = pa
    return "%s:" % rn.get(a, hex(a)) + ">".join(reversed(out))
PP = struct.unpack("<3f", rd(q(q(roots["pl"] + 0x3b0) + 0x68) + 0x1e0, 12))
def chrpos(v):
    try:
        vt = q(v)
        if not (0x5700000 <= vt < 0x5800000): return None
        p1 = q(v + 0x3b0)
        if not ok(p1): return None
        p2 = q(p1 + 0x68)
        if not ok(p2): return None
        pos = struct.unpack("<3f", rd(p2 + 0x1e0, 12))
        return pos if all(abs(c) < 1e4 and c == c for c in pos) and 0.5 < math.dist(pos, PP) < 40 else None
    except Exception: return None
t0 = time.time(); diffs = []; n = 0
for a, ba in wa.items():
    bb = rd(a, 0x400); n += 1
    if not bb or bb == ba: continue
    for o in range(0, 0x3f9, 8):
        x = struct.unpack_from("<Q", ba, o)[0]; y = struct.unpack_from("<Q", bb, o)[0]
        if x != y and (ok(x) or ok(y) or x == 0 or y == 0) and (ok(x) or ok(y)): diffs.append((a, o, x, y))
print("re-read %d windows in %.0f s; changed pointer-ish fields: %d" % (n, time.time() - t0, len(diffs)), flush=True)
rows = []
for a, o, x, y in diffs:
    px = chrpos(x) if ok(x) else None; py = chrpos(y) if ok(y) else None
    if px or py: rows.append((a, o, x, y, px, py))
print("player", [round(c, 1) for c in PP]); print("changed fields whose old/new pointee is a ChrIns within 40 m: %d" % len(rows))
for a, o, x, y, px, py in rows[:30]: print("  win %#x +%#x  locked %#x %s -> free %#x %s   %s" % (a, o, x, [round(c, 1) for c in px] if px else "-", y, [round(c, 1) for c in py] if py else "-", path(a)))
