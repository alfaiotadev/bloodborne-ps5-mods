import sys, struct, pickle, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
A = pickle.load(open(workpath("lockA.pkl"), "rb")); m = A["wins"][A["roots"]["mgr"]]
R = struct.unpack_from("<4f", m, 0x10); U = struct.unpack_from("<4f", m, 0x20); F = struct.unpack_from("<4f", m, 0x30); P = struct.unpack_from("<4f", m, 0x40)
cr = lambda a, b: (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
print("R", [round(x, 3) for x in R], "U", [round(x, 3) for x in U], "F", [round(x, 3) for x in F])
print("R x U =", [round(x, 3) for x in cr(R, U)], "(= F if right-handed R,U,F)")
print("U x F =", [round(x, 3) for x in cr(U, F)], " F x R =", [round(x, 3) for x in cr(F, R)])
print("lengths", [round(math.sqrt(sum(c*c for c in v[:3])), 3) for v in (R, U, F)], "dots RU RF UF", [round(sum(a*b for a, b in zip(x[:3], y[:3])), 3) for x, y in ((R, U), (R, F), (U, F))])
