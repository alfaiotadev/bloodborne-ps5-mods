#!/usr/bin/env python3
"""Player position read / warp for Bloodborne (ps5debug; needs ps5dbg.py from tools/dev/core).
The game's own SetPosition (0x1cc16a0, used by the debug tool SprjEzSelectBot.PlayerWarp via 0x194b110) does, on
X = [[[[pl+0x58]+8]+0x3b0]+0x68] = [[pl+0x3b0]+0x68]:  X+0x1e0 = X+0x1f0 = pos(x,y,z,1);  word X+0x210 = 0x0101;  byte X+0x32a = 1.
Angles: X+0x1d0 = (pitchRad, yawRad, 0, 0)  (the debug tool's degX/degY * deg2rad).  pl = [[0x593e878]+0x60].
Usage:  player_warp.py read
        player_warp.py nudge dx dy dz [hold_s]   (move by delta, wait, move back; prints readbacks)
        player_warp.py to x y z [yawRad]
        player_warp.py yaw dRad [hold_s]         (turn the character by dRad, wait, restore; prints readbacks)
"""
import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
def wr(a, data):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, len(data))); assert st == 0x80000000, hex(st)
    d.s.sendall(data); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
def base():
    pl = q(q(0x593e878) + 0x60); return pl, q(q(pl + 0x3b0) + 0x68)
def get():
    pl, X = base(); r = d.proc_read(pid, X + 0x1c0, 0x60)
    f = struct.unpack("<24f", r)
    return {"pl": pl, "X": X, "pos": f[8:11], "pos_1f0": f[12:15], "pos_1c0": f[0:3], "ang": f[4:6],
            "flags": struct.unpack("<H", d.proc_read(pid, X + 0x210, 2))[0], "f32a": d.proc_read(pid, X + 0x32a, 1)[0]}
def warp(x, y, z, yaw=None):
    pl, X = base()
    if yaw is not None:
        pitch = struct.unpack("<f", d.proc_read(pid, X + 0x1d0, 4))[0]
        wr(X + 0x1d0, struct.pack("<4f", pitch, yaw, 0.0, 0.0))
    wr(X + 0x1e0, struct.pack("<8f", x, y, z, 1.0, x, y, z, 1.0))   # 0x1e0 and 0x1f0 together
    wr(X + 0x210, struct.pack("<H", 0x0101)); wr(X + 0x32a, b"\x01")
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "read":
        g = get(); print("pl %#x X %#x  pos %.3f %.3f %.3f  (1f0 %.3f %.3f %.3f, 1c0 %.3f %.3f %.3f)  ang %.4f %.4f  flags %#06x f32a %d" % (g["pl"], g["X"], *g["pos"], *g["pos_1f0"], *g["pos_1c0"], *g["ang"], g["flags"], g["f32a"]))
    elif a[0] == "nudge":
        dx, dy, dz = map(float, a[1:4]); hold = float(a[4]) if len(a) > 4 else 1.5
        g = get(); p0 = g["pos"]; print("start", ["%.3f" % v for v in p0])
        warp(p0[0] + dx, p0[1] + dy, p0[2] + dz)
        for t in (0.05, 0.3, hold):
            time.sleep(t if t == 0.05 else (0.25 if t == 0.3 else max(hold - 0.35, 0)))
            g = get(); print("  +%.2fs pos %s flags %#06x f32a %d" % (t, ["%.3f" % v for v in g["pos"]], g["flags"], g["f32a"]))
        warp(*p0); time.sleep(0.5); g = get(); print("back: pos %s flags %#06x" % (["%.3f" % v for v in g["pos"]], g["flags"]))
    elif a[0] == "yaw":
        dyaw = float(a[1]); hold = float(a[2]) if len(a) > 2 else 1.5
        g = get(); y0 = g["ang"][1]; pl, X = base(); print("start yaw %.4f" % y0)
        wr(X + 0x1d0, struct.pack("<4f", g["ang"][0], y0 + dyaw, 0.0, 0.0))
        for t in (0.05, 0.3, hold):
            time.sleep(t if t == 0.05 else (0.25 if t == 0.3 else max(hold - 0.35, 0)))
            g = get(); print("  +%.2fs yaw %.4f pos %s" % (t, g["ang"][1], ["%.3f" % v for v in g["pos"]]))
        wr(X + 0x1d0, struct.pack("<4f", g["ang"][0], y0, 0.0, 0.0)); time.sleep(0.5); g = get(); print("back: yaw %.4f" % g["ang"][1])
    elif a[0] == "to":
        warp(*map(float, a[1:4]), *( [float(a[4])] if len(a) > 4 else [] )); time.sleep(0.5); print(get())
