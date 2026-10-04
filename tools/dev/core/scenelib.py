"""Scene library: repeatable player position + camera pose for Bloodborne (host side; used by scene.py and ab_loop.py).
A scene = player world position + yaw + the final camera pose (right/up/forward/position rows); see make_cam_pose_cave.py for the hook design.
  S = Scenes(d, pid, db)       d = connected ps5dbg.Dbg, pid = eboot pid, db = dict loaded from scenes.json
  S.install()                  pose-lock/call-service cave + epilogue hook (safe re-install: unhook first, never rewrite a live cave)
  S.go(name, wait)             lock camera to the scene pose, game-warp the player (same map only), wait for textures; returns position error (m)
  S.release() / S.remove()     camera lock off / remove hook + cave (back to the original code)
A plain warp never unloads textures (the elevator does), so visit every scene once (warm-up) before measured passes."""
import struct, math, time, sys
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
import make_cam_pose_cave as m
class Scenes:
    def __init__(self, d, pid, db):
        self.d, self.pid, self.db = d, pid, db
    def rd(self, x, n): return self.d.proc_read(self.pid, x, n)
    def q(self, x): return struct.unpack("<Q", self.rd(x, 8))[0]
    def wr(self, x, data, verify=True):
        st = self.d.cmd(0xBDAA0003, struct.pack("<IQI", self.pid, x, len(data))); assert st == 0x80000000, hex(st)
        self.d.s.sendall(data); assert struct.unpack("<I", self.d._recvn(4))[0] == 0x80000000
        if verify: assert self.rd(x, len(data)) == data, hex(x)
    def chain(self):
        pl = self.q(self.q(0x593e878) + 0x60); X = self.q(self.q(pl + 0x3b0) + 0x68); cam = self.q(self.q(self.q(0x593e860) + 0x2830) + 0x60); return pl, X, cam
    def install(self):
        for at, orig in ((m.LEG_A, m.LEG_A_ORIG), (m.LEG_B, m.LEG_B_ORIG)):
            if self.rd(at, 1) == b"\xe9": self.wr(at, orig)
        cave, cave_e, cave_c, cave_m, hk, hk_e, hk_c, hk_m = m.build_cave(), m.build_cave_entry(), m.build_cave_cast(), m.build_cave_mgr(), m.hook(), m.hook_entry(), m.hook_cast(), m.hook_mgr()
        hooked = self.rd(m.HOOK, 7) == hk and self.rd(m.HOOK_E, 6) == hk_e and self.rd(m.HOOK_C, 6) == hk_c and self.rd(m.HOOK_M, 5) == hk_m
        if hooked and self.rd(m.CAVE, len(cave)) == cave and self.rd(m.CAVE_E, len(cave_e)) == cave_e and self.rd(m.CAVE_C, len(cave_c)) == cave_c and self.rd(m.CAVE_M, len(cave_m)) == cave_m: return
        if self.rd(m.HOOK, 1) == b"\xe9": self.wr(m.HOOK, m.ORIG)               # never rewrite a live cave: unhook first
        if self.rd(m.HOOK_E, 1) == b"\xe9": self.wr(m.HOOK_E, m.ORIG_E)
        if self.rd(m.HOOK_C, 1) == b"\xe9": self.wr(m.HOOK_C, m.ORIG_C)
        if self.rd(m.HOOK_M, 1) == b"\xe9": self.wr(m.HOOK_M, m.ORIG_M)
        time.sleep(0.05)
        pl, X, cam = self.chain(); self.wr(m.FLAG, bytes(16)); self.wr(m.ROW0, self.rd(cam + 0x10, 0x40))
        self.wr(m.HC_FLAG, struct.pack("<BBBBifffff", 0, 0, 0, 0, 78 * 0x30, 0.0, 0.08, 0.15, 1.5 ** 2, 2.0 ** 2))   # head cam off; bone 78 (Head); offsets R/U/F; squeeze hold enter 1.5 m / leave 2.0 m
        self.wr(m.HC_PIVOT, struct.pack("<4f", 0.0, 1.42, 0.0, 0.0)); self.wr(m.HC_NOCOLL, b"\x00"); self.wr(m.HC_FLAG2, b"\x00"); self.wr(m.HC_FACE, b"\x00"); self.wr(m.HC_FACE2, b"\x00"); self.wr(m.C_PI, struct.pack("<ffff", math.pi, -math.pi, 2 * math.pi, 0.0))
        self.wr(m.CAVE, cave); self.wr(m.CAVE_E, cave_e); self.wr(m.CAVE_C, cave_c); self.wr(m.CAVE_M, cave_m); self.wr(m.HOOK, hk); self.wr(m.HOOK_E, hk_e); self.wr(m.HOOK_C, hk_c); self.wr(m.HOOK_M, hk_m)
    def call(self, fn, a0=0, a1=0, a2=0, a3=0, timeout=1.0, settle=0.03):
        """Run fn(a0..a3) on the game thread (next camera update); returns rax."""
        self.wr(m.FN, struct.pack("<5Q", fn, a0, a1, a2, a3)); self.wr(m.RET, bytes(8)); self.wr(m.CALL, b"\x01", verify=False)   # cave consumes CALL within a frame: no read-back
        t0 = time.time()
        while self.rd(m.CALL, 1) != b"\x00":
            if time.time() - t0 > timeout: self.wr(m.CALL, b"\x00", verify=False); raise RuntimeError("call service timed out (camera update not running?)")
            time.sleep(0.005)
        time.sleep(settle); return struct.unpack("<Q", self.rd(m.RET, 8))[0]
    def warp(self, pos, yaw=None):
        """The game's own warp 0x194b110(ctx=[0x593b148], &mapId, &pos, &rot) via the call service: moves physics, sets the character yaw."""
        pl, X, cam = self.chain()
        if yaw is None: yaw = struct.unpack("<f", self.rd(X + 0x1d4, 4))[0]
        self.wr(m.MAPID, self.rd(pl + 0x3f8, 4)); self.wr(m.POS, struct.pack("<4f", *pos, 1.0)); self.wr(m.ROT, struct.pack("<4f", 0.0, yaw, 0.0, 0.0))
        return self.call(0x194B110, self.q(0x593b148), m.MAPID, m.POS, m.ROT)
    def lock(self, name): self.wr(m.ROW0, bytes.fromhex(self.db[name]["cam"])); self.wr(m.FLAG, b"\x01")
    def go(self, name, wait=5.0, keep_yaw=False):
        s = self.db[name]; pl, X, cam = self.chain()
        cur = struct.unpack("<I", self.rd(pl + 0x3f8, 4))[0]
        if cur != s["map"]: raise RuntimeError("scene %s: map differs (now %#x, scene %#x) - same-map warps only" % (name, cur, s["map"]))
        self.install(); self.lock(name)                                            # camera first (absolute pose), then the player
        self.warp(s["player_pos"], None if keep_yaw else s["player_yaw"]); time.sleep(wait)
        g = struct.unpack("<3f", self.rd(X + 0x1e0, 12)); return math.dist(g, s["player_pos"])
    def release(self): self.wr(m.FLAG, b"\x00")
    def remove(self):
        self.wr(m.FLAG, b"\x00"); self.wr(m.HC_FLAG, b"\x00"); self.wr(m.HC_FLAG2, b"\x00"); self.wr(m.HC_NOCOLL, b"\x00"); self.wr(m.HC_FACE, b"\x00"); self.wr(m.HC_FACE2, b"\x00"); time.sleep(0.15)               # a few frames: the entry cave hands the game its own position row back
        self.wr(m.HOOK, m.ORIG); self.wr(m.HOOK_E, m.ORIG_E); self.wr(m.HOOK_C, m.ORIG_C); self.wr(m.HOOK_M, m.ORIG_M); time.sleep(0.05)
        self.wr(m.CAVE, bytes(len(m.build_cave()))); self.wr(m.CAVE_E, bytes(len(m.build_cave_entry()))); self.wr(m.CAVE_C, bytes(len(m.build_cave_cast()))); self.wr(m.CAVE_M, bytes(len(m.build_cave_mgr()))); self.wr(m.HC_NOCOLL, b"\x00"); self.wr(m.ROW0, bytes(0x40)); self.wr(m.FLAG, bytes(16)); self.wr(m.HC_FLAG, bytes(0x90))
