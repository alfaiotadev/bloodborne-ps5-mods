#!/usr/bin/env python3
"""Alternate MaxAnisotropy of the game's aniso samplers in the live game, with a PS5 toast and a log line
(host time + console epoch ms, to match screenshots by .meta absoluteTime) at every switch.
Usage: python3 aniso_loop.py <seq e.g. 4,16,4,16> <hold_seconds>   -> $PS5_WORKDIR/aniso_loop.log
Sampler table: [[0x59406c8]+0x250]+0x360, 19 x 0x38 B, +4 = MaxAnisotropy (int). Leaves the LAST state set.
Needs tools/dev/core (ps5dbg.py, onion_sample.py); toasts are optional (PS5_NOTIFY_ELF)."""
import struct, subprocess, sys, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath, toast
from ps5dbg import Dbg
import onion_sample
IDX = [8, 9, 10, 11, 12, 13, 14, 15, 17]     # WRAP/CLAMP/BLACK/GRAY ANISO, Diffuse/Specular/Bump/DetailBump, GIMap
seq = [int(x) for x in sys.argv[1].split(",")]; hold = float(sys.argv[2])
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
def base():
    g = struct.unpack("<Q", d.proc_read(pid, 0x59406C8, 8))[0]
    return struct.unpack("<Q", d.proc_read(pid, g + 0x250, 8))[0] + 0x360
def setv(v):
    b = base()
    for i in IDX:
        a = b + i * 0x38 + 4
        st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, 4)); assert st == 0x80000000, hex(st)
        d.s.sendall(struct.pack("<I", v)); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
    got = [struct.unpack("<I", d.proc_read(pid, b + i * 0x38 + 4, 4))[0] for i in IDX]
    assert got == [v] * len(IDX), got
log = open(workpath("aniso_loop.log"), "w")
for n, v in enumerate(seq, 1):
    setv(v)
    s = onion_sample.read() or {}
    cons = (time.time() - s["age_s"]) if "age_s" in s else 0
    line = f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={int(cons*1000)} | state={n}/{len(seq)} aniso={v}x"
    print(line, flush=True); log.write(line + "\n"); log.flush()
    toast(f"ANISO {v}x ({n}/{len(seq)}) - wait for the notification to disappear, then take a screenshot")
    time.sleep(hold)
log.write(f"DONE (left at {seq[-1]}x)\n"); log.close(); print("DONE, left at", seq[-1], "x", flush=True)
