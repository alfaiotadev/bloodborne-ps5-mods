#!/usr/bin/env python3
"""Live read/write of game memory via ps5debug (needs ps5dbg.py from tools/dev/core).
Usage: python3 code_patch.py <addr_hex> <hex_bytes>   write, verifies readback
       python3 code_patch.py <addr_hex> ?<len>         read only"""
import struct, sys
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
addr = int(sys.argv[1], 16); arg = sys.argv[2]
d = Dbg()
pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
if arg.startswith("?"):
    print(d.proc_read(pid, addr, int(arg[1:])).hex(" ")); sys.exit()
data = bytes.fromhex(arg)
print("before:", d.proc_read(pid, addr, len(data)).hex(" "))
st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, addr, len(data))); assert st == 0x80000000, hex(st)
d.s.sendall(data); st2 = struct.unpack("<I", d._recvn(4))[0]; assert st2 == 0x80000000, hex(st2)
print("after :", d.proc_read(pid, addr, len(data)).hex(" "))
