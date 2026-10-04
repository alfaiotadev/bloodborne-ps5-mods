"""apply_live.py <cheat.json> <mod-name-prefix>  - write one mod's entries into the running game (MODE/FACE2 flags off first, hooks after caves, flags on last).
The head camera cave's cached state (HOLD, ARROFF, COOL) is deliberately not part of any cheat entry, so re-applying never resets it."""
import sys, json, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
def wr(a, data):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, len(data))); assert st == 0x80000000, hex(st)
    d.s.sendall(data); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
    assert d.proc_read(pid, a, len(data)) == data, hex(a)
cfg = json.load(open(sys.argv[1]))
for m in cfg["mods"]:
    if not m["name"].startswith(sys.argv[2]): continue
    print("apply", m["name"], len(m["memory"]), "entries")
    flags = [e for e in m["memory"] if e["offset"] in ("054A0E71", "054A0E73")]
    for e in flags: wr(int(e["offset"], 16), b"\x00")
    for e in m["memory"]:
        if e in flags: continue
        a = int(e["offset"], 16); data = bytearray.fromhex(e["on"])
        wr(a, bytes(data))
    for e in flags: wr(int(e["offset"], 16), bytes.fromhex(e["on"]))
print("done")
