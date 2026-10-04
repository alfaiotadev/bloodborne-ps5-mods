#!/usr/bin/env python3
"""Decode the daemon->ShellUI shared sample (128 B) read over FTP.
Usage:  python3 onion_sample.py [seconds] [interval]
Layout: magic u32, seq u32, pid i32, valid u8, source u8, pad[2], fps f32,
pad u32, unix_ns u64, title_id[16], game_mem_mb u32, dbg[72], reserved[4]."""
import struct, subprocess, sys, time
from ps5env import ftp_url

def read():
    raw = subprocess.run(["curl","-gsS","-m5",ftp_url("system_tmp/onionhen/fps_sample")],
                         capture_output=True).stdout
    if len(raw) != 128: return None
    magic, seq, pid, valid, source = struct.unpack_from("<IIiBB", raw, 0)
    fps, = struct.unpack_from("<f", raw, 16)
    unix_ns, = struct.unpack_from("<Q", raw, 24)
    tid = raw[32:48].split(b"\0")[0].decode("latin1")
    mem, = struct.unpack_from("<I", raw, 48)
    dbg = raw[52:124].split(b"\0")[0].decode("latin1")
    age = time.time() - unix_ns/1e9 if unix_ns else -1
    return dict(magic=hex(magic), seq=seq, pid=pid, valid=valid, fps=round(fps,1),
                tid=tid, game_mem_mb=mem, dbg=dbg, age_s=round(age,1))

if __name__ == "__main__":
    total = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 2
    t0 = time.time()
    while True:
        print(time.strftime("%H:%M:%S"), read(), flush=True)
        if time.time() - t0 >= total: break
        time.sleep(step)
