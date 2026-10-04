import sys, struct, pickle
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n)
A = pickle.load(open(workpath("lockA.pkl"), "rb")); wa, par, roots = A["wins"], A["par"], A["roots"]
rn = {v: k for k, v in roots.items()}
def path(a):
    out = []
    while a in par: pa, o = par[a]; out.append("%#x" % o); a = pa
    return "%s:" % rn.get(a, hex(a)) + ">".join(reversed(out))
f = lambda v: struct.unpack("<f", struct.pack("<I", v))[0]
def floaty(v): x = f(v); return v != 0 and (abs(x) > 1e-6 and abs(x) < 1e6)
print("roots:", {k: hex(v) for k, v in roots.items()})
cnt = 0
for a, ba in wa.items():
    depth = path(a).count(">") 
    if depth > 1 and a not in roots.values(): continue
    bb = rd(a, 0x400)
    if not bb or bb == ba: continue
    for o in range(0, 0x3fd, 4):
        x = struct.unpack_from("<I", ba, o)[0]; y = struct.unpack_from("<I", bb, o)[0]
        if x != y and (x < 0x10000 or y < 0x10000 or x == 0xffffffff or y == 0xffffffff):
            print("  %-26s win %#x +%#x  locked %#x -> free %#x" % (path(a), a, o, x, y)); cnt += 1
print("count", cnt)
