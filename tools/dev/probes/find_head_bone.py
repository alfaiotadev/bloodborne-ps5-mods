"""Find the player's skeleton pose in memory: BFS over pointers from the player ChrIns (depth <= 3), report float triples that sit at head height above the player
(|dx|,|dz| < 0.5 m, dy 1.2..2.0 m; Y is up), then look for arrays of bone positions (constant stride).  Read-only.  Usage: find_head_bone.py [dmin dmax]"""
import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
dmin = float(sys.argv[1]) if len(sys.argv) > 1 else 1.2; dmax = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000 and v % 8 == 0
pl = q(q(0x593e878) + 0x60); X = q(q(pl + 0x3b0) + 0x68); P = struct.unpack("<3f", d.proc_read(pid, X + 0x1e0, 12))
print("player ChrIns %#x  pos %.3f %.3f %.3f" % (pl, *P))
seen = {pl: None}; queue = [(pl, 0x1000, 0)]; wins = {}; t0 = time.time()
while queue and len(wins) < 3000:
    a, n, depth = queue.pop(0); r = d.proc_read(pid, a, n)
    if not r: continue
    wins[a] = r
    if depth < 3:
        for o in range(0, len(r) - 7, 8):
            p = struct.unpack_from("<Q", r, o)[0]
            if heap(p) and p not in seen and all(not (w <= p < w + len(wins[w])) for w in list(wins)[-40:]): seen[p] = (a, o); queue.append((p, 0x1000, depth + 1))
print("windows %d, %.1f MB, %.1fs" % (len(wins), sum(len(v) for v in wins.values()) / 1e6, time.time() - t0))
hits = []
for a, r in wins.items():
    m = len(r) // 4 - 3
    f = struct.unpack("<%df" % (m + 3), r[:(m + 3) * 4])
    for i in range(m):
        x, y, z = f[i], f[i + 1], f[i + 2]
        if abs(x - P[0]) < 0.5 and abs(z - P[2]) < 0.5 and dmin < y - P[1] < dmax: hits.append((a + i * 4, x, y, z, f[i + 3]))
print("candidate triples:", len(hits))
by = {}
for h in hits: by.setdefault(h[0] & ~0xfff, []).append(h)
for pg, hs in sorted(by.items())[:60]:
    for h in hs[:6]: print("  %#x  (%.3f, %.3f, %.3f | %.3f)  dy %.3f  prov %s" % (h[0], h[1], h[2], h[3], h[4], h[2] - P[1], "%#x+%#x" % seen[[w for w in wins if w <= h[0] < w + len(wins[w])][0]] if seen.get([w for w in wins if w <= h[0] < w + len(wins[w])][0]) else "root"))
import pickle; pickle.dump({"P": P, "hits": hits}, open(workpath("head_hits.pkl"), "wb"))
