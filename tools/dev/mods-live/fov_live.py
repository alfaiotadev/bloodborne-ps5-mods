"""fov_live.py SCALE  - set the Wide-FOV multiplier live (base vertical FOV 43 deg, clamped 38..48; SCALE 1.3 = release default)."""
import sys, struct, math
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
s = float(sys.argv[1]); data = struct.pack("<f", math.pi / 180.0 * s)
st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, 0x54A0500, 4)); assert st == 0x80000000
d.s.sendall(data); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
v = struct.unpack("<f", d.proc_read(pid, 0x54A0500, 4))[0]
print("pid %d FOV scale %.2f -> vertical %.1f deg, horizontal (16:9) %.1f deg" % (pid, v / (math.pi / 180), 43 * v / (math.pi / 180), math.degrees(2 * math.atan(math.tan(math.radians(43 * v / (math.pi / 180)) / 2) * 16 / 9))))
