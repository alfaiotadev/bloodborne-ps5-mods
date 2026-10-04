"""Wide BFS from WorldChrMan only; list every ChrIns-like object (position via +0x3b0 -> +0x68 -> +0x1e0) with its distance to the camera view ray."""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
ok = lambda v: 0x200000000 <= v < 0x400000000 and v % 8 == 0
wcm = q(0x593e878); pl = q(wcm + 0x60); cam = q(q(q(0x593e860) + 0x2830) + 0x60)
b = rd(cam + 0x30, 0x20); f = struct.unpack("<8f", b); Fw, P = f[0:3], f[4:7]; l = math.sqrt(sum(x * x for x in Fw)); Fw = tuple(x / l for x in Fw)
print("pid", pid, "cam", [round(x, 2) for x in P], "fwd", [round(x, 2) for x in Fw], flush=True)
def ray(x):
    v = (x[0] - P[0], x[1] - P[1], x[2] - P[2]); t = sum(v[i] * Fw[i] for i in range(3)); perp = math.sqrt(max(sum(c * c for c in v) - t * t, 0)); return t, perp
queue = [(wcm, 0)]; parent = {wcm: None}; n = 0; t0 = time.time(); chrs = {}
def path(a):
    out = []
    while parent.get(a): pa, o = parent[a]; out.append("%#x" % o); a = pa
    return "wcm:" + ">".join(reversed(out))
while queue and n < 9000 and time.time() - t0 < 100:
    a, dep = queue.pop(0); bb = rd(a, 0x400); n += 1
    if not bb: continue
    p1 = struct.unpack_from("<Q", bb, 0x3b0)[0]
    if ok(p1) and a not in chrs:
        try:
            p2 = q(p1 + 0x68)
            if ok(p2):
                pos = struct.unpack("<3f", rd(p2 + 0x1e0, 12))
                if all(abs(c) < 1e4 and c == c for c in pos) and pos != (0.0, 0.0, 0.0): chrs[a] = (pos, struct.unpack_from("<Q", bb, 0)[0])
        except Exception: pass
    if dep < 5:
        for off in range(0, 0x3f9, 8):
            p = struct.unpack_from("<Q", bb, off)[0]
            if ok(p) and p not in parent: parent[p] = (a, off); queue.append((p, dep + 1))
print("windows %d in %.0f s; ChrIns-like objects: %d" % (n, time.time() - t0, len(chrs)), flush=True)
rows = []
for a, (pos, vt) in chrs.items():
    t, perp = ray(pos); rows.append((perp, t, a, pos, vt))
PP = struct.unpack("<3f", rd(q(q(pl + 0x3b0) + 0x68) + 0x1e0, 12)); print("player", [round(c, 1) for c in PP])
near = sorted((math.dist(pos, PP), a, pos, vt) for a, (pos, vt) in chrs.items() if math.dist(pos, PP) < 25)
print("chr-like within 25 m of the player: %d" % len(near))
for dd, a, pos, vt in near[:25]:
    t, perp = ray(pos); print("  d %5.1f  obj %#x vt %#x pos %s  | ray: along %.1f perp %.2f  %s" % (dd, a, vt, [round(c, 1) for c in pos], t, perp, path(a)))
