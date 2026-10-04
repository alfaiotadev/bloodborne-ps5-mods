"""Right-stick tornado diagnosis (head camera ON): per sample log the displayed rows' yaw/pitch, the direction of the game's OWN camera (HC_SAVED) from the pivot, and the pad rotation fields
cam+0x110..0x124.  Prints the first strong pitch-flip episode in detail.  Usage: cam_pad_log.py [seconds=8]"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
T = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]; S = scenelib.Scenes(d, pid, {}); S.install()
pl, X, cam = S.chain(); rows = []; t0 = time.time()
S.wr(m.HC_FLAG, b"\x01", verify=False)
while time.time() - t0 < T:
    f = struct.unpack("<12f", S.rd(cam + 0x10, 0x30)); sv = struct.unpack("<3f", S.rd(m.HC_SAVED, 12)); root = struct.unpack("<3f", S.rd(S.q(pl + 0x58) + 0x350, 12))
    v = [sv[0] - root[0], sv[1] - (root[1] + 1.42), sv[2] - root[2]]; n = math.sqrt(sum(a * a for a in v)) or 1e-9
    pad = struct.unpack("<5f", S.rd(cam + 0x110, 20)); camp = struct.unpack("<3f", S.rd(cam + 0x40, 12))
    rows.append((time.time() - t0, math.degrees(math.atan2(f[8], f[10])), math.degrees(math.asin(max(-1, min(1, f[9])))), math.degrees(math.atan2(-v[0], -v[2])), math.degrees(math.asin(max(-1, min(1, -v[1] / n)))), n, pad, camp, sv))
    time.sleep(0.002)
S.wr(m.HC_FLAG, b"\x00", verify=False)
print("%d samples" % len(rows))
flips = [i for i in range(1, len(rows)) if abs(rows[i][2] - rows[i - 1][2]) > 30]
print("pitch flips >30 deg between samples:", len(flips))
if flips:
    i0 = max(0, flips[0] - 4)
    print(" t     rowsYaw rowsPitch | gameCam-dir yaw pitch dist | pad110..124 | head-cam pos vs game pos distance")
    for r in rows[i0:i0 + 18]:
        print("%5.2f %8.1f %8.1f | %8.1f %7.1f %5.2f | %s | %.2f" % (r[0], r[1], r[2], r[3], r[4], r[5], " ".join("%6.2f" % x for x in r[6]), math.dist(r[7], r[8])))
