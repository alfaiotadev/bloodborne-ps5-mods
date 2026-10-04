import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); obj = q(mod + 0x18); w = q(pl + 0x58)
o = struct.unpack("<3f", rd(w + 0x350, 12)); print("model origin [w+0x350]", [round(x, 3) for x in o])
cam = q(q(q(0x593e860) + 0x2830) + 0x60); c = struct.unpack("<3f", rd(cam + 0x40, 12)); print("game camera", [round(x, 3) for x in c])
for off in range(0x300, 0x600, 8):
    p = q(obj + off)
    if not (0x100000000 < p < 0x800000000): continue
    try: h = struct.unpack("<3f", rd(p + 68 * 0x30 + 12, 4) + rd(p + 68 * 0x30 + 28, 4) + rd(p + 68 * 0x30 + 44, 4))
    except Exception: continue
    dx, dy, dz = h[0] - o[0], h[1] - o[1], h[2] - o[2]
    ok = 0.25 < dy < 2.4 and dx * dx + dz * dz < 2.25
    if ok or off in (0x320, 0x328, 0x400, 0x490): print("  slot %#x head-origin (%.2f %.2f %.2f) %s | dist to game camera %.2f" % (off, dx, dy, dz, "PLAUSIBLE" if ok else "no", math.dist(h, c)))
