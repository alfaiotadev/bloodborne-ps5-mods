import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); w = q(pl + 0x58); X = q(q(pl + 0x3b0) + 0x68)
print("pl %#x w %#x X %#x" % (pl, w, X))
print("physics pos [X+0x1e0]", [round(v, 3) for v in struct.unpack("<3f", rd(X + 0x1e0, 12))])
print("w rows 0x320..0x360:")
for off in range(0x300, 0x370, 0x10): print("  +%#x" % off, [round(v, 3) for v in struct.unpack("<4f", rd(w + off, 16))])
# other places holding the position: search w and pl windows for a float triple equal to the physics pos
P = struct.unpack("<3f", rd(X + 0x1e0, 12))
for name, base, size in (("w", w, 0x800), ("pl", pl, 0x1000), ("mod", mod, 0x800)):
    b = rd(base, size); f = struct.unpack("<%df" % (size // 4), b); hits = [hex(i * 4) for i in range(len(f) - 2) if abs(f[i] - P[0]) < 0.01 and abs(f[i + 1] - P[1]) < 0.01 and abs(f[i + 2] - P[2]) < 0.01]
    print(name, "float triples == physics pos at", hits[:12])
