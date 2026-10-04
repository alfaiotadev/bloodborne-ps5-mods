import sys, struct, collections
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
u = lambda a: struct.unpack("<I", d.proc_read(pid, a, 4))[0]
M = q(0x593b168); blk = q(M + 0x28); cnt = u(blk + 5 * 0x1f8 + 0xc8); base = q(blk + 5 * 0x1f8 + 0xd0)
print("entities", cnt, "base", hex(base))
raw = d.proc_read(pid, base, cnt * 0x2e0)
names = collections.Counter(); hits = []
for i in range(cnt):
    e = raw[i * 0x2e0:(i + 1) * 0x2e0]
    nm = e[0x198:0x1c0]
    s = nm.decode("utf-16le", "ignore").split("\0")[0]
    fl = struct.unpack_from("<I", e, 0x1fc)[0]
    names[s[:14]] += 1
    if s.lower().startswith("c0") or "c0000" in s.lower() or s.lower().startswith("c"):
        pos = struct.unpack_from("<3f", e, 0x24c) if False else (struct.unpack_from("<f", e, 0x24c)[0], struct.unpack_from("<f", e, 0x25c)[0], struct.unpack_from("<f", e, 0x26c)[0])
        hits.append((i, s, fl, pos))
print("distinct name prefixes (top 25):", names.most_common(25))
print("\nentities whose name starts with 'c':", len(hits))
for i, s, fl, pos in hits[:60]: print(f"  idx {i:4d} {base+i*0x2e0:#x} name={s!r:36s} flags={fl:#x} draw={(fl>>14)&1} pos=({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f})")
