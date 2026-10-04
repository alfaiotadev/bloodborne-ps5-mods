"""Samples the follow camera object for 45 s; finds (a) fields that toggle like a lock-on flag, (b) float triples lying on the camera's view ray (the lock-on target / look-at point)."""
import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
cam = q(q(q(0x593e860) + 0x2830) + 0x60); SZ = 0x1000
print("pid", pid, "follow camera %#x vtable %#x - GO: lock on 10 s / release 10 s / lock on 10 s / release" % (cam, q(cam)), flush=True)
S = []; t0 = time.time()
while time.time() - t0 < 45:
    b = rd(cam, SZ)
    if b: S.append((time.time() - t0, b))
print("samples", len(S), "(%.0f Hz)" % (len(S) / 45), flush=True)
n = SZ // 4; F = [struct.unpack("<%df" % n, b) for _, b in S]; I = [struct.unpack("<%dI" % n, b) for _, b in S]
def unit(v):
    l = math.sqrt(sum(x * x for x in v)); return None if l < 1e-6 else (v[0] / l, v[1] / l, v[2] / l, l)
# camera rows: right +0x10, up +0x20, forward +0x30, position +0x40
def rows(f): return f[0x10 // 4:0x10 // 4 + 3], f[0x20 // 4:0x20 // 4 + 3], f[0x30 // 4:0x30 // 4 + 3], f[0x40 // 4:0x40 // 4 + 3]
# (b) triples on the view ray
cand = {}
for k, f in enumerate(F):
    R, U, Fw, P = rows(f)
    uf = unit(Fw)
    if uf is None: continue
    for o in range(0x50 // 4, n - 3):
        x = f[o:o + 3]
        if any(abs(c) > 1e5 or c != c for c in x): continue
        v = (x[0] - P[0], x[1] - P[1], x[2] - P[2]); uv = unit(v)
        if uv is None or not (1.0 < uv[3] < 40): continue
        cosv = uv[0] * uf[0] + uv[1] * uf[1] + uv[2] * uf[2]
        if cosv > 0.999: cand.setdefault(o * 4, []).append(k)
print("\n(b) triples on the view ray (cos>0.999, 1..40 m ahead): offset: share of samples / first/last sample time")
for o, ks in sorted(cand.items(), key=lambda kv: -len(kv[1]))[:12]:
    f = F[ks[len(ks) // 2]]; R, U, Fw, P = rows(f); x = f[o // 4:o // 4 + 3]
    print("  +%#05x  %3.0f %%  t=%4.1f..%4.1f  value %s  dist %.1f m" % (o, 100 * len(ks) / len(F), S[ks[0]][0], S[ks[-1]][0], [round(c, 2) for c in x], math.dist(x, P)))
# (a) toggling dwords
print("\n(a) dwords that behave like a flag (<=8 transitions, value set small): offset: transition times")
for o in range(n):
    col = [I[k][o] for k in range(len(I))]
    vals = set(col)
    if len(vals) < 2 or len(vals) > 3: continue
    tr = [S[k][0] for k in range(1, len(col)) if col[k] != col[k - 1]]
    if 2 <= len(tr) <= 8 and (max(vals) < 0x100 or 0 in vals): print("  +%#05x  values %s  transitions at %s" % (o * 4, sorted(hex(v) for v in vals), [round(t, 1) for t in tr]))
