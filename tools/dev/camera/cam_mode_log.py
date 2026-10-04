"""Compare head-camera sub-features while the user wiggles the RIGHT stick: blocks of 4 s with different settings; prints the yaw/pitch behaviour per block
(number of >0.5 rad pitch jumps per second = 'tornado' indicator).  Usage: cam_mode_log.py"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]; S = scenelib.Scenes(d, pid, {}); S.install()
pl, X, cam = S.chain()
e2_save = struct.unpack("<f", S.rd(m.HC_ENTER2, 4))[0]
def cfg(flag, coll, hold):
    S.wr(m.HC_NOCOLL, bytes([1 if coll == "off" else 0])); S.wr(m.HC_ENTER2, struct.pack("<f", e2_save if hold else 0.0)); S.wr(m.HC_FLAG, bytes([1 if flag else 0]), verify=False)
plan = [("head OFF", (0, "on", 1)), ("ON coll=on hold=off", (1, "on", 0)), ("ON coll=off hold=off", (1, "off", 0)), ("ON coll=off hold=on", (1, "off", 1)), ("head OFF", (0, "on", 1))]
rows = []; t0 = time.time()
try:
    for b, (name, c) in enumerate(plan):
        cfg(*c); tb = time.time()
        while time.time() - tb < 4.0:
            f = struct.unpack("<12f", S.rd(cam + 0x10, 0x30)); rows.append((time.time() - t0, b, math.atan2(f[8], f[10]), math.asin(max(-1, min(1, f[9]))))); time.sleep(0.004)
finally:
    cfg(1, "off", 1)
def unwrap(v): return [v[0]] + [v[i] if abs(v[i] - v[i - 1]) < math.pi else v[i] - 2 * math.pi * round((v[i] - v[i - 1]) / (2 * math.pi)) for i in range(1, len(v))]
for b, (name, c) in enumerate(plan):
    rb = [r for r in rows if r[1] == b]
    if len(rb) < 3: continue
    ys = unwrap([r[2] for r in rb]); ps = [r[3] for r in rb]; dt = rb[-1][0] - rb[0][0]
    jumps = sum(1 for i in range(1, len(ps)) if abs(ps[i] - ps[i - 1]) > 0.5); path = sum(abs(ys[i] - ys[i - 1]) for i in range(1, len(ys)))
    print("block %d %-22s %3d samples  pitch %.2f..%.2f  pitch jumps/s %5.1f  yaw total %7.0f deg (%6.0f deg/s)" % (b, name, len(rb), min(ps), max(ps), jumps / dt, math.degrees(path), math.degrees(path) / dt))
