#!/usr/bin/env python3
"""Alternate a sampler field in the live game, with a PS5 toast and a log line (host time + console epoch ms,
to match screenshots by .meta absoluteTime) at every switch. Generalises aniso_loop.py.
Usage: python3 sampler_loop.py <aniso|bias> <seq e.g. 0,-0.75,0,-0.75> <hold_seconds>  -> $PS5_WORKDIR/sampler_loop.log
Sampler table: [[0x59406c8]+0x250]+0x360, 19 x 0x38 B; +0 = mipLODBias (float), +4 = MaxAnisotropy (int).
Writes the 9 geometry samplers (WRAP/CLAMP/BLACK/GRAY ANISO, Diffuse/Specular/Bump/DetailBump, GIMap).
Leaves the LAST state set.  Needs tools/dev/core (ps5dbg.py, onion_sample.py); toasts are optional (PS5_NOTIFY_ELF)."""
import struct, subprocess, sys, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath, toast
from ps5dbg import Dbg
import onion_sample
IDX = [8, 9, 10, 11, 12, 13, 14, 15, 17]
field = sys.argv[1]; hold = float(sys.argv[3])
assert field in ("aniso", "bias")
seq = [float(x) for x in sys.argv[2].split(",")]
OFF, FMT = (4, "<I") if field == "aniso" else (0, "<f")
conv = int if field == "aniso" else float
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
def base():
    g = struct.unpack("<Q", d.proc_read(pid, 0x59406C8, 8))[0]
    return struct.unpack("<Q", d.proc_read(pid, g + 0x250, 8))[0] + 0x360
def setv(v):
    b = base()
    for i in IDX:
        a = b + i * 0x38 + OFF
        st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, 4)); assert st == 0x80000000, hex(st)
        d.s.sendall(struct.pack(FMT, conv(v))); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
    got = [struct.unpack(FMT, d.proc_read(pid, b + i * 0x38 + OFF, 4))[0] for i in IDX]
    assert all(abs(g - conv(v)) < 1e-6 for g in got), got
log = open(workpath("sampler_loop.log"), "w")
for n, v in enumerate(seq, 1):
    setv(v)
    s = onion_sample.read() or {}
    cons = (time.time() - s["age_s"]) if "age_s" in s else 0
    line = f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={int(cons*1000)} | state={n}/{len(seq)} {field}={v:g}"
    print(line, flush=True); log.write(line + "\n"); log.flush()
    toast(f"{field.upper()} {v:g} ({n}/{len(seq)}) - wait for the notification to disappear, then take a screenshot")
    time.sleep(hold)
log.write(f"DONE (left at {seq[-1]:g})\n"); log.close(); print("DONE, left at", f"{seq[-1]:g}", flush=True)
