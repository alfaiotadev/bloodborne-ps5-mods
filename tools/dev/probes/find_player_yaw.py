"""Find other copies of the player's facing: float == yaw, or sin/cos(yaw) pairs, in ChrIns and one pointer level below (read-only)."""
import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000
pl = q(q(0x593e878) + 0x60); X = q(q(pl + 0x3b0) + 0x68)
yaw = struct.unpack("<f", d.proc_read(pid, X + 0x1d4, 4))[0]
s, c = math.sin(yaw), math.cos(yaw)
print("yaw %.4f  sin %.4f  cos %.4f   (also -yaw %.4f, yaw+pi %.4f)" % (yaw, s, c, -yaw, yaw + math.pi))
T = 2.5e-3
def scan(base, size, tag):
    raw = d.proc_read(pid, base, size)
    if not raw: return
    n = size // 4; f = struct.unpack("<%df" % n, raw[:n * 4])
    for i in range(n):
        v = f[i]
        if abs(v - yaw) < T: print("  %s+%#x  == yaw  (%.4f)" % (tag, i * 4, v))
        elif abs(v + yaw) < T and abs(v) > 0.3: print("  %s+%#x  == -yaw (%.4f)" % (tag, i * 4, v))
        for j in range(max(0, i - 3), min(n, i + 4)):
            if j != i and abs(f[i] - s) < T and abs(f[j] - c) < T and abs(s) > 0.2 and abs(c) > 0.2:
                print("  %s+%#x sin / +%#x cos pair (%.4f, %.4f)" % (tag, i * 4, j * 4, f[i], f[j])); break
print("--- ChrIns direct"); scan(pl, 0x800, "pl")
raw = d.proc_read(pid, pl, 0x800); seen = set()
for o in range(0, 0x800, 8):
    p = struct.unpack_from("<Q", raw, o)[0]
    if heap(p) and p not in seen and p != pl:
        seen.add(p)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): scan(p, 0x600, "sub")
        if buf.getvalue(): print("--- [pl+%#x] -> %#x" % (o, p)); print(buf.getvalue(), end="")
