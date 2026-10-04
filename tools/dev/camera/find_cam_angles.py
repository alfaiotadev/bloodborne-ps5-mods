"""Find the follow camera's yaw/pitch angle fields: derive yaw/pitch from the camera direction vectors, then look for matching floats / sin-cos pairs (read-only)."""
import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
mgr = q(q(0x593e860) + 0x2830); cam = q(mgr + 0x60)
raw = d.proc_read(pid, cam, 0x400); f = struct.unpack("<256f", raw)
print("cam %#x" % cam)
for o in range(0, 0x80, 16): print("  +%02x: " % o + " ".join("%9.4f" % v for v in f[o // 4:o // 4 + 4]))
# candidate direction vectors: +0x10 / +0x20 / +0x30 rows (x,y,z)
for off in (0x10, 0x20, 0x30):
    x, y, z = f[off // 4:off // 4 + 3]
    n = math.sqrt(x * x + y * y + z * z)
    if 0.98 < n < 1.02:
        print("row +%#x (%.3f %.3f %.3f) unit: atan2(x,z)=%.4f atan2(z,x)=%.4f asin(y)=%.4f" % (off, x, y, z, math.atan2(x, z), math.atan2(z, x), math.asin(max(-1, min(1, y)))))
fwd = f[0x30 // 4:0x30 // 4 + 3]; yaw = math.atan2(fwd[0], fwd[2]); pitch = math.asin(fwd[1])
print("camera forward yaw %.4f pitch %.4f" % (yaw, pitch))
def scan(base, size, tag):
    r = d.proc_read(pid, base, size)
    if not r: return
    g = struct.unpack("<%df" % (size // 4), r[:size // 4 * 4])
    for i, v in enumerate(g):
        for name, want in (("yaw", yaw), ("-yaw", -yaw), ("yaw+pi", yaw + math.pi if yaw < 0 else yaw - math.pi), ("pitch", pitch), ("-pitch", -pitch)):
            if abs(v - want) < 2.5e-3 and abs(want) > 0.05: print("  %s+%#x  %s  (%.4f)" % (tag, i * 4, name, v))
        if abs(v - math.sin(yaw)) < 2.5e-3 and abs(math.sin(yaw)) > 0.1: print("  %s+%#x  sin(yaw) (%.4f)" % (tag, i * 4, v))
        if abs(v - math.cos(yaw)) < 2.5e-3 and abs(math.cos(yaw)) > 0.1: print("  %s+%#x  cos(yaw) (%.4f)" % (tag, i * 4, v))
print("--- follow cam object (0x600)"); scan(cam, 0x600, "cam")
for off, nm in ((0, "manager"),): 
    print("--- manager (0x400)"); scan(mgr, 0x400, "mgr")
