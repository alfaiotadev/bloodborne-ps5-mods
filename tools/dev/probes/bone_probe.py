import sys, struct, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
ARR = int(sys.argv[1], 16); N = 108      # Usage: bone_probe.py <bone_array_addr_hex> (find it with find_qs_pose.py / find_bone_array.py)
def bones():
    r = d.proc_read(pid, ARR, N * 0x30); return [struct.unpack_from("<12f", r, i * 0x30) for i in range(N)]
b0 = bones(); time.sleep(0.6); b1 = bones(); time.sleep(0.6); b2 = bones()
top = sorted(range(N), key=lambda i: -b0[i][1])[:14]
print("top bones by model-space height (idx: t.xyz | q | motion over 1.2 s):")
for i in top:
    mv = sum(abs(b2[i][k] - b0[i][k]) for k in range(3))
    print("  %3d: t(%.3f %.3f %.3f)  q(%.3f %.3f %.3f %.3f)  move %.4f" % (i, *b0[i][0:3], *b0[i][4:8], mv))
print("bones that moved most:", sorted(range(N), key=lambda i: -sum(abs(b2[i][k] - b0[i][k]) for k in range(3)))[:10])
print("bones 0..5:", [("%d" % i, ["%.3f" % v for v in b0[i][0:3]]) for i in range(6)])
