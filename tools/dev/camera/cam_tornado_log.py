"""Log the follow camera while the user triggers the 'tornado' (head camera ON): every 0.25 s print the game camera's distance to the pivot, the camera distance fields,
the squeeze-hold state and the view yaw/pitch rate.  Usage: cam_tornado_log.py [seconds=12]"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
T = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]; S = scenelib.Scenes(d, pid, {}); S.install()
pl, X, cam = S.chain(); t0 = time.time(); rows = []
def smp():
    f = struct.unpack("<12f", S.rd(cam + 0x10, 0x30)); pp = struct.unpack("<3f", S.rd(X + 0x1e0, 12)); sv = struct.unpack("<3f", S.rd(m.HC_SAVED, 12))
    root = struct.unpack("<3f", S.rd(S.q(pl + 0x58) + 0x350, 12)); dist = math.dist(sv, (root[0], root[1] + 1.42, root[2]))
    fd, cdt, cd = struct.unpack("<3f", S.rd(cam + 0x180, 12)); st = S.rd(m.HC_STATE, 1)[0]
    return time.time() - t0, math.atan2(f[8], f[10]), math.asin(max(-1, min(1, f[9]))), dist, st, fd, cdt, cd
while time.time() - t0 < T: rows.append(smp()); time.sleep(0.008)
def unwrap(v): return [v[0]] + [v[i] if abs(v[i] - v[i - 1]) < math.pi else v[i] - 2 * math.pi * round((v[i] - v[i - 1]) / (2 * math.pi)) for i in range(1, len(v))]
ys = unwrap([r[1] for r in rows]); print("%d samples over %.1fs" % (len(rows), rows[-1][0]))
print(" time  dist(m) hold  yawrate(deg/s) pitch   [+0x180 fulcrum] [+0x184 camDistTgt] [+0x188 camDist]")
step = max(1, len(rows) // 48)
for i in range(step, len(rows), step):
    dt = rows[i][0] - rows[i - step][0]; yr = math.degrees(ys[i] - ys[i - step]) / dt
    print("%5.2f  %6.2f   %d   %9.1f   %6.2f      %6.2f           %6.2f            %6.2f" % (rows[i][0], rows[i][3], rows[i][4], yr, rows[i][2], rows[i][5], rows[i][6], rows[i][7]))
