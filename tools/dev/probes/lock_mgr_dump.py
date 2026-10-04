import sys, struct, pickle, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
A = pickle.load(open(workpath("lockA.pkl"), "rb")); wa, roots = A["wins"], A["roots"]
mgr = wa[roots["mgr"]]; cam = wa[roots["cam"]]
print("mgr %#x (locked-state snapshot): entries at +0x100..+0x1a0" % roots["mgr"])
for o in range(0x100, 0x1a0, 0x10):
    q = struct.unpack_from("<2Q", mgr, o); f = struct.unpack_from("<4f", mgr, o)
    print("  +%#x  %016x %016x   floats %s" % (o, q[0], q[1], [round(x, 3) for x in f]))
print("cam+0x150..0x160:", [hex(struct.unpack_from("<I", cam, o)[0]) for o in range(0x150, 0x160, 4)], " floats", [round(struct.unpack_from("<f", cam, o)[0], 3) for o in range(0x150, 0x160, 4)])
P = struct.unpack_from("<3f", mgr, 0x40)
print("camera pos (mgr+0x40)", [round(x, 2) for x in P])
