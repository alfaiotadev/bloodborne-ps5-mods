"""Find the pointer path from the player ChrIns to the 8-element body-position array (stride 0xa0) and check it is stable across frames. Read-only.  Usage: head_chain.py <element0_addr_hex>"""
import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
heap = lambda v: 0x100000000 < v < 0x800000000 and v % 8 == 0
pl = q(q(0x593e878) + 0x60)
TARGET = int(sys.argv[1], 16)          # element 0 address (heap address of this game session: find it with find_bone_array.py / find_arrays_bfs.py)
seen = {pl: None}; queue = [(pl, 0)]; found = None; n = 0
while queue and not found:
    a, depth = queue.pop(0); r = d.proc_read(pid, a, 0x1000); n += 1
    if not r: continue
    for o in range(0, len(r) - 7, 8):
        p = struct.unpack_from("<Q", r, o)[0]
        if not heap(p): continue
        if p <= TARGET < p + 0x1000 and (a, o) not in [(x[0], x[1]) for x in [seen.get(p) or (0, 0)]]:
            path = [(a, o)]; cur = a
            while seen.get(cur): par, off = seen[cur]; path.append((par, off)); cur = par
            found = (p, path[::-1]); break
        if p not in seen and depth < 4: seen[p] = (a, o); queue.append((p, depth + 1))
print("windows read", n)
if found:
    base, path = found; print("target window base %#x, element0 at base+%#x" % (base, TARGET - base))
    print("path from player ChrIns %#x:" % pl, " -> ".join("[+%#x]" % off for _, off in path))
    # verify by re-walking the path and reading element 6 over several frames
    for i in range(3):
        cur = pl
        for _, off in path: cur = q(cur + off)
        print("  walk -> %#x (same window: %s)  element6 y = %.4f" % (cur, cur == base, struct.unpack("<f", d.proc_read(pid, cur + (TARGET - base) + 6 * 0xa0 + 4, 4))[0])); time.sleep(0.3)
else: print("no path found within depth 4")
