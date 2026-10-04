"""Read the YEBIS CPostEffect context ([0x5865ed0]): init-flag bytes, AA / temporal AA enables and parameters (read-only)."""
import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
ctx = q(0x5865ed0); print("YEBIS ctx %#x" % ctx)
r = d.proc_read(pid, ctx + 0x130, 0x30); print("init-flag bytes ctx+0x130..0x15f:", " ".join("%02x" % b for b in r))
names = {0x145: "ANTIALIAS_TEMPORAL", 0x147: "GAUSSIANBLUR", 0x14f: "ANTIALIAS", 0x150: "ANTIALIAS_DISTANCEFALLOFF"}
print("  ", {n: r[o - 0x130] for o, n in names.items()})
g = lambda o, f="<f": struct.unpack(f, d.proc_read(pid, ctx + o, 4))[0]
print("AA enable [+0xbbc] =", d.proc_read(pid, ctx + 0xbbc, 1)[0], "  falloff dist [+0xbc0,+0xbc4] =", g(0xbc0), g(0xbc4), "  dirty [+0x6d5] =", d.proc_read(pid, ctx + 0x6d5, 1)[0])
print("TAA enable [+0xb8c] =", d.proc_read(pid, ctx + 0xb8c, 1)[0])
print("TAA params +0xb98..0xbac:", ["%.5g" % g(o) for o in (0xb90, 0xb94, 0xb98, 0xb9c, 0xba0, 0xba4, 0xba8, 0xbac)])
print("raw +0xb80..0xbd0:")
r = d.proc_read(pid, ctx + 0xb80, 0x50)
for o in range(0, 0x50, 16): print("  +%#x: %s   %s" % (0xb80 + o, " ".join("%08x" % v for v in struct.unpack_from("<4I", r, o)), " ".join("%10.5g" % v for v in struct.unpack_from("<4f", r, o))))
