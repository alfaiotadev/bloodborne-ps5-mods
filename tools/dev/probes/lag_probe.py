"""Waits until the player runs, then samples the animated world-bone arrays and the model->world translation for ~15 s to find which copy is newer."""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); obj = q(mod + 0x18); w = q(pl + 0x58)
def wt(): return struct.unpack("<3f", rd(w + 0x350, 12))
raw = rd(obj, 0x700)
def snap(a): r = rd(a, 0x30 * 170); f = struct.unpack("<2040f", r[:8160]); return [(f[12 * i + 3], f[12 * i + 7], f[12 * i + 11]) for i in range(170)], f
cands = []
for o in range(0x300, 0x600, 8):
    v = struct.unpack_from("<Q", raw, o)[0]
    if not (0x100000000 < v < 0x800000000): continue
    try: s1, f1 = snap(v)
    except Exception: continue
    ok = sum(1 for i in range(170) if abs(sum(x * x for x in f1[12 * i:12 * i + 3]) - 1) < 0.02)
    if ok < 165: continue
    time.sleep(0.15); s2, _ = snap(v)
    mv = sum(1 for i in range(170) if max(abs(s1[i][j] - s2[i][j]) for j in range(3)) > 1e-4)
    cands.append((o, v, mv)); 
print("pid", pid, "valid-array slots (off, ptr, bones moving in 0.15 s):", [(hex(o), hex(v), m) for o, v, m in cands])
anim = [(o, v) for o, v, m in cands if m > 50]
print("animated:", [(hex(o), hex(v)) for o, v in anim], "- now RUN around (waiting for motion up to 4 min)")
t0 = time.time(); prev = wt(); tprev = time.time(); started = None; log = []
while time.time() - t0 < 240:
    time.sleep(0.02); cur = wt(); tc = time.time(); dt = tc - tprev
    sp = math.dist(cur, prev) / dt if dt > 0 else 0
    if started is None and sp > 2.0: started = tc; print("motion detected, sampling 15 s")
    if started is not None:
        row = {"t": tc, "w": cur, "sp": sp}
        for o, v in anim:
            r = rd(v, 0x30); f = struct.unpack("<12f", r); row[o] = (f[3], f[7], f[11])
        log.append(row)
        if tc - started > 15: break
    prev, tprev = cur, tc
print("samples", len(log))
mov = [r for r in log if r["sp"] > 2.0]; print("moving samples", len(mov))
if len(mov) > 20 and len(anim) >= 2:
    o1, o2 = anim[0][0], anim[1][0]
    lags = []
    for i in range(1, len(mov)):
        a, b = mov[i], mov[i - 1]
        vel = [(a["w"][j] - b["w"][j]) for j in range(3)]; n = math.sqrt(sum(x * x for x in vel))
        if n < 1e-4: continue
        u = [x / n for x in vel]; dif = [a[o1][j] - a[o2][j] for j in range(3)]
        lags.append((sum(dif[j] * u[j] for j in range(3)), sum(a["sp"] for _ in [0]) / 1, a["sp"]))
    import statistics as st
    ds = [l[0] for l in lags]; sps = [l[2] for l in lags]
    print("slot %#x - slot %#x along motion: mean %.4f m (median %.4f), mean speed %.2f m/s -> lag %.1f ms (positive: %#x is AHEAD / newer)" % (o1, o2, st.mean(ds), st.median(ds), st.mean(sps), 1000 * st.mean(ds) / st.mean(sps), o1))
    # offset of each array's bone0 from the model origin along motion
    for o, _ in anim:
        offs = []
        for i in range(1, len(mov)):
            a, b = mov[i], mov[i - 1]; vel = [(a["w"][j] - b["w"][j]) for j in range(3)]; n = math.sqrt(sum(x * x for x in vel))
            if n < 1e-4: continue
            offs.append(sum((a[o][j] - a["w"][j]) * vel[j] / n for j in range(3)))
        print("  slot %#x bone0-origin along motion: mean %.3f sd %.3f" % (o, st.mean(offs), st.pstdev(offs)))
