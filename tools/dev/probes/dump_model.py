import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl = q(q(0x593e878) + 0x60); m48 = q(pl + 0x48); mod = q(m48 + 0x18)
print("player", hex(pl), "[pl+0x48]", hex(m48), "model", hex(mod))
for label, base, n in (("[pl+0x48] object", m48, 0x80), ("model object", mod, 0x1c0)):
    raw = d.proc_read(pid, base, n); print("\n==", label)
    for o in range(0, n, 16):
        w = struct.unpack_from("<4I", raw, o); print("  +%03x: %s" % (o, " ".join("%08x" % x for x in w)))
