#!/usr/bin/env python3
"""Inspect or edit the per-app capability record ("attr") of the running PS4 game inside SceSysAvControl.elf.

This is the manual counterpart of vrr_watch.py: use it to look at the entries, to try other bit combinations, or to
restore the original value. See docs/vrr.md and docs/agents/75-avcontrol-vrr.md for what the bits mean.

Usage (PS5_HOST must be set, the PS4 game must be running)
  python3 avctl_attr.py scan             list the table entries that hold the PS4 default 0x082E0057 (or a value set by this tool)
  python3 avctl_attr.py set HEX          write HEX into the attr dword of every such entry (original values are remembered)
  python3 avctl_attr.py restore          write the remembered original values back
After `set`, the console re-evaluates the video mode when the app is suspended and resumed (press the PS button and go
back to the game); the effect shows in the system log as `VRR(peg:60 range:48 - 60)`.

Entry layout: three dwords {key, appid, attr}; key is the process id or 0xFFFFFFFE; each app has two entries, and the
table exists twice (in .data and in the shared memory mapping /SceAvControl), so up to four dwords change together.
The remembered originals live in PS5_WORKDIR/avctl_orig.json (default ./work).

Writing a system process is risky: only the attr dwords found by the scan are touched, but a wrong value could confuse the
video pipeline until the console restarts. Tested only on firmware 12.40, PS5 Pro.
"""
import json
import os
import struct
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dev", "core")]
import ps5env  # noqa: E402
from ps5dbg import Dbg  # noqa: E402

PROC_NAME = "SceSysAvControl.elf"
PS4_DEFAULTS = [0x082E0057, 0x082E0257]      # running / suspended


def save_path():
    return ps5env.workpath("avctl_orig.json")      # created on first use (PS5_WORKDIR, default ./work)


def scan(d, pid, attr_values):
    hits = set()
    for _name, s, e, _off, prot in d.proc_maps(pid):
        if not (prot & 2) or (e - s) > (128 << 20):
            continue
        pos = s
        while pos < e:
            n = min(0x40000, e - pos)
            b = d.proc_read(pid, pos, n)
            if b:
                for av in attr_values:
                    pat = struct.pack("<I", av)
                    i = b.find(pat)
                    while i != -1:
                        if i >= 8 and i % 4 == 0:
                            key, appid, attr = struct.unpack_from("<III", b, i - 8)
                            if appid not in (0, 0xFFFFFFFF) and (key == 0xFFFFFFFE or 0 < key < 0x10000):
                                hits.add((pos + i, key, appid, attr))
                        i = b.find(pat, i + 1)
            pos += n
    return sorted(hits)


def write32(d, pid, addr, value):
    d.proc_write(pid, addr, struct.pack("<I", value))
    assert struct.unpack("<I", d.proc_read(pid, addr, 4))[0] == value, "readback mismatch"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    d = Dbg()
    pid = next(p for n, p in d.proc_list() if n == PROC_NAME)
    SAVE = save_path()
    saved = {int(k): v for k, v in json.load(open(SAVE)).items()} if os.path.exists(SAVE) else {}
    values = list(PS4_DEFAULTS)
    if saved:   # entries we modified earlier: look for their current values too
        values += sorted({struct.unpack("<I", d.proc_read(pid, a, 4))[0] for a in saved})
    if cmd == "scan":
        for a, k, ap, at in scan(d, pid, values):
            print("%#x: key=%#x appid=%#x attr=%#x" % (a, k, ap, at))
    elif cmd == "set":
        new = int(sys.argv[2], 16)
        hits = scan(d, pid, values)
        if not 2 <= len(hits) <= 8:
            raise SystemExit("expected 2..8 entries, found %d (is the PS4 game running?)" % len(hits))
        for a, k, ap, at in hits:
            saved.setdefault(a, [k, ap, at])          # keep the FIRST original per address
        json.dump({str(a): v for a, v in saved.items()}, open(SAVE, "w"))
        for a, k, ap, at in hits:
            write32(d, pid, a, new)
            print("%#x: appid=%#x %#x -> %#x" % (a, ap, at, new), flush=True)
    elif cmd == "restore":
        for a, (k, ap, at) in saved.items():
            if struct.unpack("<I", d.proc_read(pid, a - 4, 4))[0] != ap:
                print("%#x: appid changed, skipped" % a)
                continue
            write32(d, pid, a, at)
            print("%#x: restored %#x" % (a, at), flush=True)
        if os.path.exists(SAVE):
            os.remove(SAVE)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
