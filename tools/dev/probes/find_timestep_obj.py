# Find the fixed timestep object (frame timing; dt float at +0x18, 0x3c888889 = 1/60 s with the 60fps patch). Needs ps5dbg.py (tools/dev/core).
import struct, sys
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
maps = d.proc_maps(pid)
big = max(maps, key=lambda m: m[2] - m[1]); arena = (big[1], big[2])
pat = struct.pack("<I", 0x3c888889)
cands = []
for name, s0, e0, off, prot in maps:
    sz = e0 - s0
    if sz < (1 << 12) or sz > (1 << 30) or prot & 2 == 0 or (s0, e0) == arena:
        continue
    pos = s0
    while pos < e0:
        n = min(8 << 20, e0 - pos); b = d.proc_read(pid, pos, n)
        if b:
            i = b.find(pat)
            while i != -1:
                a = pos + i
                if a % 4 == 0 and i >= 8 and i + 0x258 <= len(b):
                    f10 = struct.unpack_from("<I", b, i - 8)[0]; f14 = b[i - 4]; f26c = struct.unpack_from("<I", b, i + 0x254)[0]
                    if f10 == 1 and f14 == 0 and f26c == 1:
                        cands.append((a, name, s0, e0))
                i = b.find(pat, i + 1)
        pos += n
print("pid", pid, "candidates:", len(cands))
for a, name, s0, e0 in cands:
    obj = a - 0x18
    raw = d.proc_read(pid, obj, 0x2d0) or b''
    g = lambda o: struct.unpack_from("<I", raw, o)[0]
    print(f"obj {obj:#x} (dt field {a:#x}) in {name} [{s0:#x}-{e0:#x}]  +8={g(8):#x} +c={g(0xc):#x} +10={g(0x10)} +18={g(0x18):#x} +268={g(0x268):#x} +26c={g(0x26c):#x} +275/276={raw[0x275]}/{raw[0x276]}")
