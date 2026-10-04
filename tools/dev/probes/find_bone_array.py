"""Find arrays of bone world positions: windows (BFS from the player ChrIns, depth <= 3) with many (x,y,z,w=1) points within 2 m of the player at a constant stride. Read-only."""
import sys, struct, time, collections
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000 and v % 8 == 0
pl = q(q(0x593e878) + 0x60); X = q(q(pl + 0x3b0) + 0x68); P = struct.unpack("<3f", d.proc_read(pid, X + 0x1e0, 12))
seen = {pl}; queue = [(pl, 0x1000, 0, None)]; wins = {}; prov = {}
while queue and len(wins) < 3500:
    a, n, depth, par = queue.pop(0); r = d.proc_read(pid, a, n)
    if not r: continue
    wins[a] = r; prov[a] = par
    if depth < 3:
        for o in range(0, len(r) - 7, 8):
            p = struct.unpack_from("<Q", r, o)[0]
            if heap(p) and p not in seen: seen.add(p); queue.append((p, 0x1000, depth + 1, (a, o)))
print("player %.3f %.3f %.3f, windows %d" % (*P, len(wins)))
near = lambda x, y, z: abs(x - P[0]) < 2 and abs(z - P[2]) < 2 and -0.5 < y - P[1] < 2.3
cands = []   # absolute address of 16-aligned (x,y,z,w) points
for a, r in wins.items():
    m = len(r) // 4 - 3
    f = struct.unpack("<%df" % (m + 3), r[:(m + 3) * 4])
    for i in range(0, m, 4 if a % 16 == 0 else 1):
        if (a + i * 4) % 16: continue
        if near(f[i], f[i + 1], f[i + 2]) and abs(f[i + 3] - 1.0) < 1e-3: cands.append(a + i * 4)
cs = sorted(set(cands)); print("aligned near points:", len(cs))
# stride analysis: for each candidate count how many candidates at +k*stride
best = []
for stride in (0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80, 0xa0, 0xc0, 0x100):
    S = set(cs); runs = []
    for a in cs:
        if a - stride in S: continue
        n = 1
        while a + n * stride in S: n += 1
        if n >= 8: runs.append((n, a))
    for n, a in runs: best.append((n, stride, a))
for n, stride, a in sorted(best, reverse=True)[:25]:
    base = [w for w in wins if w <= a < w + len(wins[w])][0]
    print("run of %3d at %#x stride %#x  (window %#x+%#x, parent %s)" % (n, a, stride, base, a - base, "%#x+%#x" % prov[base] if prov[base] else "root"))
