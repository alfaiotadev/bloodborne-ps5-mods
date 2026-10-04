import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
repo = q(0x5940340); print("SoloParamRepository", hex(repo))
raw = d.proc_read(pid, repo, 0xA00)
found = {}
for o in range(0, 0xA00 - 8, 8):
    p = struct.unpack_from("<Q", raw, o)[0]
    if not (0x100000000 < p < 0x400000000): continue
    try:
        p1 = q(p + 0x70)
        if not (0x100000000 < p1 < 0x400000000): continue
        blob = q(p1 + 0x70)
        if not (0x100000000 < blob < 0x400000000): continue
        h = d.proc_read(pid, blob, 0x30)
        name = h[0xC:0x30].split(b"\0")[0]
        if len(name) >= 3 and all(32 <= c < 127 for c in name):
            rows = struct.unpack_from("<H", h, 0xA)[0]
            found[o] = (name.decode(), rows, hex(blob))
    except Exception: pass
for o, (n, r, b) in sorted(found.items()): print(f"repo+{o:#05x}  {n:36s} rows={r:5d} blob={b}")
