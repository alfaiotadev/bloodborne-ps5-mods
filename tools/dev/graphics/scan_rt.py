#!/usr/bin/env python3
"""Find engine texture descriptors of a given size in the running game (ps5debug) and
show which parts of their GPU surface memory contain data.
Usage: python3 scan_rt.py <W> <H>
Descriptor layout (observed): +0x20 qword surface address, +0x2c size, +0x38 format/tile, +0x44 u16 W, u16 H.
The map prints 64 chunks of the surface in memory order ('#' = data, '.' = zeros) so a render that
only covers a sub-rectangle (e.g. 1080p viewport inside a 4K target) shows up as a partially empty map."""
import struct, sys
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg

W, H = int(sys.argv[1]), int(sys.argv[2])
pat = struct.pack("<HH", W, H)
d = Dbg()
pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
maps = d.proc_maps(pid)
big = max(maps, key=lambda m: m[2] - m[1])               # the GPU arena
arena = (big[1], big[2])
print(f"pid {pid}; GPU arena {arena[0]:#x}-{arena[1]:#x} ({(arena[2-1]-arena[0])/2**20:.0f} MB)")
found = []
for name, s, e, off, prot in maps:
    sz = e - s
    if prot != 3 or sz < (1 << 20) or sz > (1 << 30) or (s, e) == arena:
        continue
    pos = s
    while pos < e:
        n = min(8 << 20, e - pos)
        b = d.proc_read(pid, pos, n)
        if b:
            i = b.find(pat)
            while i != -1:
                a = pos + i
                if (a - 0x44) % 8 == 0:
                    found.append(a - 0x44)
                i = b.find(pat, i + 1)
        pos += n
print(f"{len(found)} candidate descriptors with {W}x{H} at +0x44")
shown = 0
for base in found:
    desc = d.proc_read(pid, base, 0x60)
    if not desc:
        continue
    addr, = struct.unpack_from("<Q", desc, 0x20)
    size, = struct.unpack_from("<I", desc, 0x2C)
    fmt, = struct.unpack_from("<I", desc, 0x38)
    if not (arena[0] <= addr < arena[1]) or size < (1 << 20):
        continue
    chunks = 64; step = size // chunks; cm = ""
    for c in range(chunks):
        samp = d.proc_read(pid, addr + c * step + step // 3, 256) or b""
        samp2 = d.proc_read(pid, addr + c * step + (2 * step) // 3, 256) or b""
        cm += "#" if (any(samp) or any(samp2)) else "."
    print(f"desc {base:#x}: surface {addr:#x} size {size/2**20:.1f} MB fmt {fmt:#x}\n    {cm}  ({cm.count('#')}/64 chunks with data)")
    shown += 1
    if shown >= 12:
        break
