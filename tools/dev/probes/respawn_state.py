import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
b = rd(0x54A0E00, 0x80)
print("pid", pid, "MODE %d FACE2 %d NOCOLL %d | ARROFF %#x COOL %d | OFFS %s" % (b[0x71], b[0x73], b[0x70], struct.unpack_from("<i", b, 0x14)[0], struct.unpack_from("<I", b, 0x2c)[0], [round(x, 2) for x in struct.unpack_from("<3f", b, 0x60)]))
print("hooks:", rd(0x1836c54, 5).hex(), rd(0x183f77b, 7).hex(), rd(0x1c090e0, 6).hex())
wcm = q(0x593e878); pl = q(wcm + 0x60)
print("wcm %#x pl %#x vt %#x" % (wcm, pl, q(pl)))
mod = q(pl + 0x48); w = q(pl + 0x58); print("[pl+0x48] %#x vt %#x (want 0x579cf10) | [pl+0x58] %#x vt %#x (want 0x5770610)" % (mod, q(mod), w, q(w)))
obj = q(mod + 0x18); print("[mod+0x18] %#x vt %#x (want 0x57a0820)" % (obj, q(obj)))
o = struct.unpack("<3f", rd(w + 0x350, 12)); print("origin", [round(x, 2) for x in o])
def head(p): bb = rd(p + 68 * 0x30, 0x30); return struct.unpack("<3f", bb[12:16] + bb[28:32] + bb[44:48])
found = []
for off in range(0x300, 0x600, 8):
    p = q(obj + off)
    if not (0x200000000 <= p < 0x800000000) or p % 16: continue
    try: h = head(p)
    except Exception: continue
    dy = h[1] - o[1]; dxz2 = (h[0] - o[0]) ** 2 + (h[2] - o[2]) ** 2
    ok = -0.5 < dy < 2.4 and dxz2 < 2.25
    if ok or (abs(dy) < 5 and dxz2 < 25): found.append((hex(off), "OK" if ok else "near", [round(c, 2) for c in (h[0]-o[0], dy, h[2]-o[2])]))
print("candidate slots:", found)
