import sys, struct, json
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
repo = q(0x5940340); blob = q(q(q(repo + 0x9c0) + 0x70) + 0x70)
h = d.proc_read(pid, blob, 0x40); n = struct.unpack_from("<H", h, 0xA)[0]
print("LOCK_CAM_PARAM_ST blob", hex(blob), "rows", n, "name", h[0xC:0x30].split(b"\0")[0])
tab = d.proc_read(pid, blob + 0x40, n * 24); ents = [struct.unpack_from("<IIQQ", tab, i * 24) for i in range(n)]
sizes = sorted(set(ents[i + 1][2] - ents[i][2] for i in range(n - 1))); rs = sizes[0]; print("row size", rs, "sizes", sizes[:4])
rows = []
for rid, pad, doff, noff in ents:
    raw = d.proc_read(pid, blob + doff, rs); f = struct.unpack_from("<%df" % (rs // 4), raw, 0)
    rows.append({"id": rid, "addr": hex(blob + doff), "f": list(f), "hex": raw.hex()})
json.dump({"blob": hex(blob), "rowsize": rs, "rows": rows}, open(workpath("cam_rows.json"), "w"))
for r in rows[:72]:
    f = r["f"]; print(f"id {r['id']:5d} {r['addr']}  f0={f[0]:<8.4g} f1={f[1]:<8.4g} f2={f[2]:<8.4g} f3={f[3]:<8.4g} f4={f[4]:<8.4g} f5(0x14)={f[5]:<8.4g} f6={f[6]:<8.4g} f7={f[7]:<8.4g}")
