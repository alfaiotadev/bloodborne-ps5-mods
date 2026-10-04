import sys, struct, pickle
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
A = pickle.load(open(workpath("lockA.pkl"), "rb")); wa, par, roots = A["wins"], A["par"], A["roots"]
rn = {v: k for k, v in roots.items()}
tp = struct.unpack_from("<Q", wa[roots["mgr"]], 0x110)[0]
print("target pointer in mgr entry 0: %#x" % tp)
def path(a):
    out = []
    while a in par: pa, o = par[a]; out.append("%#x" % o); a = pa
    return "%s:" % rn.get(a, hex(a)) + ">".join(reversed(out))
for a, b in wa.items():
    for o in range(0, 0x3f9, 8):
        if struct.unpack_from("<Q", b, o)[0] == tp: print("  referenced by win %#x +%#x   %s" % (a, o, path(a)))
cam = wa[roots["cam"]]; print("follow cam %#x pointers/values near +0x100..+0x1c0:" % roots["cam"])
for o in range(0x100, 0x1c0, 0x10): print("  +%#x" % o, " ".join("%016x" % x for x in struct.unpack_from("<2Q", cam, o)), [round(v, 3) for v in struct.unpack_from("<4f", cam, o)])
mgr = wa[roots["mgr"]]
print("mgr entries' pointers:", [hex(struct.unpack_from("<Q", mgr, o)[0]) for o in range(0x110, 0x400, 0x80)], "second qwords:", [hex(struct.unpack_from("<Q", mgr, o + 8)[0]) for o in range(0x110, 0x400, 0x80)])
