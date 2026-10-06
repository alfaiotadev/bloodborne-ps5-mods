#!/usr/bin/env python3
"""Make the VRR mode of PS4 (backward-compatible) games a 119.88 Hz mode (HDMI timing 1080P_11988, VRR range 48-120 Hz).

Read docs/vrr.md first. This tool WRITES CODE into a system process (SceSysAvControl.elf, the system video service).
It is meant to be used together with `vrr_watch.py --hz120` and ONLY for 1080p PS4 games, and it is tested only on
system software 12.40 (PS5 Pro, Bloodborne). It is not permanent: a console restart removes it.

Why it is needed. Setting the "VRR supported" bit of a PS4 game (vrr_watch.py) gives VRR 60 Hz: the refresh enum of the
mode becomes 0x8003 and the HDMI timing stays 1080P_5994, so the display never runs faster than 60 Hz. The service chooses
the HDMI timing (a table index, byte +0xd of its hardware mode record; 8 = 1080P_5994, 0x2e = 1080P_11988) from the
REQUESTED refresh enum, before the VRR conversion. Changing only the VRR enum to 0x800d (VRR 119.88) therefore left the
link at 59.94 Hz. The patch has three parts:

  P1  0x42D87E  4 bytes     VRR conversion of refresh 3 / 9: 0x8003 -> 0x800D (VRR 119.88 Hz, range 48-120 Hz)
  P2  0x4A2844  32 bytes    code cave in int3 padding: sets the timing index to 0x2E (1080P_11988) when the converted
                            refresh is 0x800D and the resolution is 1080p; then runs the two instructions it replaced
  P3  0x42D88E  7 bytes     jump to P2 (replaces `or byte [rbx+4],0x80 ; mov r12d,r11d`, both re-executed by P2)

The conversion only runs for apps that the service allows VRR for (the attr bit set by vrr_watch.py); apps without it are
not affected. Every original byte string is verified before anything is written; the order is P1, P2, P3 (the jump
last); `restore` undoes P3, P2, P1.

Usage (PS5_HOST must be set, the ps5debug payload must be running)
  python3 vrr120_patch.py plan       show the state of the three patches, write nothing
  python3 vrr120_patch.py apply      write them (do this BEFORE the game starts, with vrr_watch.py --hz120 running)
  python3 vrr120_patch.py restore    put the original bytes back

Firmware 12.40 addresses only. On any other build the original bytes will not match and nothing is written.
"""
import os
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dev", "core")]
from ps5dbg import Dbg  # noqa: E402

PROC_NAME = "SceSysAvControl.elf"
CAVE = bytes.fromhex("804b04804181f80d800000750b41837e140b7504c6430d2e4589dce931b0f8ff")
JUMP = bytes.fromhex("e9b14f07006690")
# (name, address, original, patched)
PATCHES = [
    ("P1", 0x42D87E, bytes.fromhex("03800000"), bytes.fromhex("0d800000")),
    ("P2", 0x4A2844, b"\xcc" * len(CAVE), CAVE),
    ("P3", 0x42D88E, bytes.fromhex("804b04804589dc"), JUMP),
]


def state(d, pid, addr, orig, new):
    cur = d.proc_read(pid, addr, len(orig))
    if cur is None:
        return "unreadable"
    return "original" if cur == orig else "patched" if cur == new else "UNEXPECTED (" + cur.hex() + ")"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd not in ("plan", "apply", "restore"):
        raise SystemExit(__doc__)
    d = Dbg()
    pid = next((p for n, p in d.proc_list() if n == PROC_NAME), None)
    if pid is None:
        raise SystemExit(PROC_NAME + " not found (is ps5debug running on this console?)")
    states = [(name, addr, orig, new, state(d, pid, addr, orig, new)) for name, addr, orig, new in PATCHES]
    for name, addr, orig, new, st in states:
        print("%s %#x (%2d bytes): %s" % (name, addr, len(new), st))
    if any(s[4].startswith(("UNEXPECTED", "unreadable")) for s in states):
        raise SystemExit("unexpected content: another firmware or an older edit - nothing written")
    if cmd == "apply":
        for name, addr, orig, new, st in states:
            if st == "original":
                d.proc_write(pid, addr, new)
                if d.proc_read(pid, addr, len(new)) != new:
                    raise SystemExit("read-back mismatch at %#x - run `restore`" % addr)
                print("written", name)
        print("done; undo with: vrr120_patch.py restore")
    elif cmd == "restore":
        for name, addr, orig, new, st in reversed(states):
            if st == "patched":
                d.proc_write(pid, addr, orig)
                print("restored", name)
        print("done")


if __name__ == "__main__":
    main()
