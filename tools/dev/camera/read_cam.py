import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
w = q(0x593e860); mgr = q(w + 0x2830)
print("world", hex(w), "ChrCam manager", hex(mgr))
for off, name in ((0x60, "follow cam (ChrExFollowCam/ChrFollowCam)"), (0x68, "ChrAimCam"), (0x78, "BallistaAimCam")):
    sub = q(mgr + off)
    print(f"\n== sub-object +{off:#x} {name}: {sub:#x}")
    if not (0x100000000 < sub < 0x400000000): print("   (not a heap pointer)"); continue
    raw = d.proc_read(pid, sub, 0x210)
    for o in range(0, 0x210, 16):
        w4 = struct.unpack_from("<4I", raw, o); f4 = struct.unpack_from("<4f", raw, o)
        print(f"   +{o:03x}: " + " ".join(f"{x:08x}" for x in w4) + "   " + " ".join(f"{x:10.4g}" for x in f4))
