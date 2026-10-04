#!/usr/bin/env python3
"""Read-only snapshot of Bloodborne's graphics state via ps5debug.
Usage: python3 gfx_inspect.py > $PS5_WORKDIR/gfx_<res>.txt

Dumps, for the running eboot.bin (CUSA03173 v1.09, absolute addresses):
  * resolution globals + UI scale/copies
  * SprjGraphics object [0x59406c8] (0x6a0 B) and its render-target table
    ([obj+0x90], 0xb0-byte entries: +0x68 color RT, +0x70 depth RT, +0x80/+0x84 W/H)
  * each RT object (+0x40 = surface descriptor) as raw dwords
  * process memory map, largest regions first (to spot resolution-sized pools)
"""
import struct, sys
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg

d = Dbg()
pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
print("pid", pid)


def rd(a, n):
    b = d.proc_read(pid, a, n)
    return b


def q(a):
    b = rd(a, 8)
    return struct.unpack("<Q", b)[0] if b else None


def hexdw(a, n, label=""):
    b = rd(a, n)
    print(f"-- {label} @{a:x} len {n:#x}" + ("  (UNREADABLE)" if b is None else ""))
    if b is None:
        return
    for o in range(0, n, 16):
        dw = struct.unpack_from("<4I", b, o)
        print(f"{a+o:x}: " + " ".join(f"{x:08x}" for x in dw) + "   " + " ".join(f"{x:>10}" for x in dw))


def u32(a):
    b = rd(a, 4)
    return struct.unpack("<I", b)[0] if b else None


print("RES   W/H", u32(0x55289f8), u32(0x55289fc))
print("UI    W/H", u32(0x59404d8), u32(0x59404dc))
sx = rd(0x59404d0, 8)
print("S     X/Y", struct.unpack("<ff", sx) if sx else None)

g = q(0x59406c8)
print(f"SprjGraphics ptr {g:#x}" if g else "SprjGraphics ptr NULL")
if g:
    hexdw(g, 0x6a0, "SprjGraphics object")
    tbl = q(g + 0x90)
    print(f"RT table ptr {tbl:#x}" if tbl else "RT table NULL")
    if tbl:
        for i in range(8):
            e = tbl + i * 0xb0
            hexdw(e, 0xb0, f"RT-table entry {i}")
            for off, nm in ((0x68, "color"), (0x70, "depth")):
                rt = q(e + off)
                if rt and rt > 0x10000:
                    hexdw(rt, 0x80, f"entry {i} {nm} RT object")
                    sd = q(rt + 0x40)
                    if sd and sd > 0x10000:
                        hexdw(sd, 0x60, f"entry {i} {nm} surface descriptor")

for name, a in (("SprjWindow singleton", 0x5940500), ("graphics @593d710", 0x593d710),
                ("videoout state 58b9df8", 0x58b9df8)):
    hexdw(a, 0x40, name)

maps = d.proc_maps(pid)
print(f"-- memory map: {len(maps)} regions, total {sum(e-s for _,s,e,_,_ in maps)/2**20:.0f} MB")
for name, s, e, off, prot in sorted(maps, key=lambda m: m[1] - m[2])[:40]:
    print(f"{s:x}-{e:x} {(e-s)/2**20:9.2f} MB prot={prot:#x} off={off:#x} {name}")
