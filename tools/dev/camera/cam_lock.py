#!/usr/bin/env python3
"""Camera pose lock control over ps5debug (needs ps5dbg.py from tools/dev/core and make_cam_pose_cave.py from tools/dev/mods-live).
  install                      write data block + cave, then the epilogue hook (flag stays 0 = original camera); removes legacy hooks first
  record [file.json name]      read the current final pose (cam+0x10..0x4f) -> print / save as name
  lock [--yaw d] [--pitch d] [--spin]  lock the camera to the CURRENT pose, optionally orbited by d rad around the player (default; the player keeps its screen position) or spun in place (--spin)  [FLAG=1]
  lockpose name file.json      lock to a saved pose
  unlock                       FLAG=0 (original behaviour)
  remove                       FLAG=0, restore both hooks FIRST, then clear caves + data
  status"""
import sys, struct, json, math, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import make_cam_pose_cave as m
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
cam = lambda: q(q(q(0x593e860) + 0x2830) + 0x60)
rd = lambda a, n: d.proc_read(pid, a, n)
def wr(a, data, verify=True):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, len(data))); assert st == 0x80000000, hex(st)
    d.s.sendall(data); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
    if verify: assert rd(a, len(data)) == data, hex(a)
def pose(): return rd(cam() + 0x10, 0x40)              # right, up, forward, position (4 x 16 B)
def yp(p): f = struct.unpack("<16f", p); return math.atan2(f[8], f[10]), math.asin(max(-1, min(1, f[9])))
def player_pos():
    pl = q(q(0x593e878) + 0x60); X = q(q(pl + 0x3b0) + 0x68); return struct.unpack("<3f", rd(X + 0x1e0, 12))
def turned(p, dyaw, dpitch, orbit=True):
    """Rotate the whole camera frame (rows + position) rigidly about the player's world position (orbit) so the player keeps its screen position;
    orbit=False spins the camera in place instead (position kept)."""
    f = list(struct.unpack("<16f", p)); R, U, F = f[0:3], f[4:7], f[8:11]; pos = f[12:15]
    P = player_pos() if orbit else pos
    off = [pos[i] - P[i] for i in range(3)]
    cy, sy = math.cos(dyaw), math.sin(dyaw)
    ry = lambda v: [v[0] * cy + v[2] * sy, v[1], -v[0] * sy + v[2] * cy]          # yaw about world Y (yaw = atan2(x,z) increases)
    R, U, F, off = ry(R), ry(U), ry(F), ry(off)
    cp, sp = math.cos(dpitch), math.sin(dpitch)                                    # pitch about the (new) right axis: look up by dpitch
    F2 = [F[i] * cp + U[i] * sp for i in range(3)]; U2 = [U[i] * cp - F[i] * sp for i in range(3)]
    rot = lambda v: [v[i] for i in range(3)] if False else None
    # offset rotates like the frame: components along (R,U,F) are preserved
    oR = sum(off[i] * R[i] for i in range(3)); oU = sum(off[i] * U[i] for i in range(3)); oF = sum(off[i] * F[i] for i in range(3))
    off2 = [oR * R[i] + oU * U2[i] + oF * F2[i] for i in range(3)]
    pos2 = [P[i] + off2[i] for i in range(3)]
    return struct.pack("<16f", *R, 0.0, *U2, 0.0, *F2, 0.0, *pos2, 1.0)
def set_rows(p): wr(m.ROW0, p)
a = sys.argv[1:]; cmd = a[0] if a else "status"
val = lambda k, dflt: float(a[a.index(k) + 1]) if k in a else dflt
HK = m.hook()
def legacy_cleanup():
    for at, orig in ((m.LEG_A, m.LEG_A_ORIG), (m.LEG_B, m.LEG_B_ORIG)):
        if rd(at, 1) == b"\xe9": wr(at, orig)
if cmd == "install":
    legacy_cleanup(); wr(m.FLAG, bytes(16)); wr(m.ROW0, pose()); wr(m.CAVE, m.build_cave())
    if rd(m.HOOK, 7) != HK: wr(m.HOOK, HK)
    print("installed (flag 0)")
elif cmd == "record":
    p = pose(); y, pt = yp(p); f = struct.unpack("<16f", p); print("pose yaw %.4f pitch %.4f pos %.3f %.3f %.3f" % (y, pt, *f[12:15]))
    if len(a) >= 3:
        db = json.load(open(a[1])) if __import__("os").path.exists(a[1]) else {}
        db[a[2]] = p.hex(); json.dump(db, open(a[1], "w"), indent=1); print("saved", a[2], "->", a[1])
elif cmd == "lock":
    set_rows(turned(pose(), val("--yaw", 0.0), val("--pitch", 0.0), orbit="--spin" not in a)); wr(m.FLAG, b"\x01"); print("LOCKED", "(spin in place)" if "--spin" in a else "(orbit around player)")
elif cmd == "lockpose":
    set_rows(bytes.fromhex(json.load(open(a[2]))[a[1]])); wr(m.FLAG, b"\x01"); print("LOCKED to", a[1])
elif cmd == "unlock":
    wr(m.FLAG, b"\x00"); print("UNLOCKED")
elif cmd == "remove":
    wr(m.FLAG, b"\x00"); legacy_cleanup(); wr(m.HOOK, m.ORIG); wr(m.CAVE, bytes(len(m.build_cave()))); wr(m.ROW0, bytes(0x40)); wr(m.FLAG, bytes(16)); print("REMOVED")
print("status: flag", rd(m.FLAG, 1)[0], "cave runs", struct.unpack("<I", rd(m.CNT, 4))[0], "hook", rd(m.HOOK, 7).hex(), " cam pose yaw/pitch %.4f %.4f" % yp(pose()))
