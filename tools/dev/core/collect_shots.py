#!/usr/bin/env python3
"""Fetch the screenshots of an ab_loop run and sort them into states.
Usage: python3 collect_shots.py <ab_loop log> <outdir> [--n 40]
Parses the log (`console_epoch_ms=<ms> | state i/N = <label>` lines, label = "<state>" or "<scene> :: <state>", the `shot: ... ack_epoch_ms=<ms>` lines and `RESTORED all`),
lists the newest N photos on the console (ftp .../photo/NPXS40087/<title>/<hash>/<ts>.jxr|.meta) and matches each photo's `.meta` absoluteTime to the shot that took it
(absoluteTime ~ ack_epoch_ms - 1.0 s, tolerance 0.7 s); photos that match no ack fall back to the state window that was active.
Downloads <outdir>/<ii>_<scene>__<state>_<k>.{jxr,meta} and writes <outdir>/manifest.json (file, scene, state, state_index, absoluteTime, ...)."""
import json, re, subprocess, sys, os
from ps5env import ftp_url
FTP = ftp_url("user/av_contents/photo/NPXS40087/")
ACK_OFFSET_MS, ACK_TOL_MS = 1000, 700
def get(path, binary=False, t=30):
    r = subprocess.run(["curl", "-gsS", "-m", str(t), FTP + path], capture_output=True); return r.stdout if binary else r.stdout.decode("utf-8", "ignore")
def listdir(path): return [l.split()[-1] for l in get(path).splitlines() if l.strip() and l.split()[-1] not in (".", "..")]
def slug(x, n=24): return re.sub(r"[^A-Za-z0-9]+", "_", x).strip("_")[:n]
log, out = sys.argv[1], sys.argv[2]; N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 40
states, end = [], None            # state = {start, idx, label, scene, state, acks}
for line in open(log, errors="ignore"):
    m = re.search(r"console_epoch_ms=(\d+) \| state (\d+)/(\d+) = (.+)$", line)
    if m:
        label = m.group(4).strip(); sc, _, st = label.partition(" :: ")
        states.append({"start": int(m.group(1)), "idx": int(m.group(2)), "label": label, "scene": sc if st else "", "state": st or label, "acks": []}); continue
    m = re.search(r"shot: ok=True .*ack_epoch_ms=(\d+)", line)
    if m and states: states[-1]["acks"].append(int(m.group(1))); continue
    m = re.search(r"console_epoch_ms=(\d+) \| RESTORED", line)
    if m: end = int(m.group(1))
if not states: sys.exit("no states in log")
t_lo = states[0]["start"] - 2000; t_hi = (end or states[-1]["start"] + 30000) + 2000
files = []
for title in listdir(""):
    for h in listdir(title + "/"):
        for f in listdir(f"{title}/{h}/"):
            if f.endswith(".jxr"): files.append((f, f"{title}/{h}/{f}"))
files.sort(key=lambda x: x[0]); files = files[-N:]
os.makedirs(out, exist_ok=True); manifest = []; counts = {}
for fname, path in files:
    meta = get(path[:-4] + ".meta"); m = re.search(r'"absoluteTime":\[\[(\d+)', meta)
    if not m: continue
    t = int(m.group(1))
    if not (t_lo <= t <= t_hi): continue
    best = None
    for si, s in enumerate(states):                      # 1) by the shot's ack time (robust for short holds)
        for ack in s["acks"]:
            err = abs(t - (ack - ACK_OFFSET_MS))
            if err <= ACK_TOL_MS and (best is None or err < best[0]): best = (err, si)
    if best is not None: idx, how = best[1], "ack"
    else:                                                # 2) fallback: the state window that was active
        idx = max((i for i, s in enumerate(states) if s["start"] - 2000 <= t), default=0); how = "window"
    s = states[idx]; k = counts.get(idx, 0); counts[idx] = k + 1
    base = f"{s['idx']:02d}_" + (f"{slug(s['scene'])}__" if s["scene"] else "") + f"{slug(s['state'])}_{k}"
    open(f"{out}/{base}.jxr", "wb").write(get(path, binary=True, t=90)); open(f"{out}/{base}.meta", "w").write(meta)
    manifest.append({"file": base, "photo": path, "absoluteTime": t, "scene": s["scene"], "state": s["state"], "state_index": s["idx"], "matched_by": how,
                     "state_start_ms": s["start"], "offset_into_state_s": round((t - s["start"]) / 1000, 2)})
manifest.sort(key=lambda x: x["absoluteTime"])
json.dump(manifest, open(f"{out}/manifest.json", "w"), indent=1, ensure_ascii=False)
print(f"{len(manifest)} photos matched to {len(states)} states -> {out}")
for m in manifest: print(f"  state {m['state_index']} {m['scene']!r} {m['state']!r}: {m['file']} (+{m['offset_into_state_s']} s, by {m['matched_by']})")
