"""PoC: make the player's body face the camera direction every frame (FPS look).  Per iteration: yaw = camera forward yaw - pi (player yaw convention), write X+0x1d0 = (0, yaw, 0, 0)
and call the game's 0x1cbcf30(pl, 1) through the call service.  Host-side loop (~30-60 Hz).  Usage: face_cam.py [seconds=10] [--off PI_OFFSET_RAD]"""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
T = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else 10.0
off = float(sys.argv[sys.argv.index("--off") + 1]) if "--off" in sys.argv else 0.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]; S = scenelib.Scenes(d, pid, {}); S.install()
pl, X, cam = S.chain(); t0 = time.time(); n = 0
wrap = lambda a: (a + math.pi) % (2 * math.pi) - math.pi
while time.time() - t0 < T:
    f = struct.unpack("<3f", S.rd(cam + 0x30, 12)); yaw = wrap(math.atan2(f[0], f[2]) - math.pi + off)
    S.wr(X + 0x1d0, struct.pack("<4f", 0.0, yaw, 0.0, 0.0), verify=False)
    S.call(0x1CBCF30, pl, 1, settle=0.0); n += 1
print("%d iterations in %.1fs (%.1f Hz)" % (n, time.time() - t0, n / (time.time() - t0)))
