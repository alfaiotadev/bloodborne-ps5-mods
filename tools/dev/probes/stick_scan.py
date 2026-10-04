"""Find the LEFT stick values in memory.  Takes 5 snapshots of the player's object graph (+ WorldChrMan) while the user holds: idle, forward, back, left, right (on-screen toast cues),
then reports float fields that behave like a stick axis: X: left/right = opposite +-1, others ~0;  Y: forward/back = opposite +-1, others ~0.  Usage: stick_scan.py [hold_s=6]"""
import sys, struct, time, subprocess, pickle
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath, toast
from ps5dbg import Dbg
HOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000 and v % 8 == 0
wcm = q(0x593e878); pl = q(wcm + 0x60)
def windows():
    seen = {pl, wcm}; queue = [(pl, 0), (wcm, 0)]; wins = {}
    while queue and len(wins) < 5000:
        a, depth = queue.pop(0); r = d.proc_read(pid, a, 0x1000)
        if not r: continue
        wins[a] = r
        if depth < 3:
            for o in range(0, len(r) - 7, 8):
                p = struct.unpack_from("<Q", r, o)[0]
                if heap(p) and p not in seen: seen.add(p); queue.append((p, depth + 1))
    return wins
# the window set is fixed from the first (idle) snapshot; later snapshots re-read the same addresses
names = ["idle (no stick)", "FORWARD", "BACK", "LEFT", "RIGHT"]; snaps = []
addrs = None
for i, nm in enumerate(names):
    toast("Left stick: %s - hold %d s (do not touch the right stick)" % (nm, HOLD)); print("cue:", nm, flush=True); time.sleep(HOLD * 0.45)
    if addrs is None: w = windows(); addrs = list(w); snaps.append(w)
    else: snaps.append({a: d.proc_read(pid, a, 0x1000) for a in addrs})
    time.sleep(max(0.0, HOLD * 0.55 - 1.0))
toast("Stick mapping done"); pickle.dump(snaps, open(workpath("stick_snaps.pkl"), "wb"))
def fl(r, i): return struct.unpack_from("<f", r, i * 4)[0]
cx, cy = [], []
for a in snaps[0]:
    rs = [s.get(a) for s in snaps]
    if any(r is None for r in rs): continue
    for i in range(len(rs[0]) // 4):
        v = [fl(r, i) for r in rs]
        if not all(abs(x) < 1e6 and x == x for x in v): continue
        z = lambda x: abs(x) < 0.15; big = lambda x: abs(x) > 0.5
        if z(v[0]) and big(v[3]) and big(v[4]) and v[3] * v[4] < 0 and z(v[1]) and z(v[2]): cx.append((a + i * 4, v))
        if z(v[0]) and big(v[1]) and big(v[2]) and v[1] * v[2] < 0 and z(v[3]) and z(v[4]): cy.append((a + i * 4, v))
print("X-axis candidates:", len(cx)); [print("  %#x  %s" % (a, ["%.2f" % x for x in v])) for a, v in cx[:25]]
print("Y-axis candidates:", len(cy)); [print("  %#x  %s" % (a, ["%.2f" % x for x in v])) for a, v in cy[:25]]
