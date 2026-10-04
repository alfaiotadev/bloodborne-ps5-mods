#!/usr/bin/env python3
"""Temporarily set a small integer in the live game, toast + log, ALWAYS restore the original value.
Usage: python3 flag_toggle.py <addr_hex> <size 1|2|4> <new_value_hex> <hold_s> [<check_addr_hex> <check_qword_hex>] [label]
The optional check (e.g. object address + its vtable pointer) must match, otherwise nothing is written.
Log lines carry console_epoch_ms to match screenshots by .meta absoluteTime. Needs tools/dev/core (ps5dbg.py, onion_sample.py); toasts are optional (PS5_NOTIFY_ELF)."""
import struct, subprocess, sys, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import toast
from ps5dbg import Dbg
import onion_sample
a = sys.argv
ADDR = int(a[1], 16); SIZE = int(a[2]); NEW = int(a[3], 16); HOLD = float(a[4])
CHK = (int(a[5], 16), int(a[6], 16)) if len(a) > 6 else None
LABEL = a[7] if len(a) > 7 else f"{ADDR:#x}"
FMT = {1: "<B", 2: "<H", 4: "<I"}[SIZE]
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
def rd(): return struct.unpack(FMT, d.proc_read(pid, ADDR, SIZE))[0]
def wr(v):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, ADDR, SIZE)); assert st == 0x80000000, hex(st)
    d.s.sendall(struct.pack(FMT, v)); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
    assert rd() == v, hex(rd())
def cons_ms():
    s = onion_sample.read() or {}
    return int((time.time() - s["age_s"]) * 1000) if "age_s" in s else 0
if CHK:
    got = struct.unpack("<Q", d.proc_read(pid, CHK[0], 8))[0]
    assert got == CHK[1], f"check failed: {got:#x} != {CHK[1]:#x} (object moved? game restarted?)"
orig = rd(); print(f"{LABEL} @ {ADDR:#x} = {orig:#x}; will set {NEW:#x} for {HOLD:.0f} s", flush=True)
try:
    wr(NEW); print(f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={cons_ms()} | SET {LABEL}={NEW:#x}", flush=True)
    toast(f"{LABEL}={NEW:#x} {HOLD:.0f} s - watch the screen / take a screenshot")
    time.sleep(HOLD)
finally:
    wr(orig); print(f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={cons_ms()} | RESTORED {LABEL}={rd():#x}", flush=True)
    toast(f"{LABEL} restored")
