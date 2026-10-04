"""Find hkQsTransform arrays (translation vec4, rotation quaternion, scale vec4 ~ (1,1,1); stride 0x30) in the object graph of the player ChrIns. Read-only."""
import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000 and v % 8 == 0
pl = q(q(0x593e878) + 0x60); X = q(q(pl + 0x3b0) + 0x68); P = struct.unpack("<3f", d.proc_read(pid, X + 0x1e0, 12))
seen = {pl}; queue = [(pl, 0, None)]; wins = {}; prov = {}
while queue and len(wins) < 4000:
    a, depth, par = queue.pop(0); n = 0x2000 if depth else 0x1000; r = d.proc_read(pid, a, n)
    if not r: continue
    wins[a] = r; prov[a] = par
    if depth < 3:
        for o in range(0, len(r) - 7, 8):
            p = struct.unpack_from("<Q", r, o)[0]
            if heap(p) and p not in seen: seen.add(p); queue.append((p, depth + 1, (a, o)))
print("windows %d (%.1f MB)" % (len(wins), sum(len(v) for v in wins.values()) / 1e6))
runs = []
for a, r in wins.items():
    m = len(r) // 4
    f = struct.unpack("<%df" % m, r[:m * 4])
    ok = {}
    for i in range(0, m - 11, 4):                 # 16-byte aligned candidates: [t(4) q(4) s(4)]
        if (a + i * 4) % 16: continue
        qn = f[i + 4] ** 2 + f[i + 5] ** 2 + f[i + 6] ** 2 + f[i + 7] ** 2
        if abs(qn - 1) < 2e-3 and all(abs(f[i + 8 + k] - 1) < 1e-3 for k in range(3)): ok[a + i * 4] = f[i:i + 3]
    for s in sorted(ok):
        if s - 0x30 in ok: continue
        n = 1
        while s + n * 0x30 in ok: n += 1
        if n >= 10: runs.append((n, s, a))
for n, s, a in sorted(runs, reverse=True)[:12]:
    pa = prov[a]; r = wins[a]; f = lambda k: struct.unpack_from("<3f", r, s - a + k * 0x30)
    ys = [f(k)[1] for k in range(n)]
    print("run of %3d bones at %#x (window %#x+%#x, parent %s)  t.y range %.3f..%.3f  first t %s" % (n, s, a, s - a, "%#x+%#x" % pa if pa else "root", min(ys), max(ys), ["%.3f" % v for v in f(0)]))
