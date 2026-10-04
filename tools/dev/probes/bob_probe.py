"""While walking straight: per-axis peak-to-peak of (array head - origin), the smoothed offset OFFS, and the final camera (found in the camera manager object) relative to the origin."""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); X = q(q(pl + 0x3b0) + 0x68)
blk = rd(0x54A0E00, 0xa0); hold = struct.unpack_from("<I", blk, 0x3c)[0]; arroff = struct.unpack_from("<i", blk, 0x14)[0]
holder = q(mod + hold); arr = q(holder + arroff); bone = arr + 68 * 0x30
mgr = q(q(0x593e860) + 0x2830)
print("pid", pid, "holder [mod+%#x]=%#x slot %#x array %#x" % (hold, holder, arroff, arr), flush=True)
# find the manager output position: a vec3 within 1.5 m of origin+(0,1.55,0) inside the manager object window(s)
o = struct.unpack("<3f", rd(X + 0x1e0, 12)); exp = (o[0], o[1] + 1.55, o[2]); found = None
for base in (mgr, q(mgr + 0x60), q(mgr + 0x68), q(mgr + 0x70), q(mgr + 0x78)):
    if not (0x200000000 <= base < 0x800000000): continue
    b = rd(base, 0x800)
    if not b: continue
    f = struct.unpack("<%df" % (len(b) // 4), b)
    for i in range(len(f) - 2):
        if math.dist(f[i:i + 3], exp) < 0.35 and i % 4 == 0: found = base + i * 4; break
    if found: break
print("final camera position found at %s" % (hex(found) if found else None), "- WALK straight ahead now (20 s)", flush=True)
time.sleep(1.0); rows = []; t0 = time.time()
while time.time() - t0 < 20:
    o = struct.unpack("<3f", rd(X + 0x1e0, 12)); b = rd(bone, 0x30); h = struct.unpack("<3f", b[12:16] + b[28:32] + b[44:48]); s = struct.unpack("<3f", rd(0x54A0E60, 12))
    c = struct.unpack("<3f", rd(found, 12)) if found else (0, 0, 0)
    rows.append((time.time() - t0, o, h, s, c))
def p2p(v):
    s = sorted(v); n = len(s); return s[int(n * 0.98)] - s[int(n * 0.02)]
mv = [r for r in rows if True]
print("samples", len(rows))
for name, ex in (("array head - origin", lambda r: tuple(r[2][i] - r[1][i] for i in range(3))), ("OFFS (smoothed offset)", lambda r: r[3]), ("final camera - origin", lambda r: tuple(r[4][i] - r[1][i] for i in range(3)))):
    ax = list(zip(*[ex(r) for r in rows])); print("  %-24s peak-to-peak  x %.3f  y %.3f  z %.3f  m (2-98 %%)" % (name, p2p(ax[0]), p2p(ax[1]), p2p(ax[2])))
dist = math.dist(rows[0][1], rows[-1][1]); print("walked %.1f m in %.0f s" % (dist, rows[-1][0]))
