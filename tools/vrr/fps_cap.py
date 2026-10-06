#!/usr/bin/env python3
"""Cap the frame rate of the running Bloodborne at a value inside the VRR window (live, nothing is saved).

With VRR 60 active the display follows the game's frame rate between 48 and 60 Hz. The game normally runs at a fixed
60 FPS, so VRR has nothing to follow; a cap of, say, 55 FPS makes the benefit visible (steady 18.18 ms frames, display
refresh 55 Hz). Below 48 FPS the display leaves the VRR window and its refresh readout starts to jump - keep the cap >= 48.
With the 120 Hz link (vrr_watch.py --hz120 and vrr120_patch.py, see docs/vrr.md) caps up to 118 work with vsync on:
100 gave a flat 10.00 ms frame time on the tested setup; on a plain 60 Hz link a cap above 60 changes nothing (vsync).

Usage (PS5_HOST must be set, the game must be running with the 60 FPS mod on)
  python3 fps_cap.py set 55      limit the game to 55 FPS (vsync stays on); 48..60 on the VRR 60 link, up to 118 on the 120 Hz link
  python3 fps_cap.py off         back to 60 FPS
  python3 fps_cap.py status      show the current cap and measure the frame times for 3 s

How: the engine's frame timer waits until each frame is at least `target` seconds long. The target is rewritten every
frame from an immediate in the code (Bloodborne v1.09: `mov dword [r12+0x18], imm32` at 0x243487E, imm32 at 0x2434883);
the 60 FPS mod stores 1/60 there. This tool writes 1/cap instead. A write to the frame timer FIELD would be undone within
a frame, which is why the code immediate is patched. The patch lives in the running game only; closing the game removes it.
Game-specific: Bloodborne GOTY CUSA03173 v01.09 on firmware 12.40 (PS5 Pro), other titles/versions are not supported.
"""
import os
import statistics
import struct
import sys
import time

sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dev", "core")]
from ps5dbg import Dbg  # noqa: E402

LIMITER_IMM = 0x2434883                       # imm32 = frame-timer target (float seconds)
VSYNC_SITE = 0x25B3271                        # 44 89 e6 = Present interval kept (vsync); the experimental unlock writes 48 31 f6
VSYNC_ON = bytes.fromhex("4489e6")
SIXTY_FPS_MOD_SITE = 0x2483EC1                # `ret` (0xC3) when the 60 FPS mod is active, `call` (0xE8) in the stock game
ONE_SIXTIETH = bytes.fromhex("8988883c")      # 60 FPS mod: 1/60 s as float32 little endian
FRAME_TIMER_PTR = 0x59404F8                   # global pointer to the frame-timer object
RING_OFFSET, RING_INDEX = 0x60, 0x260         # 32 x 16 bytes of frame durations (us, u64), ring head index


def connect():
    d = Dbg()
    pid = [p for n, p in d.proc_list() if n == "eboot.bin"]
    if not pid:
        raise SystemExit("the game (eboot.bin) is not running")
    return d, pid[-1]


def current_cap(d, pid):
    return 1.0 / struct.unpack("<f", d.proc_read(pid, LIMITER_IMM, 4))[0]


def measure(d, pid, seconds=3.0):
    obj = struct.unpack("<Q", d.proc_read(pid, FRAME_TIMER_PTR, 8))[0]
    last, frames, t0 = None, [], time.time()
    while time.time() - t0 < seconds:
        raw = d.proc_read(pid, obj + RING_OFFSET, 0x204)
        idx = struct.unpack_from("<I", raw, 0x200)[0]
        if last is not None and idx != last:
            n = (idx - last) & 0x1F
            for k in range(n if 0 < n < 32 else 0):
                frames.append(struct.unpack_from("<Q", raw, ((last + 1 + k) & 0x1F) * 16)[0] / 1000.0)
        last = idx
        time.sleep(0.05)
    if not frames:
        return "no frames measured"
    s = sorted(frames)
    return "%.1f fps, median %.2f ms, p99 %.2f ms, max %.2f ms, stdev %.2f ms" % (
        len(frames) / seconds, s[len(s) // 2], s[min(len(s) - 1, int(len(s) * 0.99))], s[-1], statistics.pstdev(frames))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    d, pid = connect()
    if d.proc_read(pid, VSYNC_SITE, 3) != VSYNC_ON:
        raise SystemExit("the vsync site is not in its original state (an unlock experiment is active?) - restart the game")
    if cmd == "set":
        cap = float(sys.argv[2])
        if not 20 <= cap <= 118:
            raise SystemExit("cap must be between 20 and 118 (inside the VRR window: 48..60, or 48..118 with the 120 Hz link)")
        if cap > 60:
            print("note: a cap above 60 only has an effect on the 120 Hz link (vrr_watch.py --hz120 + vrr120_patch.py)")
        if d.proc_read(pid, SIXTY_FPS_MOD_SITE, 1) != b"\xc3":
            raise SystemExit("the 60 FPS mod is not active (or this is not Bloodborne v1.09): refusing to touch the frame timer")
        d.proc_write(pid, LIMITER_IMM, struct.pack("<f", 1.0 / cap))
        print("cap set to %g FPS" % cap)
        time.sleep(0.5)
    elif cmd == "off":
        d.proc_write(pid, LIMITER_IMM, ONE_SIXTIETH)
        print("cap removed (60 FPS)")
        time.sleep(0.5)
    elif cmd != "status":
        raise SystemExit(__doc__)
    print("limiter target: %.1f FPS" % current_cap(d, pid))
    print("measured:", measure(d, pid))


if __name__ == "__main__":
    main()
