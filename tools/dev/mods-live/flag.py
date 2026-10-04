"""flag.py NAME=VAL ...  - set head camera data flags live (MODE, FACE2, NOCOLL) and print the state."""
import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
A = {"NOCOLL": 0x54A0E70, "MODE": 0x54A0E71, "FACE2": 0x54A0E73}
def wr(a, data):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, len(data))); assert st == 0x80000000, hex(st)
    d.s.sendall(data); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
for kv in sys.argv[1:]:
    k, v = kv.split("="); wr(A[k], bytes([int(v)]))
print({k: d.proc_read(pid, a, 1)[0] for k, a in A.items()}, "pid", pid)
