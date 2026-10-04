"""Samples head-origin geometry for 80 s and reports which cave plausibility check would fail (YMIN .25 / YMAX 2.4 / horizontal R2 2.25 / LIMIT 100 to the game camera)."""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); obj = q(mod + 0x18); w = q(pl + 0x58)
cam = q(q(q(0x593e860) + 0x2830) + 0x60)
arroff = struct.unpack("<i", rd(0x54A0E14, 4))[0]; arr = q(obj + arroff); print("pid", pid, "ARROFF %#x array %#x" % (arroff, arr), flush=True)
rows = []; t0 = time.time()
while time.time() - t0 < 80:
    t = time.time()
    try:
        o = struct.unpack("<3f", rd(w + 0x350, 12)); b = rd(arr + 68 * 0x30, 0x30); h = struct.unpack("<3f", b[12:16] + b[28:32] + b[44:48]); c = struct.unpack("<3f", rd(cam + 0x40, 12))
    except Exception as e: print("read fail", e); break
    dy = h[1] - o[1]; dxz2 = (h[0] - o[0]) ** 2 + (h[2] - o[2]) ** 2; dc2 = sum((h[i] - c[i]) ** 2 for i in range(3))
    rows.append((t - t0, dy, dxz2, dc2, o))
bad = [r for r in rows if not (0.25 < r[1] < 2.4) or r[2] >= 2.25 or r[3] >= 100]
print("samples", len(rows), "failing", len(bad))
print("max dy %.2f min dy %.2f | max dxz %.2f m | max dist-to-cam %.2f m" % (max(r[1] for r in rows), min(r[1] for r in rows), math.sqrt(max(r[2] for r in rows)), math.sqrt(max(r[3] for r in rows))))
for r in bad[:25]:
    why = []
    if r[1] <= 0.25: why.append("dy<=0.25")
    if r[1] >= 2.4: why.append("dy>=2.4")
    if r[2] >= 2.25: why.append("dxz>=1.5")
    if r[3] >= 100: why.append("cam>=10m")
    print("  t=%5.2f dy=%.2f dxz=%.2f cam=%.2f  %s" % (r[0], r[1], math.sqrt(r[2]), math.sqrt(r[3]), ",".join(why)))
