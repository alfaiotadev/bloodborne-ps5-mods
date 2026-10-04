import sys, struct, time, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
ok = lambda v: 0x200000000 <= v < 0x800000000 and v % 8 == 0
pl = q(q(0x593e878) + 0x60); mod = q(pl + 0x48); w = q(pl + 0x58)
o = struct.unpack("<3f", rd(w + 0x350, 12)); print("pid", pid, "pl %#x mod %#x w %#x origin %s" % (pl, mod, w, [round(x, 2) for x in o]), flush=True)
queue = [(pl, 0, "pl"), (mod, 0, "mod"), (w, 0, "w")]; parent = {pl: None, mod: None, w: None}; n = 0; t0 = time.time(); hits = []
def path(a):
    out = []
    while parent.get(a):
        pa, off = parent[a]; out.append("%#x" % off); a = pa
    return "->".join(reversed(out)) + " (root %#x)" % a
while queue and n < 6000 and time.time() - t0 < 90:
    a, dep, nm = queue.pop(0); b = rd(a, 0x800); n += 1
    if not b: continue
    if a % 16 == 0 and len(b) >= 0x30 * 70:
        f = struct.unpack("<%df" % (len(b) // 4), b[:len(b) // 4 * 4])
        # does this window contain a 3x4 orthonormal matrix whose translation is within 3 m of the origin? then it is (part of) a world pose array
        for k in range(0, len(f) - 11, 12):
            r0, r1, t = f[k:k + 3], f[k + 4:k + 7], (f[k + 3], f[k + 7], f[k + 11])
            if abs(sum(x * x for x in r0) - 1) < 0.02 and abs(sum(x * x for x in r1) - 1) < 0.02 and math.dist(t, o) < 3.0 and t != (0.0, 0.0, 0.0):
                hits.append((a, k * 4, t)); break
    if dep < 5:
        for off in range(0, len(b) - 7, 8):
            p = struct.unpack_from("<Q", b, off)[0]
            if ok(p) and p not in parent: parent[p] = (a, off); queue.append((p, dep + 1, nm))
print("windows %d in %.0f s, hits %d" % (n, time.time() - t0, len(hits)), flush=True)
for a, off, t in hits[:14]: print("  array-like @ %#x (+%#x) t=%s path %s" % (a, off, [round(x, 2) for x in t], path(a)))
