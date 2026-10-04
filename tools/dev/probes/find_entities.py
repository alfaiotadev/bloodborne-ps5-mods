import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
u = lambda a: struct.unpack("<I", d.proc_read(pid, a, 4))[0]
M = q(0x593b168); print("draw entity manager M", hex(M), "groups", u(M + 0x10), "blocks(+0x20)", u(M + 0x20))
pl = q(q(0x593e878) + 0x60); m48 = q(pl + 0x48)
models = {"+0x10": q(m48 + 0x10), "+0x18": q(m48 + 0x18), "+0x20": q(m48 + 0x20)}
nb = u(M + 0x20); blk_base = q(M + 0x28)
print("block array", hex(blk_base))
for k, mo in models.items():
    idx = u(mo + 0x78); print(f"\nmodel {k} {mo:#x}: vtable {q(mo):#x}, +0x78={idx:#x}")
    for b in range(min(nb, 6)):
        cnt = u(blk_base + b * 0x1f8 + 0xc8); arr = q(blk_base + b * 0x1f8 + 0xd0)
        if idx < cnt:
            ent = arr + idx * 0x2e0; fl = u(ent + 0x1fc)
            print(f"  block {b}: count {cnt}, entity {ent:#x} vtable {q(ent):#x} flags@1fc={fl:#x} draw={(fl>>14)&1}")
