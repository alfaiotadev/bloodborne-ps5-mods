# Usage: hc_state.py [cheat.json]   (default: <repo>/cheats/CUSA03173_01.09.json)
# Checks the live head-camera hooks, data block and pointer chain against the cheat entries.
import sys, struct, json
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
rd = lambda a, n: d.proc_read(pid, a, n); q = lambda a: struct.unpack("<Q", rd(a, 8))[0]
print("pid", pid)
print("hooks: mgr", rd(0x1836c54, 5).hex(), "| epi", rd(0x183f77b, 7).hex(), "| cast", rd(0x1c090e0, 6).hex())
blk = rd(0x54A0E00, 0x80)
print("data: BONEOFF=%d (bone %d) RUF=%s ARROFF=%#x LIMIT=%s MINN=%s | NOCOLL=%d MODE=%d FACE2=%d" % (
    struct.unpack_from("<i", blk, 4)[0], struct.unpack_from("<i", blk, 4)[0] // 0x30, [round(x, 3) for x in struct.unpack_from("<3f", blk, 8)],
    struct.unpack_from("<i", blk, 0x14)[0], struct.unpack_from("<f", blk, 0x18)[0], struct.unpack_from("<f", blk, 0x1c)[0], blk[0x70], blk[0x71], blk[0x73]))
exp = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "cheats", "CUSA03173_01.09.json")))
bad = 0
for m in exp["mods"]:
    if not m["name"].startswith("FPS head camera ("): continue
    for e in m["memory"]:
        a = int(e["offset"], 16); want = bytes.fromhex(e["on"]); got = rd(a, len(want))
        if got != want: bad += 1; print("  MISMATCH %#x len %d: got %s want %s" % (a, len(want), got.hex()[:24], want.hex()[:24]))
print("head camera entries mismatching:", bad)
wcm = q(0x593e878); pl = q(wcm + 0x60); mod = q(pl + 0x48); obj = q(mod + 0x18)
print("chain: wcm %#x pl %#x mod %#x(vt %#x, want 0x579cf10) obj %#x(vt %#x, want 0x57a0820)" % (wcm, pl, mod, q(mod), obj, q(obj)))
a = q(obj + 0x430); head = struct.unpack("<3f", rd(a + 68 * 0x30 + 12, 4) + rd(a + 68 * 0x30 + 28, 4) + rd(a + 68 * 0x30 + 44, 4))
print("array[+0x430] %#x head bone world pos %s" % (a, [round(x, 3) for x in head]))
cam = q(q(q(0x593e860) + 0x2830) + 0x60); print("follow camera %#x pos row %s" % (cam, [round(x, 3) for x in struct.unpack("<3f", rd(cam + 0x40, 12))]))
