import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
cam = q(q(q(0x593e860) + 0x2830) + 0x60)
print("follow cam", hex(cam))
def rdf(o): return struct.unpack("<f", d.proc_read(pid, cam + o, 4))[0]
def wrf(o, v):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, cam + o, 4)); assert st == 0x80000000
    d.s.sendall(struct.pack("<f", v)); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
offs = [0x50, 0x5c, 0x160, 0x164, 0x168, 0x16c, 0x170, 0x174, 0x178, 0x17c, 0x180, 0x184, 0x188, 0x18c, 0x190, 0x194, 0x198, 0x19c, 0x1a0, 0x1a4, 0x1a8, 0x1ac, 0x1b0, 0x1b4, 0x1b8, 0x1bc, 0x1c0, 0x1c4, 0x1c8, 0x1cc, 0x1d0, 0x1d4, 0x1d8, 0x1dc, 0x1e0, 0x1e4, 0x1e8, 0x1ec, 0x1f0, 0x1f4, 0x1f8, 0x1fc, 0x200, 0x204, 0x208, 0x20c]
print("off    orig        wrote       after 0.4 s   verdict")
for o in offs:
    v = rdf(o)
    if v == 0 or v != v or abs(v) > 1e6: print(f"+{o:03x} {v:11.5g}  (skip)"); continue
    nv = v * 1.001; wrf(o, nv); time.sleep(0.4); a = rdf(o)
    verdict = "PERSISTS (input/param)" if abs(a - nv) < abs(v) * 1e-4 else ("reverted (computed per frame)" if abs(a - v) < abs(v) * 1e-4 else f"changed to {a:.5g}")
    print(f"+{o:03x} {v:11.5g} {nv:11.5g} {a:11.5g}   {verdict}")
    wrf(o, v)
