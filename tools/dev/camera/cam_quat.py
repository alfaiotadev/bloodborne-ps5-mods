"""Search snapshots A/B for a camera orientation stored as a quaternion (unit 4-float group that rotates +-Z/+-X onto the camera forward/right in both A and B)."""
import sys, pickle, struct, math, itertools
A, B = pickle.load(open(sys.argv[1], "rb")), pickle.load(open(sys.argv[2], "rb"))
def fwd(S):
    f = struct.unpack("<12f", S["wins"][S["cam"]][0x10:0x40]); return f[0:3], f[3 + 1:3 + 4][:0] or f[4:7], f[8:11]
def qrot(q, v, inv=False):
    x, y, z, w = q
    if inv: x, y, z = -x, -y, -z
    # v' = v + 2w(u x v) + 2 u x (u x v)
    ux, uy, uz = x, y, z
    cx, cy, cz = uy * v[2] - uz * v[1], uz * v[0] - ux * v[2], ux * v[1] - uy * v[0]
    dx, dy, dz = uy * cz - uz * cy, uz * cx - ux * cz, ux * cy - uy * cx
    return (v[0] + 2 * (w * cx + dx), v[1] + 2 * (w * cy + dy), v[2] + 2 * (w * cz + dz))
def close(a, b, t=0.03): return all(abs(x - y) < t for x, y in zip(a, b))
right = lambda S: struct.unpack("<3f", S["wins"][S["cam"]][0x10:0x1c])
up = lambda S: struct.unpack("<3f", S["wins"][S["cam"]][0x20:0x2c])
fw = lambda S: struct.unpack("<3f", S["wins"][S["cam"]][0x30:0x3c])
tA, tB = (right(A), up(A), fw(A)), (right(B), up(B), fw(B))
hits = {}
for addr, ra in A["wins"].items():
    rb = B["wins"].get(addr)
    if not rb: continue
    m = min(len(ra), len(rb)) // 4 - 3
    fa = struct.unpack("<%df" % (m + 3), ra[:(m + 3) * 4]); fb = struct.unpack("<%df" % (m + 3), rb[:(m + 3) * 4])
    for i in range(m):
        ga, gb = fa[i:i + 4], fb[i:i + 4]
        if ga == gb: continue
        na = sum(x * x for x in ga); nb = sum(x * x for x in gb)
        if abs(na - 1) > 4e-3 or abs(nb - 1) > 4e-3: continue
        if sum(1 for x in ga if abs(x) > 1e-3) < 3: continue
        for perm in itertools.permutations(range(4)):
            qa = tuple(ga[j] for j in perm); qb = tuple(gb[j] for j in perm)
            for inv in (False, True):
                for axis, (ta, tb) in (("Z->fwd", ((0, 0, 1), (0, 0, 1))), ("-Z->fwd", ((0, 0, -1), (0, 0, -1)))):
                    ra_ = qrot(qa, ta, inv); rb_ = qrot(qb, tb, inv)
                    if close(ra_, tA[2]) and close(rb_, tB[2]):
                        hits.setdefault((addr + i * 4), []).append((perm, inv, axis))
for a, v in sorted(hits.items())[:40]:
    print("%#x  floats A %s" % (a, ["%.3f" % x for x in struct.unpack_from("<4f", [r for ad, r in A["wins"].items() if ad <= a < ad + len(r)][0], a - [ad for ad, r in A["wins"].items() if ad <= a < ad + len(r)][0])]), v[:2])
print(len(hits), "candidate quaternion groups")
