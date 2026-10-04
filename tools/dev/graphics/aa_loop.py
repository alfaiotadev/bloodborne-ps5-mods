#!/usr/bin/env python3
"""Alternate force-AA OFF/ON in the live game and log every state change with
host time and console epoch time, so screenshots can be matched to states.
Usage: python3 aa_loop.py <rounds> <hold_seconds>  -> $PS5_WORKDIR/aa_loop.log
Starts OFF, ends ON.  Needs ps5debug + tools/dev/core (ps5dbg.py, onion_sample.py)."""
import struct, sys, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
from ps5dbg import Dbg
import onion_sample
ADDR = 0x25d8034; OFF = bytes.fromhex("0f95c0"); ON = bytes.fromhex("b00190")
rounds = int(sys.argv[1]); hold = float(sys.argv[2])
d = Dbg()
pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
def put(b):
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, ADDR, len(b))); assert st == 0x80000000
    d.s.sendall(b); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
log = open(workpath("aa_loop.log"), "w")
def note(label):
    time.sleep(1.5)
    s = onion_sample.read() or {}
    fx = (s.get("dbg") or "").split("FX:")[1][:1] if "FX:" in (s.get("dbg") or "") else "?"
    # console epoch ~ host time + offset; sample age_s is (host now - console unix) so epoch = now - age
    cons = time.time() - s["age_s"] if "age_s" in s else 0
    line = f"{time.strftime('%H:%M:%S')} host | console_epoch={cons:.0f} | state={label} | FX={fx} | fps={s.get('fps')}"
    print(line, flush=True); log.write(line + "\n"); log.flush()
for r in range(rounds):
    put(OFF); note(f"OFF r{r+1}"); time.sleep(max(0, hold - 1.5))
    put(ON);  note(f"ON  r{r+1}"); time.sleep(max(0, hold - 1.5))
log.write("DONE (left ON)\n"); log.close()
