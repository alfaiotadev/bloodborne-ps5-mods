import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl = q(q(0x593e878) + 0x60); ent = q(q(pl + 0x48) + 0x18)
print("player", hex(pl), "draw entity", hex(ent))
fl = struct.unpack("<I", d.proc_read(pid, ent + 0x1fc, 4))[0]
print("entity+0x1fc flags = %#x  (bit14 draw=%d, bit15=%d, 0x2000 dirty=%d)" % (fl, (fl >> 14) & 1, (fl >> 15) & 1, (fl >> 13) & 1))
obj = q(ent + 0x10); print("entity+0x10 ->", hex(obj))
if 0x100000000 < obj < 0x400000000:
    raw = d.proc_read(pid, obj, 0x20); print("  obj+0x00..0x1f:", raw.hex(" "))
print("vtable of entity:", hex(q(ent)))
for off in (0x0, 0x8, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70):
    v = q(ent + off); print("  ent+%#04x = %#x" % (off, v))
