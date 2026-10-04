"""Log the camera yaw rate (deg/s) while the player walks, toggling the head camera ON/OFF in 4 s blocks (OFF, ON, OFF, ON by default). Installs the head cave if needed.
Usage: cam_spin_log.py [blocks=4] [block_s=4]   (the user holds the left stick forward during the run)"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
blocks = int(sys.argv[1]) if len(sys.argv) > 1 else 4; bs = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]; S = scenelib.Scenes(d, pid, {})
S.install()
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
def sample():
    pl, X, cam = S.chain(); mgr = q(q(0x593e860) + 0x2830); f = struct.unpack("<12f", d.proc_read(pid, cam + 0x10, 0x30)); fm = struct.unpack("<12f", d.proc_read(pid, mgr + 0x10, 0x30))
    pos = struct.unpack("<3f", d.proc_read(pid, X + 0x1e0, 12)); saved = struct.unpack("<3f", d.proc_read(pid, m.HC_SAVED, 12)); camp = struct.unpack("<3f", d.proc_read(pid, cam + 0x40, 12))
    w = struct.unpack('<5f', d.proc_read(pid, cam + 0x110, 20))      # cam+0x110 vec4, +0x120, ... ; +0x124 = angular rate used by the update
    return math.atan2(f[8], f[10]), math.asin(max(-1, min(1, f[9]))), math.atan2(fm[8], fm[10]), pos, saved, camp, d.proc_read(pid, cam + 0x124, 4), w
rows = []; t0 = time.time()
for b in range(blocks):
    on = b % 2 == 1; S.wr(m.HC_FLAG, b"\x01" if on else b"\x00"); tb = time.time()
    while time.time() - tb < bs:
        rows.append((time.time() - t0, on, b) + sample()); time.sleep(0.01)
S.wr(m.HC_FLAG, b"\x00")
def unwrap(v): return [v[0]] + [v[i] if abs(v[i] - v[i - 1]) < math.pi else v[i] - 2 * math.pi * round((v[i] - v[i - 1]) / (2 * math.pi)) for i in range(1, len(v))]
for b in range(blocks):
    rb = [r for r in rows if r[2] == b]
    if len(rb) < 3: continue
    w124 = [struct.unpack('<f', r[9][:4])[0] for r in rb]; ysr = unwrap([r[3] for r in rb]); rate = [(ysr[i] - ysr[i - 1]) / max(rb[i][0] - rb[i - 1][0], 1e-3) for i in range(1, len(ysr))]
    n = len(rate); mx = sum(w124[1:]) / n; my = sum(rate) / n; cov = sum((a - mx) * (b - my) for a, b in zip(w124[1:], rate)); vx = sum((a - mx) ** 2 for a in w124[1:]); vy = sum((b - my) ** 2 for b in rate)
    corr = cov / math.sqrt(vx * vy) if vx > 1e-12 and vy > 1e-12 else float('nan')
    print('   [cam+0x124] range %.3f..%.3f  corr(yaw rate, [+0x124]) %.2f' % (min(w124), max(w124), corr))
    ys = unwrap([r[3] for r in rb]); ym = unwrap([r[5] for r in rb]); dt = rb[-1][0] - rb[0][0]
    pp = math.dist(rb[0][6], rb[-1][6]); path = sum(abs(ys[i] - ys[i - 1]) for i in range(1, len(ys)))
    print("block %d head-cam %-3s  %3d samples %.1fs  cam yaw net %7.1f deg, total turned %7.1f deg (%6.1f deg/s)  mgr yaw net %7.1f deg  pitch %.2f..%.2f  player moved %.2f m" % (b, "ON" if rb[0][1] else "OFF", len(rb), dt, math.degrees(ys[-1] - ys[0]), math.degrees(path), math.degrees(path) / dt, math.degrees(ym[-1] - ym[0]), min(r[4] for r in rb), max(r[4] for r in rb), pp))
