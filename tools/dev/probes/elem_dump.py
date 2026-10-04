import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl = q(q(0x593e878) + 0x60); obj = q(pl + 0x4d0); hold = q(obj + 0xe8); X = q(q(pl + 0x3b0) + 0x68); P = struct.unpack("<3f", d.proc_read(pid, X + 0x1e0, 12))
print("pl %#x obj %#x holder %#x  player y %.3f" % (pl, obj, hold, P[1]))
for k in (0, 1, 2, 3, 6):
    a = hold + 0xdd0 + k * 0xa0; r = d.proc_read(pid, a, 0xa0); print("-- element %d at %#x" % (k, a))
    for o in range(0, 0xa0, 16):
        print("   +%02x: %s   %s" % (o, " ".join("%08x" % v for v in struct.unpack_from("<4I", r, o)), " ".join("%9.4f" % v for v in struct.unpack_from("<4f", r, o))))
print("holder header (first 0x60 bytes of the holder window and 0xd80..0xdd0):")
for lo in (0, 0xd80):
    r = d.proc_read(pid, hold + lo, 0x50)
    for o in range(0, 0x50, 16): print("  h+%#05x: %s" % (lo + o, " ".join("%08x" % v for v in struct.unpack_from("<4I", r, o))))
