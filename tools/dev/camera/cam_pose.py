"""Set the follow camera's orientation by writing its direction matrix (cam+0x10 right, +0x20 up, +0x30 forward; the update integrates
new = delta * old, so the matrix is the camera's state). yaw = atan2(fwd.x, fwd.z), pitch = asin(fwd.y).
Usage: cam_pose.py read | turn dYaw [dPitch] [hold_s] | to yaw pitch"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
mgr = q(q(0x593e860) + 0x2830); cam = q(mgr + 0x60)
def rows(yaw, pitch):
    sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
    return struct.pack("<12f", cy, 0, -sy, 0,   -sp * sy, cp, -sp * cy, 0,   cp * sy, sp, cp * cy, 0)
def get():
    raw = d.proc_read(pid, (mgr if "--mgr" in sys.argv else cam) + 0x10, 0x30); f = struct.unpack("<12f", raw)
    return raw, math.atan2(f[8], f[10]), math.asin(max(-1, min(1, f[9])))
BLOCKS = [(mgr, 0x10), (cam, 0x10), (cam, 0x2e0)] if "--mgr" in sys.argv else ([(cam, 0x2e0), (cam, 0x10)] if "--both" in sys.argv else [(cam, 0x10)])
def wr(data):
    for base, off in BLOCKS:
        st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, base + off, len(data))); assert st == 0x80000000
        d.s.sendall(data); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
a = [x for x in sys.argv[1:] if x not in ("--both", "--mgr")]
raw0, y0, p0 = get()
if not a or a[0] == "read": print("yaw %.4f pitch %.4f" % (y0, p0))
elif a[0] == "turn":
    dy = float(a[1]); dp = float(a[2]) if len(a) > 2 else 0.0; hold = float(a[3]) if len(a) > 3 else 2.5
    print("start yaw %.4f pitch %.4f" % (y0, p0)); wr(rows(y0 + dy, p0 + dp))
    for t in (0.1, 0.5, hold):
        time.sleep(t if t == 0.1 else (0.4 if t == 0.5 else max(hold - 0.6, 0))); _, y, p = get(); print("  +%.1fs yaw %.4f pitch %.4f" % (t, y, p))
    wr(raw0); time.sleep(1.0); _, y, p = get(); print("restored: yaw %.4f pitch %.4f" % (y, p))
elif a[0] == "to":
    wr(rows(float(a[1]), float(a[2]))); time.sleep(0.5); _, y, p = get(); print("yaw %.4f pitch %.4f" % (y, p))
