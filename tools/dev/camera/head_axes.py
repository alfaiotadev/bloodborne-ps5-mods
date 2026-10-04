"""Which local axes of the head bone (78) point forward / up in world space?  Reads the live pose + model->world rows, rotates the local axes with the bone quaternion (hkQsTransform +0x10 = x,y,z,w).
Read-only.  Also prints the character facing from the model->world rows and the follow-camera forward."""
import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q64 = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl = q64(q64(0x593e878) + 0x60); m = q64(pl + 0x58); arr = q64(q64(pl + 0xa68) + 0x50)
R = [struct.unpack("<3f", d.proc_read(pid, m + 0x320 + 16 * i, 12)) for i in range(3)]
cam = q64(q64(q64(0x593e860) + 0x2830) + 0x60); cf = struct.unpack("<3f", d.proc_read(pid, cam + 0x30, 12))
def rot(qv, v):
    x, y, z, w = qv; ux, uy, uz = x, y, z
    cx, cy, cz = uy * v[2] - uz * v[1], uz * v[0] - ux * v[2], ux * v[1] - uy * v[0]
    dx, dy, dz = uy * cz - uz * cy, uz * cx - ux * cz, ux * cy - uy * cx
    return (v[0] + 2 * (w * cx + dx), v[1] + 2 * (w * cy + dy), v[2] + 2 * (w * cz + dz))
tow = lambda v: tuple(v[0] * R[0][k] + v[1] * R[1][k] + v[2] * R[2][k] for k in range(3))     # model -> world (rotation part)
yaw = lambda v: math.degrees(math.atan2(v[0], v[2])); pit = lambda v: math.degrees(math.asin(max(-1, min(1, v[1]))))
print("model axes in world: x", ["%.2f" % v for v in R[0]], " y", ["%.2f" % v for v in R[1]], " z", ["%.2f" % v for v in R[2]])
print("camera forward (game): yaw %.1f pitch %.1f" % (yaw(cf), pit(cf)))
for bone in (78, 77, 49, 0):
    qv = struct.unpack("<4f", d.proc_read(pid, arr + bone * 0x30 + 0x10, 16))
    print("bone %d q %s" % (bone, ["%.3f" % v for v in qv]))
    for name, ax in (("+x", (1, 0, 0)), ("-x", (-1, 0, 0)), ("+y", (0, 1, 0)), ("-y", (0, -1, 0)), ("+z", (0, 0, 1)), ("-z", (0, 0, -1))):
        w = tow(rot(qv, ax)); print("   local %s -> world (%.2f %.2f %.2f)  yaw %6.1f pitch %6.1f" % (name, *w, yaw(w), pit(w)))
