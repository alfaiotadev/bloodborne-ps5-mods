"""Static snapshot while locked on: BFS the camera/player/world objects; list ChrIns-like objects and raw float triples close to the camera's view ray (the lock-on target)."""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
ok = lambda v: 0x200000000 <= v < 0x400000000 and v % 8 == 0
pl = q(q(0x593e878) + 0x60); wcm = q(0x593e878); cam = q(q(q(0x593e860) + 0x2830) + 0x60); mgr = q(q(0x593e860) + 0x2830)
def camstate():
    b = rd(cam + 0x30, 0x20); f = struct.unpack("<8f", b); return f[0:3], f[4:7]    # forward row, position row
Fw0, P0 = camstate(); print("pid", pid, "cam pos %s fwd %s - GO (stand still, locked on)" % ([round(x, 2) for x in P0], [round(x, 2) for x in Fw0]), flush=True)
t0 = time.time(); roots = [("pl", pl), ("cam", cam), ("mgr", mgr), ("wcm", wcm)]
queue = [(a, 0, n) for n, a in roots]; seen = {a for _, a in roots}; parent = {a: (None, n) for n, a in roots}; wins = {}
while queue and len(wins) < 2600 and time.time() - t0 < 50:
    a, dep, nm = queue.pop(0); b = rd(a, 0x400)
    if not b: continue
    wins[a] = b
    if dep < 3:
        for o in range(0, 0x3f9, 8):
            p = struct.unpack_from("<Q", b, o)[0]
            if ok(p) and p not in seen: seen.add(p); parent[p] = (a, o); queue.append((p, dep + 1, nm))
Fw1, P1 = camstate(); drift = math.dist(P0, P1); print("windows %d in %.0f s; camera drift %.3f m" % (len(wins), time.time() - t0, drift), flush=True)
Fw, P = Fw1, P1; l = math.sqrt(sum(x * x for x in Fw)); Fw = tuple(x / l for x in Fw)
def ray(x):
    v = (x[0] - P[0], x[1] - P[1], x[2] - P[2]); t = sum(v[i] * Fw[i] for i in range(3))
    if not (1.5 < t < 40): return None
    perp = math.sqrt(max(sum(c * c for c in v) - t * t, 0)); return t, perp
def path(a):
    out = []
    while a is not None and parent[a][0] is not None: pa, o = parent[a]; out.append("%#x" % o); a = pa
    return "%s:" % parent[a][1] + ">".join(reversed(out))
chrs = []; trip = []
for a, b in wins.items():
    p1 = struct.unpack_from("<Q", b, 0x3b0)[0]
    if ok(p1):
        try:
            p2 = q(p1 + 0x68)
            if ok(p2):
                pos = struct.unpack("<3f", rd(p2 + 0x1e0, 12))
                if all(abs(c) < 1e4 and c == c for c in pos):
                    r = ray(pos)
                    if r and r[1] < 3.0: chrs.append((r[1], r[0], a, pos, struct.unpack_from("<Q", b, 0)[0]))
        except Exception: pass
    f = struct.unpack("<%df" % 0x100, b)
    for i in range(0x100 - 2):
        x = f[i:i + 3]
        if any(c != c or abs(c) > 1e4 for c in x): continue
        r = ray(x)
        if r and r[1] < 0.5 and r[0] > 4.2: trip.append((r[1], r[0], a, i * 4, x))
print("\nChrIns-like objects within 3 m of the view ray (perp, along, addr, pos, vtable, path):")
for perp, t, a, pos, vt in sorted(chrs)[:8]: print("  perp %.2f along %.1f  obj %#x vt %#x pos %s  %s" % (perp, t, a, vt, [round(c, 1) for c in pos], path(a)))
print("\nraw float triples within 0.5 m of the view ray, >4.2 m ahead (perp, along, window, offset, value, path):")
for perp, t, a, o, x in sorted(trip)[:14]: print("  perp %.2f along %.1f  win %#x +%#x %s  %s" % (perp, t, a, o, [round(c, 2) for c in x], path(a)))
