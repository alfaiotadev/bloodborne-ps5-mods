"""Does the head bone's look direction follow the camera (right stick) or the body?  Logs head forward yaw/pitch (local +z of bone 78 -> world), the game camera yaw/pitch and the body yaw
(model->world row for model z) every ~50 ms while the user turns the camera with the right stick standing still.  Read-only.  Usage: head_look_log.py [seconds=8]"""
import sys, struct, math, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
T = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q64 = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl = q64(q64(0x593e878) + 0x60); m = q64(pl + 0x58); arr = q64(q64(pl + 0xa68) + 0x50); cam = q64(q64(q64(0x593e860) + 0x2830) + 0x60)
def rot(qv, v):
    x, y, z, w = qv; cx, cy, cz = y * v[2] - z * v[1], z * v[0] - x * v[2], x * v[1] - y * v[0]; dx, dy, dz = y * cz - z * cy, z * cx - x * cz, x * cy - y * cx
    return (v[0] + 2 * (w * cx + dx), v[1] + 2 * (w * cy + dy), v[2] + 2 * (w * cz + dz))
yaw = lambda v: math.degrees(math.atan2(v[0], v[2])); pit = lambda v: math.degrees(math.asin(max(-1, min(1, v[1]))))
rows = []; t0 = time.time()
while time.time() - t0 < T:
    R = [struct.unpack("<3f", d.proc_read(pid, m + 0x320 + 16 * i, 12)) for i in range(3)]; tow = lambda v: tuple(v[0] * R[0][k] + v[1] * R[1][k] + v[2] * R[2][k] for k in range(3))
    qv = struct.unpack("<4f", d.proc_read(pid, arr + 78 * 0x30 + 0x10, 16)); hf = tow(rot(qv, (0, 0, 1)))
    cf = struct.unpack("<3f", d.proc_read(pid, cam + 0x30, 12)); body = tow((0, 0, 1))
    rows.append((time.time() - t0, yaw(hf), pit(hf), yaw(cf), pit(cf), yaw(body))); time.sleep(0.04)
def unwrap(v): return [v[0]] + [v[i] if abs(v[i] - v[i - 1]) < 180 else v[i] - 360 * round((v[i] - v[i - 1]) / 360) for i in range(1, len(v))]
H, C, B = unwrap([r[1] for r in rows]), unwrap([r[3] for r in rows]), unwrap([r[5] for r in rows])
print("  t    headYaw camYaw bodyYaw | headPitch camPitch")
for i in range(0, len(rows), max(1, len(rows) // 24)): print("%5.2f %8.1f %7.1f %7.1f | %8.1f %8.1f" % (rows[i][0], H[i], C[i], B[i], rows[i][2], rows[i][4]))
def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b); c = sum((x - ma) * (y - mb) for x, y in zip(a, b)); va = sum((x - ma) ** 2 for x in a); vb = sum((y - mb) ** 2 for y in b); return c / math.sqrt(va * vb) if va > 1e-9 and vb > 1e-9 else float("nan")
print("camera yaw range %.0f deg;  corr(head yaw, cam yaw) %.2f   corr(body yaw, cam yaw) %.2f   head-yaw range %.0f  body-yaw range %.0f" % (max(C) - min(C), corr(H, C), corr(B, C), max(H) - min(H), max(B) - min(B)))
