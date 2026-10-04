import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
u = lambda a: struct.unpack("<I", d.proc_read(pid, a, 4))[0]
M = q(0x593b168); nb = u(M + 0x20); blk = q(M + 0x28)
print("blocks", nb)
for b in range(nb):
    cnt = u(blk + b * 0x1f8 + 0xc8); arr = q(blk + b * 0x1f8 + 0xd0)
    print(f"block {b}: count {cnt} base {arr:#x}")
ent = q(blk + 5 * 0x1f8 + 0xd0)          # first entity of block 5
for i in (0, 1, 2):
    e = ent + i * 0x2e0; raw = d.proc_read(pid, e, 0x2e0)
    print(f"\n== entity block5[{i}] {e:#x}  flags@1fc={struct.unpack_from('<I',raw,0x1fc)[0]:#x}")
    for o in range(0, 0x2e0, 16):
        w = struct.unpack_from("<4I", raw, o); f = struct.unpack_from("<4f", raw, o)
        if any(w): print(f"  +{o:03x}: " + " ".join(f"{x:08x}" for x in w) + "  " + " ".join(f"{x:9.3g}" for x in f))
