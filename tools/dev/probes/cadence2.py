import sys, struct, time, statistics as st
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); w = q(pl + 0x58); X = q(q(pl + 0x3b0) + 0x68); cam = q(q(q(0x593e860) + 0x2830) + 0x60)
srcs = [("model origin [w+0x350]", w + 0x350), ("physics pos [X+0x1e0]", X + 0x1e0), ("game camera pos [cam+0x40]", cam + 0x40)]
print("pid", pid, "RUN now", flush=True); time.sleep(2)
for name, a in srcs:
    t0 = time.time(); prev = None; tprev = None; ivs = []; n = 0; same = 0
    while time.time() - t0 < 5:
        h = rd(a, 12); t = time.time(); n += 1
        if prev is not None and h == prev: same += 1
        elif prev is not None:
            if tprev is not None: ivs.append((t - tprev) * 1000)
            tprev = t
        else: tprev = t
        prev = h
    print("%-28s %4d samples (%3.0f Hz) identical %3.0f %%  change interval median %.1f ms mean %.1f  changes %d" % (name, n, n / 5, 100 * same / max(n - 1, 1), st.median(ivs) if ivs else float("nan"), st.mean(ivs) if ivs else float("nan"), len(ivs)), flush=True)
