"""Follow the game's own PlayerWarp read chain: X=[[[[pl+0x58]+8]+0x3b0]+0x68]; X+0x1d0/0x1e0 are what 0x1948740 saves as igPos/deg (read-only)."""
import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl = q(q(0x593e878) + 0x60)
c1 = q(pl + 0x58); c2 = q(c1 + 8); c3 = q(c2 + 0x3b0); X = q(c3 + 0x68)
print("pl %#x  [pl+0x58]=%#x  [+8]=%#x  [+0x3b0]=%#x  [+0x68]=X=%#x" % (pl, c1, c2, c3, X))
raw = d.proc_read(pid, X + 0x180, 0x80)
for o in range(0, 0x80, 16):
    print("  X+%03x: " % (0x180 + o) + " ".join("%08x" % v for v in struct.unpack_from("<4I", raw, o)) + "   " + " ".join("%10.4f" % v for v in struct.unpack_from("<4f", raw, o)))
cands = {"X+0x1d0": X + 0x1d0, "[pl+0x400]+0x30": q(pl + 0x400) + 0x30, "[pl+0x58]+0x350": c1 + 0x350, "[pl+0x60]+0x1b0": q(pl + 0x60) + 0x1b0}
for i in range(4):
    print(" ".join("%s=(%.3f,%.3f,%.3f)" % ((k,) + struct.unpack("<3f", d.proc_read(pid, a, 12))) for k, a in cands.items()))
    time.sleep(0.5)
