"""Head-cam ON all the time; every 4 s switch the follow-camera chase fields (cam+0x198.. as float) between the game's values and 1.0 in different sets, and log how much the view yaw
turns while the user circles with the left stick.  Restores the original values at the end.  Usage: cam_chase_log.py"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]; S = scenelib.Scenes(d, pid, {}); S.install()
pl, X, cam = S.chain()
ALL8 = [0x198, 0x19c, 0x1a0, 0x1a4, 0x1a8, 0x1ac, 0x1b0, 0x1b4]; TARGET = [0x1a8, 0x1ac, 0x1b0, 0x1b4]; COLL = [0x18c, 0x190, 0x194]; ALL11 = ALL8 + [0x1c0, 0x1c4, 0x1c8]
orig = {o: struct.unpack("<f", S.rd(cam + o, 4))[0] for o in ALL11 + COLL}
def setf(offs, v):
    for o in offs: S.wr(cam + o, struct.pack("<f", orig[o] if v is None else v), verify=False)
# plan: (name, [(offsets, value), ...])  -- circle with the left stick the whole time
plan = [("normal", []), ("chase all8=1", [(ALL8, 1.0)]), ("normal", []), ("target4=1", [(TARGET, 1.0)]), ("chase all11=1", [(ALL11, 1.0)])]
S.wr(m.HC_FLAG, b"\x01"); rows = []; t0 = time.time()
try:
    for b, (name, offs) in enumerate(plan):
        setf(ALL11 + COLL, None)
        for o_list, v in offs: setf(o_list, v)
        tb = time.time()
        while time.time() - tb < 4.0:
            f = struct.unpack("<12f", S.rd(cam + 0x10, 0x30)); pp = struct.unpack("<3f", S.rd(X + 0x1e0, 12)); sv = struct.unpack("<3f", S.rd(m.HC_SAVED, 12))
            dist = math.dist(sv, (pp[0], pp[1] + 1.42, pp[2])); rows.append((time.time() - t0, b, math.atan2(f[8], f[10]), math.asin(max(-1, min(1, f[9]))), pp, dist)); time.sleep(0.01)
finally:
    setf(ALL11 + COLL, None); S.wr(m.HC_FLAG, b"\x00")
def unwrap(v): return [v[0]] + [v[i] if abs(v[i] - v[i - 1]) < math.pi else v[i] - 2 * math.pi * round((v[i] - v[i - 1]) / (2 * math.pi)) for i in range(1, len(v))]
for b, (name, offs) in enumerate(plan):
    rb = [r for r in rows if r[1] == b]
    if len(rb) < 3: continue
    ys = unwrap([r[2] for r in rb]); dt = rb[-1][0] - rb[0][0]; path = sum(abs(ys[i] - ys[i - 1]) for i in range(1, len(ys)))
    print("block %d %-12s %3d samples  yaw net %7.1f deg  total %7.1f deg (%6.1f deg/s)  pitch %.2f..%.2f  player moved %.2f m  game cam dist to pivot %.2f..%.2f m" % (b, name, len(rb), math.degrees(ys[-1] - ys[0]), math.degrees(path), math.degrees(path) / dt, min(r[3] for r in rb), max(r[3] for r in rb), math.dist(rb[0][4], rb[-1][4]), min(r[5] for r in rb), max(r[5] for r in rb)))
