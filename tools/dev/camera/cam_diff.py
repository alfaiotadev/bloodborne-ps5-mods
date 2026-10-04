"""Find the camera's yaw/pitch state fields by correlation. Samples float windows of the camera objects while the user turns the camera,
then reports fields whose changes track the forward-vector yaw / pitch (slope +-1, or in degrees). Usage: cam_diff.py [seconds=15]"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
T = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000
world = q(0x593e860); mgr = q(world + 0x2830); cam = q(mgr + 0x60)
wins = {"cam": (cam, 0x600), "mgr": (mgr, 0x600), "world": (world, 0x3000)}
# one pointer level below mgr and the world object (first 0x3000) -> 0x300-byte windows
for nm, (b, n) in list(wins.items()):
    if nm == "cam": continue
    raw = d.proc_read(pid, b, n)
    for o in range(0, n, 8):
        p = struct.unpack_from("<Q", raw, o)[0]
        if heap(p) and all(abs(p - w[0]) > 0x600 for w in wins.values()): wins["%s+%#x" % (nm, o)] = (p, 0x300)
print("windows:", len(wins), "total bytes %d" % sum(n for _, n in wins.values()), flush=True)
def snap():
    out = {}
    for nm, (b, n) in wins.items():
        r = d.proc_read(pid, b, n)
        if r: out[nm] = struct.unpack("<%df" % (len(r) // 4), r[:len(r) // 4 * 4])
    return out
yawpitch = lambda s: (math.atan2(s["cam"][0x30 // 4 + 0], s["cam"][0x30 // 4 + 2]), math.asin(max(-1, min(1, s["cam"][0x30 // 4 + 1]))))
print("SAMPLING %.0f s -- turn the camera now" % T, flush=True)
t0 = time.time(); samples = []
while time.time() - t0 < T:
    s = snap(); samples.append((time.time() - t0, s))
print("samples:", len(samples), " rate %.1f Hz" % (len(samples) / T), flush=True)
ys, ps = [], []
for _, s in samples:
    y, p = yawpitch(s)
    if ys and y - ys[-1] > math.pi: y -= 2 * math.pi
    if ys and y - ys[-1] < -math.pi: y += 2 * math.pi
    ys.append(y); ps.append(p)
print("yaw range %.3f..%.3f  pitch range %.3f..%.3f" % (min(ys), max(ys), min(ps), max(ps)))
def corr(a, b):
    n = len(a); ma = sum(a) / n; mb = sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
    if va < 1e-12 or vb < 1e-12: return 0, 0
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)); return cov / math.sqrt(va * vb), cov / vb
for label, ref in (("yaw", ys), ("pitch", ps)):
    if max(ref) - min(ref) < 0.05: print("-- %s barely moved, skipped" % label); continue
    print("== fields tracking", label)
    hits = []
    for nm, (b, n) in wins.items():
        series = [s[nm] for _, s in samples if nm in s]
        if len(series) != len(samples): continue
        for i in range(len(series[0])):
            col = [r[i] for r in series]
            if not all(math.isfinite(c) for c in col) or max(col) - min(col) < 0.02: continue
            r, slope = corr(col, ref)   # slope = d(ref)/d(field) -> want ~ +-1 (rad) or +-0.01745 (deg)
            if abs(r) > 0.97: hits.append((abs(r), nm, i * 4, r, slope, min(col), max(col)))
    for h in sorted(hits, reverse=True)[:25]:
        print("  %s+%#x  r=%.4f  dref/dfield=%.4f  range %.3f..%.3f  (abs %#x)" % (h[1], h[2], h[3], h[4], h[5], h[6], wins[h[1]][0] + h[2]))
