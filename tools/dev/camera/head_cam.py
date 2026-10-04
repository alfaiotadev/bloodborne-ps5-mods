#!/usr/bin/env python3
"""Head-bolted camera control (needs tools/dev/core: ps5dbg.py, scenelib.py; and mods-live/make_cam_pose_cave.py).
  head_cam.py install | status | remove
  head_cam.py on  [--mode mgr|epi] [--r 0.0] [--u 0.08] [--f 0.15] [--bone 78] [--enter 1.5] [--leave 2.0]   camera position := player's head bone + R/U/F metres along the camera's right/up/forward (orientation = the game's own, pad-driven);
                  squeeze hold: while the game's own camera is closer than --enter metres to the pivot (camera squeezed against a wall) the last good orientation is shown, until it is farther than --leave (--enter 0 = off)
  head_cam.py face2 on|off                                         DISPLAY-ONLY facing: the model->world rows are rotated so the body/arms point along the camera (game state and movement untouched)
  head_cam.py face on|off [--off rad]                              the player's body faces the camera direction every frame (FPS look); --off = yaw offset in radians
  head_cam.py coll off|on                                         camera collision for the game's own camera (off = no pull-in against walls)
  modes: mgr (default) = position overridden only in the camera MANAGER's output pose (game's follow camera state untouched);  epi = old way (override at the follow camera's epilogue + restore at its entry)
  head_cam.py set [--r ..] [--u ..] [--f ..]                      change the offsets live
  head_cam.py off                                                 back to the normal third-person camera (the game's own position row is handed back)"""
import sys, struct, time, json
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
S = scenelib.Scenes(d, pid, {})
a = sys.argv[1:]; cmd = a[0] if a else "status"
val = lambda k: float(a[a.index(k) + 1]) if k in a else None
def put(r=None, u=None, f=None, bone=None, enter=None, leave=None):
    b, R, U, F, e2, l2 = struct.unpack("<ifffff", S.rd(m.HC_BONEOFF, 24))
    if bone is not None: b = int(bone) * 0x30
    if enter is not None: e2 = enter * enter
    if leave is not None: l2 = leave * leave
    S.wr(m.HC_BONEOFF, struct.pack("<ifffff", b, R if r is None else r, U if u is None else u, F if f is None else f, e2, l2))
def status():
    f, v, hold, good = S.rd(m.HC_FLAG, 4); b, R, U, F, e2, l2 = struct.unpack("<ifffff", S.rd(m.HC_BONEOFF, 24)); runs = struct.unpack("<I", S.rd(m.CNT, 4))[0]
    print("head cam flag=%d mgr-mode=%d valid=%d hold=%d bone=%d  R/U/F=%.3f/%.3f/%.3f  squeeze hold enter %.2f m leave %.2f m  camera collision %s  cave runs %d  hooks %s %s %s" % (f, S.rd(m.HC_FLAG2, 1)[0], v, hold, b // 0x30, R, U, F, e2 ** 0.5, l2 ** 0.5, "OFF" if S.rd(m.HC_NOCOLL, 1)[0] else "on", runs, S.rd(m.HOOK, 7).hex(), S.rd(m.HOOK_E, 6).hex(), S.rd(m.HOOK_C, 6).hex()))
if cmd == "install": S.install(); status()
elif cmd == "on":
    mode = a[a.index("--mode") + 1] if "--mode" in a else "mgr"
    S.install(); put(val("--r"), val("--u"), val("--f"), val("--bone"), val("--enter"), val("--leave")); S.wr(m.HC_NOCOLL, b"\x01")
    S.wr(m.HC_FLAG, b"\x01" if mode == "epi" else b"\x00"); S.wr(m.HC_FLAG2, b"\x01" if mode == "mgr" else b"\x00"); time.sleep(0.3); status()
elif cmd == "set": put(val("--r"), val("--u"), val("--f"), val("--bone"), val("--enter"), val("--leave")); status()
elif cmd == "face2":
    S.install(); S.wr(m.HC_FACE2, b"\x01" if a[1] == "on" else b"\x00"); time.sleep(0.3); print("face2", a[1]); status()
elif cmd == "face":
    S.install()
    if "--off" in a: S.wr(m.HC_FACEOFF, struct.pack("<f", float(a[a.index("--off") + 1])))
    S.wr(m.HC_FACE, b"\x01" if a[1] == "on" else b"\x00"); time.sleep(0.3); print("face-camera", a[1], "offset %.3f rad" % struct.unpack("<f", S.rd(m.HC_FACEOFF, 4))[0]); status()
elif cmd == "coll": S.wr(m.HC_NOCOLL, b"\x01" if a[1] == "off" else b"\x00"); status()
elif cmd == "off": S.wr(m.HC_FLAG, b"\x00"); S.wr(m.HC_FLAG2, b"\x00"); S.wr(m.HC_NOCOLL, b"\x00"); time.sleep(0.3); status()
elif cmd == "remove": S.remove(); print("removed")
else: status()
