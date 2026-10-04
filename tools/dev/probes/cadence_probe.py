"""For every plausible pose slot, sample the head bone at ~100+ Hz for 5 s and report how often its value changes (60 Hz copy: ~16 ms between changes; 30 Hz copy: ~33 ms)."""
import sys, struct, time, statistics as st
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); obj = q(mod + 0x18); w = q(pl + 0x58)
arroff = struct.unpack("<i", rd(0x54A0E14, 4))[0]
print("pid", pid, "cave ARROFF %#x" % arroff, "obj %#x" % obj, flush=True)
def head(a):
    b = rd(a + 68 * 0x30, 0x30); return struct.unpack("<3f", b[12:16] + b[28:32] + b[44:48])
o = struct.unpack("<3f", rd(w + 0x350, 12)); slots = []
for off in range(0x300, 0x600, 8):
    p = q(obj + off)
    if not (0x200000000 <= p < 0x800000000) or p % 16: continue
    try: h = head(p)
    except Exception: continue
    dy = h[1] - o[1]; dxz2 = (h[0] - o[0]) ** 2 + (h[2] - o[2]) ** 2
    if -0.5 < dy < 2.4 and dxz2 < 2.25: slots.append((off, p))
print("plausible slots:", [(hex(a), hex(b)) for a, b in slots], "- RUN with the left stick now", flush=True)
time.sleep(2)
for off, p in slots:
    t0 = time.time(); prev = None; tprev = None; ivs = []; n = 0; same = 0
    while time.time() - t0 < 5:
        h = head(p); t = time.time(); n += 1
        if prev is not None and h == prev: same += 1
        if prev is not None and h != prev:
            if tprev is not None: ivs.append((t - tprev) * 1000)
            tprev = t
        elif prev is None: tprev = t
        prev = h
    rate = n / 5
    med = st.median(ivs) if ivs else float("nan")
    print("slot %#x%s: %d samples (%.0f Hz), identical-consecutive %.0f %%, change interval median %.1f ms (mean %.1f), changes %d" % (off, " <== cave" if off == arroff else "", n, rate, 100 * same / max(n - 1, 1), med, st.mean(ivs) if ivs else float("nan"), len(ivs)), flush=True)
