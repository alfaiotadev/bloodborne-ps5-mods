import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
ok = lambda v: 0x200000000 <= v < 0x800000000
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); w = q(pl + 0x58); o = struct.unpack("<3f", rd(w + 0x350, 12))
print("pid", pid, "map %#x" % struct.unpack("<I", rd(pl + 0x3f8, 4))[0], "mod %#x origin %s" % (mod, [round(x, 2) for x in o]))
def arr(p):
    if not ok(p) or p % 16: return None
    try: r = rd(p, 0x30 * 170)
    except Exception: return None
    if not r or len(r) < 8160: return None
    f = struct.unpack("<2040f", r[:8160]); n = sum(1 for i in range(170) if abs(sum(x * x for x in f[12 * i:12 * i + 3]) - 1) < 0.02)
    if n < 120: return None
    h = (f[68 * 12 + 3], f[68 * 12 + 7], f[68 * 12 + 11]); return [round(h[i] - o[i], 2) for i in range(3)]
def holder(name, a):
    if not ok(a): print("  %-14s %#x (not a pointer)" % (name, a)); return
    b = rd(a, 0x600); vt = struct.unpack_from("<Q", b, 0)[0]; hits = []
    for off in range(0, 0x5f8, 8):
        r = arr(struct.unpack_from("<Q", b, off)[0])
        if r is not None: hits.append((hex(off), r[1]))
    print("  %-14s %#x vt %#x arrays at %s" % (name, a, vt, hits))
for off in (0x18, 0x20, 0x28, 0x30, 0x5f0, 0x5f8, 0x600):
    holder("[mod+%#x]" % off, q(mod + off))
