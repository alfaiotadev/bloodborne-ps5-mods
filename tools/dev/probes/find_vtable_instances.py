import struct, sys
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
VT = int(sys.argv[1], 16)
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
maps = d.proc_maps(pid)
big = max(maps, key=lambda m: m[2] - m[1]); arena = (big[1], big[2])
pat = struct.pack("<Q", VT); hits = []
for name, s0, e0, off, prot in maps:
    sz = e0 - s0
    if sz < (1 << 12) or sz > (1 << 30) or prot & 2 == 0 or (s0, e0) == arena: continue
    pos = s0
    while pos < e0:
        n = min(8 << 20, e0 - pos); b = d.proc_read(pid, pos, n)
        if b:
            i = b.find(pat)
            while i != -1:
                if (pos + i) % 8 == 0: hits.append((pos + i, s0))
                i = b.find(pat, i + 1)
        pos += n
print("vtable", hex(VT), "instances:", len(hits))
for a, s0 in hits[:12]:
    raw = d.proc_read(pid, a + 0x5b0, 0x30) or b''
    print(f"  obj {a:#x} [{s0:#x}]  +5b0..: {raw.hex(' ')}")
