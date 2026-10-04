import sys, struct, json
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
blob = q(q(q(q(0x59402d8) + 0x68) + 0x70) + 0x70)
tab = d.proc_read(pid, blob + 0x40, 64 * 24); rows = []
for i in range(64):
    rid, pad, doff, noff = struct.unpack_from("<IIQQ", tab, i * 24)
    raw = d.proc_read(pid, blob + doff, 20); a, b, c, dd = struct.unpack_from("<4f", raw, 0); e = struct.unpack_from("<I", raw, 16)[0]
    rows.append({"id": rid, "addr": hex(blob + doff), "A": a, "B": b, "C": c, "D": dd, "E": e, "hex": raw.hex()})
json.dump({"blob": hex(blob), "rows": rows}, open(workpath("lod_rows.json"), "w"))
for r in rows: print(f"{r['id']:2d} {r['addr']}  A={r['A']:<7g} B={r['B']:<5g} C={r['C']:<7g} D={r['D']:<5g} E={r['E']}")
