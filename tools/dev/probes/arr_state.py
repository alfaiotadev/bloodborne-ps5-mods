import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); obj = q(mod + 0x18)
X = q(q(pl + 0x3b0) + 0x68); P = struct.unpack("<3f", rd(X + 0x1e0, 12)); print("player", [round(v, 2) for v in P], "obj %#x" % obj)
raw = rd(obj, 0x600)
print("obj slots:", {hex(o): hex(struct.unpack_from("<Q", raw, o)[0]) for o in range(0x400, 0x600, 8) if 0x100000000 < struct.unpack_from("<Q", raw, o)[0] < 0x800000000})
def snap(a): r = rd(a, 0x30 * 170); f = struct.unpack("<2040f", r[:8160]); return [(f[12 * i + 3], f[12 * i + 7], f[12 * i + 11]) for i in range(170)]
slots = [o for o in range(0x400, 0x600, 8) if 0x100000000 < struct.unpack_from("<Q", raw, o)[0] < 0x800000000]
S = {}
for k in range(3):
    for o in slots:
        a = struct.unpack_from("<Q", raw, o)[0]
        try: S.setdefault(o, []).append(snap(a))
        except Exception as e: S.setdefault(o, []).append(None)
    time.sleep(0.4)
for o in slots:
    s = S[o]
    if None in s: print("slot %#x unreadable" % o); continue
    nz = sum(1 for t in s[0] if any(abs(x) > 1e-6 for x in t)); mv = sum(1 for i in range(170) if max(abs(s[0][i][j] - s[2][i][j]) for j in range(3)) > 1e-4)
    h = s[0][68]; print("slot %#x: nonzero bones %3d/170, moving %3d, bone68 %s (rel player %s)" % (o, nz, mv, [round(x, 2) for x in h], [round(h[j] - P[j], 2) for j in range(3)]))
