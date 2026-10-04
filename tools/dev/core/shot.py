#!/usr/bin/env python3
"""Remote screenshot trigger for the patched onionHEN ShellUI payload.
The payload remembers the arguments of a REAL screenshot press (press the screenshot button ONCE after ShellUI has loaded),
then replays CaptureScreen when /system_tmp/onionhen/screenshot_request appears (checked on the UI thread every ~6 frames).
  python3 shot.py state              print screenshot_state ("valid=1 ..." = armed)
  python3 shot.py [n] [interval_s]   request n screenshots (default 1), wait for the ack each time
Library:  import shot; ok, ack_epoch_ms, status = shot.trigger()   (status 0 = called, 1 = not armed yet, 2 = original missing)"""
import subprocess, sys, time
from ps5env import workpath, ftp_url
FTP_DIR = "system_tmp/onionhen/"
def _get(name):
    r = subprocess.run(["curl", "-gsS", "-m", "5", ftp_url(FTP_DIR + name)], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""
def state(): return _get("screenshot_state")
def trigger(timeout=4.0):
    prev = _get("screenshot_ack")
    open(workpath("shot_req"), "w").write("1")
    subprocess.run(["curl", "-gsS", "-m", "10", "-T", workpath("shot_req"), ftp_url(FTP_DIR + "screenshot_request")], check=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.15); a = _get("screenshot_ack")
        if a and a != prev:
            ms, st = a.split()[:2]; return int(st) == 0, int(ms), int(st)
    return False, 0, -1
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "state": print(state() or "(no state file: payload not loaded or never pressed)"); sys.exit()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1; iv = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    for i in range(n):
        ok, ms, st = trigger(); print(f"shot {i+1}/{n}: ok={ok} status={st} ack_epoch_ms={ms}", flush=True)
        if i + 1 < n: time.sleep(iv)
