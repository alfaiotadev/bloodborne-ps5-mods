import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl = q(q(0x593e878) + 0x60); m = q(pl + 0x58)
print("pl %#x  [pl+0x58]=%#x" % (pl, m))
for lo, hi in ((0x60, 0x110), (0x320, 0x380)):
    raw = d.proc_read(pid, m + lo, hi - lo)
    for o in range(0, hi - lo, 16):
        print("  m+%03x: " % (lo + o) + " ".join("%08x" % v for v in struct.unpack_from("<4I", raw, o)) + "   " + " ".join("%9.4f" % v for v in struct.unpack_from("<4f", raw, o)))
