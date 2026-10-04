import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
wcm = q(0x593e878); cam = q(q(q(0x593e860) + 0x2830) + 0x60)
regs = [("wcm", wcm + 0x60, 0x60), ("cam", cam + 0x100, 0x40)]
print("pid", pid, "RIGHT stick circles now (6 s), then LEFT stick (6 s)", flush=True)
phases = {"right": [], "left": []}; t0 = time.time()
while time.time() - t0 < 14:
    t = time.time() - t0; ph = "right" if 1 < t < 7 else ("left" if 8 < t < 14 else None)
    if ph is None: continue
    row = {}
    for name, a, n in regs: row[name] = struct.unpack("<%df" % (n // 4), rd(a, n))
    phases[ph].append(row)
for name, a, n in regs:
    print("\n%s floats (offset: max|v| right-stick phase / left-stick phase):" % name)
    for i in range(n // 4):
        mr = max(abs(r[name][i]) if r[name][i] == r[name][i] and abs(r[name][i]) < 1e5 else 0 for r in phases["right"]); ml = max(abs(r[name][i]) if r[name][i] == r[name][i] and abs(r[name][i]) < 1e5 else 0 for r in phases["left"])
        rng = lambda ph: (max(r[name][i] for r in phases[ph]) - min(r[name][i] for r in phases[ph])) if phases[ph] else 0
        if rng("right") > 1e-3 or rng("left") > 1e-3: print("  +%#x  right-phase range %.3f  left-phase range %.3f   (max|v| %.2f / %.2f)" % (a - (wcm if name == "wcm" else cam) + i * 4, rng("right"), rng("left"), mr, ml))
