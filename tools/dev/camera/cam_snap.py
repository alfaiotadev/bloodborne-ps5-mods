"""Wide snapshot diff to find the camera angle state. Usage: cam_snap.py save <file> | diff <fileA> <fileB>
Snapshots: roots (world 0x3000, mgr 0x600, cam 0x600, player ChrIns 0x800) + heap pointers inside them (0x400 each) + pointers inside those (0x300 each).
diff: fields whose float delta equals the camera forward-yaw delta (rad) or pitch delta (rad / deg), reported with their absolute address."""
import sys, struct, math, pickle, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000 and v % 8 == 0
def snap():
    world = q(0x593e860); mgr = q(world + 0x2830); cam = q(mgr + 0x60); pl = q(q(0x593e878) + 0x60)
    wins = {}
    def fyaw():
        f = struct.unpack("<3f", d.proc_read(pid, cam + 0x30, 12)); return math.atan2(f[0], f[2]), math.asin(max(-1, min(1, f[1])))
    y_before, p_before = fyaw()
    def add(a, n):
        if a in wins: return None
        r = d.proc_read(pid, a, n); wins[a] = r; return r
    roots = [(world, 0x3000), (mgr, 0x600), (cam, 0x600), (pl, 0x800)]
    lvl1 = []
    for a, n in roots:
        r = add(a, n)
        if r:
            for o in range(0, n, 8):
                p = struct.unpack_from("<Q", r, o)[0]
                if heap(p) and p not in wins: lvl1.append(p)
    lvl1 = list(dict.fromkeys(lvl1)); lvl2 = []
    for p in lvl1:
        r = add(p, 0x400)
        if r:
            for o in range(0, 0x400, 8):
                v = struct.unpack_from("<Q", r, o)[0]
                if heap(v) and v not in wins: lvl2.append(v)
    for p in list(dict.fromkeys(lvl2)): add(p, 0x300)
    y_after, p_after = fyaw()
    return {"cam": cam, "yaw": y_before, "pitch": p_before, "yaw_after": y_after, "pitch_after": p_after, "wins": {a: r for a, r in wins.items() if r}}
a = sys.argv[1:]
if a[0] == "save":
    t = time.time(); s = snap(); pickle.dump(s, open(a[1], "wb"))
    print("saved %s: %d windows, %d KB, %.1fs; yaw %.4f->%.4f pitch %.4f->%.4f  %s" % (a[1], len(s["wins"]), sum(len(r) for r in s["wins"].values()) // 1024, time.time() - t, s["yaw"], s["yaw_after"], s["pitch"], s["pitch_after"], "STATIC" if abs(s["yaw"] - s["yaw_after"]) < 0.002 and abs(s["pitch"] - s["pitch_after"]) < 0.002 else "CAMERA MOVED DURING SNAPSHOT"))
else:
    A, B = pickle.load(open(a[1], "rb")), pickle.load(open(a[2], "rb"))
    dy = B["yaw"] - A["yaw"]; dy = (dy + math.pi) % (2 * math.pi) - math.pi; dp = B["pitch"] - A["pitch"]
    print("camera delta: yaw %.4f rad (%.1f deg)  pitch %.4f rad (%.1f deg)" % (dy, math.degrees(dy), dp, math.degrees(dp)))
    for label, want in (("yaw", dy), ("pitch", dp)):
        if abs(want) < 0.05: print("-- %s delta too small" % label); continue
        print("== fields with delta ~ %s" % label)
        n = 0
        for addr, ra in A["wins"].items():
            rb = B["wins"].get(addr)
            if not rb: continue
            m = min(len(ra), len(rb)) // 4
            fa = struct.unpack("<%df" % m, ra[:m * 4]); fb = struct.unpack("<%df" % m, rb[:m * 4])
            for i in range(m):
                x, y = fa[i], fb[i]
                if not (math.isfinite(x) and math.isfinite(y)): continue
                if x in (0.0, 1.0, -1.0) and y in (0.0, 1.0, -1.0): continue
                dd = y - x
                for tag, w in (("rad", want), ("-rad", -want), ("deg", math.degrees(want)), ("-deg", -math.degrees(want))):
                    if abs(dd - w) < max(0.003, abs(w) * 0.01) and abs(x) < 1000:
                        print("  %#x  %s  %.4f -> %.4f" % (addr + i * 4, tag, x, y)); n += 1
                        if n > 60: break
