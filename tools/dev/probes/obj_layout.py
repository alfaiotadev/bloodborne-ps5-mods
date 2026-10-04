import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); obj = q(mod + 0x18)
print("pid", pid, "mod %#x obj %#x" % (mod, obj))
raw = rd(obj, 0x700)
print("header:"); 
for o in range(0, 0x80, 0x10): print("  +%03x: %016x %016x" % (o, *struct.unpack_from("<QQ", raw, o)))
def isarr(a):
    try: r = rd(a, 0x30 * 170)
    except Exception: return None
    if not r or len(r) < 8160: return None
    f = struct.unpack("<2040f", r[:8160]); ok = 0
    for i in range(170):
        row = f[12 * i:12 * i + 12]; r0 = row[0:3]; r1 = row[4:7]
        if abs(sum(x * x for x in r0) - 1) < 0.02 and abs(sum(x * x for x in r1) - 1) < 0.02: ok += 1
    return ok
print("pointer slots (o: target, vtable, isarr-ok):")
for o in range(0x100, 0x700, 8):
    v = struct.unpack_from("<Q", raw, o)[0]
    if 0x100000000 < v < 0x800000000:
        ok = isarr(v)
        try: vt = q(v)
        except Exception: vt = None
        print("  +%03x -> %#x  vt=%s  arr_ok=%s" % (o, v, hex(vt) if vt is not None else None, ok if ok is None else "%d/170" % ok))
