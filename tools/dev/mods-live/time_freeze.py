#!/usr/bin/env python3
"""Freeze game time for N seconds by writing a tiny dt into the fixed timestep field, then restore it.
Usage: python3 time_freeze.py <dt_field_addr_hex> <hold_seconds> [dt_hex=358637bd (1e-6)]
dt field = timestep object + 0x18 (find with find_timestep_obj.py). Refuses to write unless the field currently reads
0x3c888889 (1/60 s). ALWAYS restores 0x3c888889 (finally). Toast + log with console epoch (match screenshots by .meta absoluteTime)."""
import struct, subprocess, sys, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import toast
from ps5dbg import Dbg
import onion_sample
ADDR = int(sys.argv[1], 16); HOLD = float(sys.argv[2]); FREEZE = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x358637bd
NORMAL = 0x3c888889
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
def rd(): return struct.unpack("<I", d.proc_read(pid, ADDR, 4))[0]
def wr(v):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, ADDR, 4)); assert st == 0x80000000, hex(st)
    d.s.sendall(struct.pack("<I", v)); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
    assert rd() == v, hex(rd())
def cons_ms():
    s = onion_sample.read() or {}
    return int((time.time() - s["age_s"]) * 1000) if "age_s" in s else 0
cur = rd(); print(f"dt field {ADDR:#x} = {cur:#x}", flush=True)
assert cur == NORMAL, f"unexpected value {cur:#x}, refusing"
try:
    wr(FREEZE); t0 = cons_ms()
    print(f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={t0} | FROZEN dt={FREEZE:#x}", flush=True)
    toast(f"TIME FROZEN {HOLD:.0f} s - take 2 screenshots")
    time.sleep(HOLD)
finally:
    wr(NORMAL); t1 = cons_ms()
    print(f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={t1} | RESTORED dt={rd():#x}", flush=True)
    toast("TIME RESTORED")
