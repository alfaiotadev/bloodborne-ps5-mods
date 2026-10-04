"""Find the player's position floats: scan ChrIns (and one pointer level below it) for float triples near the follow-camera position (read-only).
Usage: python3 find_player_pos.py [radius_m]"""
import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
R = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000
wcm = q(0x593e878); pl = q(wcm + 0x60)
mgr = q(q(0x593e860) + 0x2830); cam = q(mgr + 0x60)
cp = struct.unpack("<3f", d.proc_read(pid, cam + 0x40, 12))
print("player ChrIns %#x   follow cam %#x   cam pos (%.3f, %.3f, %.3f)" % (pl, cam, *cp))
def triples(base, size, tag):
    raw = d.proc_read(pid, base, size)
    if not raw: return
    for o in range(0, size - 12, 4):
        f = struct.unpack_from("<3f", raw, o)
        if all(abs(f[i] - cp[i]) < R for i in range(3)):
            dist = sum((f[i] - cp[i]) ** 2 for i in range(3)) ** 0.5
            print("  %s+%#x  (%.3f, %.3f, %.3f)  |d cam|=%.2f" % (tag, o, *f, dist))
print("--- ChrIns direct (0x800)")
triples(pl, 0x800, "pl")
raw = d.proc_read(pid, pl, 0x800)
seen = set()
for o in range(0, 0x800, 8):
    p = struct.unpack_from("<Q", raw, o)[0]
    if heap(p) and p not in seen and p != pl:
        seen.add(p)
        sub = d.proc_read(pid, p, 0x400)
        if sub:
            hits = []
            for so in range(0, 0x400 - 12, 4):
                f = struct.unpack_from("<3f", sub, so)
                if all(abs(f[i] - cp[i]) < R for i in range(3)): hits.append((so, f))
            if hits:
                print("--- [pl+%#x] -> %#x" % (o, p))
                for so, f in hits: print("  +%#x  (%.3f, %.3f, %.3f)  |d cam|=%.2f" % (so, *f, sum((f[i] - cp[i]) ** 2 for i in range(3)) ** 0.5))
