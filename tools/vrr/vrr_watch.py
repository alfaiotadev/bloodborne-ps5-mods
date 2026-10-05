#!/usr/bin/env python3
"""Turn VRR on for PS4 (backward-compatible) games at launch.

Why: the PS5 keeps a small capability record ("attr") for every running app inside the system process
SceSysAvControl.elf. For PS4 games it is 0x082E0057, which says "no VRR" (the log shows `VRR:x`). If bit 0x00800000 is set
before the console picks the video mode for the new app, the HDMI output switches to VRR 60 Hz (range 48-60 Hz).
This script watches the table and sets that bit as soon as a new PS4 session appears. See docs/vrr.md.

What it writes: ONLY the 32-bit attr field of table entries whose current value is exactly 0x082E0057 (the PS4 default),
never anything else, and only in the process SceSysAvControl.elf. Nothing is permanent: the entry disappears when the game
exits, and a console restart clears everything. Start it BEFORE the game; stop it with Ctrl-C.

Usage
  PS5_HOST=<console ip> python3 vrr_watch.py [--attr 8ae0057] [--dry-run] [--window ADDR:SIZE ...]
    --attr HEX       value written into the entries (default 0x08AE0057 = default | VRR supported, type A)
    --dry-run        only report what would be written
    --window A:S     extra table window to poll (hex address:hex size); the built-in windows are for firmware 12.40

Requirements: the ps5debug payload on the console (TCP 744, see tools/dev/README.md), Python 3.8+.
Tested only on firmware 12.40, PS5 Pro, with Bloodborne. Other games and firmware are untested.
"""
import os
import struct
import sys
import time

sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dev", "core")]
from ps5dbg import Dbg  # noqa: E402

PROC_NAME = "SceSysAvControl.elf"
PS4_DEFAULT_ATTR = 0x082E0057        # attr of every PS4 (BC) game seen so far: "no HDR/HFR/VR/VRR/8K"
VRR_TYPE_A = 0x00800000              # bit: app supports VRR (type A); 0x01000000 would make it type B
DEFAULT_TARGET = PS4_DEFAULT_ATTR | VRR_TYPE_A
DATA_WINDOW = (0x4F9000, 0x1000)     # .data table of {key, appid, attr} dword triples, firmware 12.40
SHM_NAME = "/SceAvControl"           # shared-memory copy of the table (found by name, whole mapping is polled)
POLL_SECONDS = 0.02


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def find_avcontrol(d):
    for name, pid in d.proc_list():
        if name == PROC_NAME:
            return pid
    raise LookupError(PROC_NAME + " not found in the process list")


def windows(d, pid, extra):
    out = [DATA_WINDOW] + list(extra)
    for name, start, end, _off, _prot in d.proc_maps(pid):
        if name == SHM_NAME:
            out.append((start, end - start))
    return out


def looks_like_table(block):
    """Sanity check of the built-in .data window: system apps there have attr 0x?8?0057 with bit 0x08000000 set."""
    n = 0
    for i in range(0, len(block) - 11, 4):
        _key, appid, attr = struct.unpack_from("<III", block, i)
        if 1 <= appid < 0x40 and (attr & 0xFF) == 0x57 and (attr & 0x08000000):
            n += 1
    return n >= 2


def default_entries(d, pid, wins):
    """Addresses of the attr dwords of all table entries that still hold the PS4 default."""
    pat = struct.pack("<I", PS4_DEFAULT_ATTR)
    hits = []
    for base, size in wins:
        b = d.proc_read(pid, base, size)
        if not b:
            continue
        i = b.find(pat)
        while i != -1:
            if i >= 8 and i % 4 == 0:
                key, appid, _attr = struct.unpack_from("<III", b, i - 8)
                if appid not in (0, 0xFFFFFFFF) and (key == 0xFFFFFFFE or 0 < key < 0x10000):
                    hits.append((base + i, key, appid))
            i = b.find(pat, i + 1)
    return hits


def main():
    args = sys.argv[1:]
    target = int(args[args.index("--attr") + 1], 16) if "--attr" in args else DEFAULT_TARGET
    dry = "--dry-run" in args
    extra = [(int(a, 16), int(s, 16)) for a, s in (w.split(":") for w in
             [args[i + 1] for i, x in enumerate(args) if x == "--window"])]
    d = None
    pid = None
    wins = None
    checked = False
    log("vrr_watch started: target attr 0x%08X%s" % (target, " (dry run)" if dry else ""))
    while True:
        try:
            if d is None:
                d = Dbg()
                pid = find_avcontrol(d)
                wins = windows(d, pid, extra)
                log("connected to %s (pid %d), polling %d windows" % (PROC_NAME, pid, len(wins)))
                if not checked:
                    block = d.proc_read(pid, *DATA_WINDOW)
                    if not (block and looks_like_table(block)):
                        log("WARNING: the built-in table window does not look like the capability table "
                            "(other firmware?). Run avctl_attr.py scan while a PS4 game runs and pass --window.")
                    checked = True
            hits = default_entries(d, pid, wins)
            if hits:
                for addr, _key, _appid in hits:
                    if not dry:
                        d.proc_write(pid, addr, struct.pack("<I", target))
                log("session appid=0x%x: attr 0x%08X -> 0x%08X in %d entries%s"
                    % (hits[0][2], PS4_DEFAULT_ATTR, target, len(hits), " (not written)" if dry else ""))
                if dry:
                    time.sleep(1.0)
            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            log("stopped")
            return
        except Exception as e:  # console busy / connection dropped / process restarted: reconnect
            d = None
            log("%s: %s; reconnecting" % (type(e).__name__, e))
            time.sleep(2)


if __name__ == "__main__":
    main()
