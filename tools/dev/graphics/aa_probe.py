"""Read the game-side AA pass (vtable 0x56e7980) fields in each scene: which instance is active, its mode and params. Read-only apart from the scene warps. Usage: aa_probe.py [scene ...]"""
import sys, struct, json, os
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
import scenelib
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
db = json.load(open(os.environ.get("SCENES", workpath("scenes.json")))); S = scenelib.Scenes(d, pid, db)
VT = 0x56e7980
def instances():
    needle = struct.pack("<Q", VT); hits = []
    for name, s, e, off, prot in d.proc_maps(pid):
        if e - s < 4096 or e - s > (1 << 30) or prot & 2 == 0: continue
        pos = s
        while pos < e:
            n = min(8 << 20, e - pos); b = d.proc_read(pid, pos, n); i = b.find(needle) if b else -1
            while i != -1:
                if (pos + i) % 8 == 0: hits.append(pos + i)
                i = b.find(needle, i + 1)
            pos += n
    return hits
inst = instances(); print("instances:", [hex(x) for x in inst])
def show(tag):
    for h in inst:
        r = d.proc_read(pid, h, 0x38)
        print("  %-26s %#x ignore=%d enable=%d mode=%d fxaa=%s dlaa(thr,lam,eps)=%s" % (tag, h, r[8], r[9], struct.unpack("<i", r[0xc:0x10])[0], ["%.4g" % x for x in struct.unpack("<4f", r[0x10:0x20])], ["%.4g" % x for x in struct.unpack("<3f", r[0x28:0x34])]))
names = sys.argv[1:] or ["bridge_end_cobblestone", "under_bridge_brick_wall", "sickroom_fences_aa", "ladder_top_horizon"]
show("current")
for n in names:
    print("== %s (err %.3f m)" % (n, S.go(n, 3.0))); show(n)
S.remove()
