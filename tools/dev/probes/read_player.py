import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
wcm = q(0x593e878); pl = q(wcm + 0x60)
print("WorldChrMan", hex(wcm), "player ChrIns", hex(pl))
vt = q(pl); print("vtable", hex(vt), "slot 0x458 ->", hex(q(vt + 0x458)))
m48 = q(pl + 0x48); print("[pl+0x48] =", hex(m48))
if 0x100000000 < m48 < 0x400000000:
    m18 = q(m48 + 0x18); print("[[pl+0x48]+0x18] =", hex(m18)); print("mask @+0x170:", d.proc_read(pid, m18 + 0x170, 16).hex(" "))
print("alt mask @pl+0x118:", d.proc_read(pid, pl + 0x118, 16).hex(" "))
print("dirty byte pl+0x1e2:", d.proc_read(pid, pl + 0x1e2, 1).hex())
