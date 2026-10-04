import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
obj = q(0x59402d8); print("LodBankMan obj", hex(obj))
p1 = q(obj + 0x68); print("+0x68 ->", hex(p1))
p2 = q(p1 + 0x70); print("+0x70 ->", hex(p2))
blob = q(p2 + 0x70); print("+0x70 -> param blob", hex(blob))
hdr = d.proc_read(pid, blob, 0x80)
print("header:", hdr[:0x50].hex(" "))
nrows = struct.unpack_from("<H", hdr, 0xA)[0]; print("rows (u16 @+0xA):", nrows)
print("[blob-0x10] =", struct.unpack("<I", d.proc_read(pid, blob - 0x10, 4))[0])
print("--- row table @+0x40")
tab = d.proc_read(pid, blob + 0x40, 64 * 24)
ents = []
for i in range(64):
    rid, pad, doff, noff = struct.unpack_from("<IIQQ", tab, i * 24); ents.append((rid, doff, noff))
for i in range(6): print(i, ents[i][0], hex(ents[i][1]), hex(ents[i][2]))
sizes = sorted(set(ents[i + 1][1] - ents[i][1] for i in range(63)))
print("row data sizes (diffs):", sizes[:6], " last offset", hex(ents[-1][1]))
rowsz = sizes[0]
print("ids:", [e[0] for e in ents])
for i in (0, 1, 2, 10, 30):
    raw = d.proc_read(pid, blob + ents[i][1], rowsz)
    w = struct.unpack_from("<%dI" % (rowsz // 4), raw, 0); f = struct.unpack_from("<%df" % (rowsz // 4), raw, 0)
    print(f"row id {ents[i][0]} @{blob+ents[i][1]:#x} size {rowsz}:")
    print("   ints  :", " ".join(f"{x}" if x < 100000 else f"{x:#x}" for x in w))
    print("   floats:", " ".join(f"{x:.4g}" for x in f))
