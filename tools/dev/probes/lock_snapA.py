"""Stage 1 (locked on): BFS the player object graph, save all windows to $PS5_WORKDIR/lockA.pkl."""
import sys, struct, time, pickle
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
ok = lambda v: 0x200000000 <= v < 0x400000000 and v % 8 == 0
wcm = q(0x593e878); pl = q(wcm + 0x60); cam = q(q(q(0x593e860) + 0x2830) + 0x60); mgr = q(q(0x593e860) + 0x2830)
roots = [pl, cam, mgr, wcm]; queue = [(a, 0) for a in roots]; seen = set(roots); wins = {}; t0 = time.time(); par = {}
while queue and len(wins) < 3500 and time.time() - t0 < 60:
    a, dep = queue.pop(0); b = rd(a, 0x400)
    if not b: continue
    wins[a] = b
    if dep < 4:
        for o in range(0, 0x3f9, 8):
            p = struct.unpack_from("<Q", b, o)[0]
            if ok(p) and p not in seen: seen.add(p); par[p] = (a, o); queue.append((p, dep + 1))
pickle.dump({"wins": wins, "par": par, "roots": {"pl": pl, "cam": cam, "mgr": mgr, "wcm": wcm}, "t": time.time()}, open(workpath("lockA.pkl"), "wb"))
print("stage A saved: %d windows in %.0f s (locked state)" % (len(wins), time.time() - t0))
