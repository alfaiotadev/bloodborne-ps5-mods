#!/usr/bin/env python3
"""Generic live A/B loop: hold fixed writes (e.g. SFX-OFF=1) for the whole run, alternate states, toast + log each switch,
ALWAYS restore every touched address to its original value at the end (finally).
Usage: python3 ab_loop.py spec.json   (needs tools/dev/core: ps5dbg.py, onion_sample.py, shot.py, scenelib.py; toasts are optional, see PS5_NOTIFY_ELF)
spec = {"hold": 20, "sequence": ["A","B","A","B"],
        "fixed":  [{"addr":"0x22cf06196","fmt":"B","val":1,"check":["0x22cf05bd0","0x57b9080"]}],
        "states": {"A":[{"addr":"0x59409d4","fmt":"f","val":"orig"}], "B":[{"addr":"0x59409d4","fmt":"f","val":0.0}]}}
"shot_delay": 6  (optional: remote screenshot N s after each switch via shot.py),
"scenes": ["bridge_end_cobblestone", ...]  (optional: run the whole sequence once per scene: camera pose lock + game warp via scenelib, see scene.py; scenes file = "scenes_file" or $SCENES or $PS5_WORKDIR/scenes.json),
"scene_wait": 5 (s to wait after each warp for textures), "warmup": 1 (warm-up passes over all scenes without shots: a warp alone never unloads textures, so a warm start makes the runs repeatable), "noverify": true on a write = no read-back check (value consumed by the game within a frame), "toast": false (skip the on-screen toasts; they are not captured in screenshots anyway).
With scenes, log state labels are "<scene> :: <state>"; collect_shots.py sorts the photos by scene and state.  "restore_first": ["0xaddr", ...] = addresses restored first at the end (call sites before code caves). val may be "orig" (= value read before the run).  fmt: B (u8) H (u16) I (u32) f (float32) x (hex bytes, ONE atomic write: use for code patches). addr may be "vt:<vtable>+<off>" (heap object found by its vtable; survives game restarts; exactly one instance) or "vtall:<vtable>+<off>" (one write per live instance). "check": [addr, qword] must match before anything is written.
Log lines carry console_epoch_ms -> match screenshots by .meta absoluteTime."""
import json, os, struct, subprocess, sys, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath, toast
from ps5dbg import Dbg
import onion_sample
try:
    import shot
except Exception:
    shot = None
spec = json.load(open(sys.argv[1])); hold = float(spec.get("hold", 20)); seq = spec["sequence"]
scene_names = spec.get("scenes") or []; scene_wait = float(spec.get("scene_wait", 5.0)); use_toast = spec.get("toast", True)
SZ = {"B": 1, "H": 2, "I": 4, "f": 4}
def nbytes(w): return len(w["val"]) // 2 if w["fmt"] == "x" and w["val"] != "orig" else None
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
def rd(a, fmt, n=None):
    if fmt == "x": return d.proc_read(pid, a, n)
    return struct.unpack("<" + fmt, d.proc_read(pid, a, SZ[fmt]))[0]
def wr(a, fmt, v, n=None, nv=False):
    if fmt == "x":                       # ONE atomic write of n bytes (code patches must not be torn)
        data = orig[(a, fmt)] if v == "orig" else bytes.fromhex(v)
        st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, len(data))); assert st == 0x80000000, hex(st)
        d.s.sendall(data); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
        got = rd(a, "x", len(data)); assert got == data, (hex(a), got.hex(), data.hex()); return
    if v == "orig": v = orig[(a, fmt)]
    st = d.cmd(0xBDAA0003, struct.pack("<IQI", pid, a, SZ[fmt])); assert st == 0x80000000, hex(st)
    d.s.sendall(struct.pack("<" + fmt, v)); assert struct.unpack("<I", d._recvn(4))[0] == 0x80000000
    if nv: return                                    # "noverify": the game consumes this value within a frame (e.g. dirty flags)
    got = rd(a, fmt); assert (abs(got - v) < 1e-6 if fmt == "f" else got == v), (hex(a), got, v)
def cons_ms():
    s = onion_sample.read() or {}
    return int((time.time() - s["age_s"]) * 1000) if "age_s" in s else 0
def find_vt_all(vt):
    maps = d.proc_maps(pid); big = max(maps, key=lambda m: m[2] - m[1]); pat = struct.pack("<Q", vt); hits = []
    for name, s0, e0, off, prot in maps:
        if e0 - s0 < 4096 or e0 - s0 > (1 << 30) or prot & 2 == 0 or (s0, e0) == (big[1], big[2]): continue
        pos = s0
        while pos < e0:
            n = min(8 << 20, e0 - pos); b = d.proc_read(pid, pos, n)
            i = b.find(pat) if b else -1
            while i != -1:
                if (pos + i) % 8 == 0: hits.append(pos + i)
                i = b.find(pat, i + 1)
            pos += n
    return hits
def find_vt(vt):
    hits = find_vt_all(vt); assert len(hits) == 1, f"vtable {vt:#x}: {len(hits)} instances"
    return hits[0]
_vt = {}
def resolve(w):
    a = w["addr"]
    if isinstance(a, str) and a.startswith("vt:"):
        vt, off = a[3:].split("+"); vt = int(vt, 16)
        if vt not in _vt: _vt[vt] = find_vt(vt)
        w["addr"] = hex(_vt[vt] + int(off, 16)); w.pop("check", None)
    return w
_vtall = {}
def expand(lst):
    """addr "vtall:<vtable>+<off>" -> one write per live instance of that vtable (e.g. several scene objects; only the active one matters)."""
    out = []
    for w in lst:
        a = w["addr"]
        if isinstance(a, str) and a.startswith("vtall:"):
            vt, off = a[6:].split("+"); vt = int(vt, 16)
            if vt not in _vtall: _vtall[vt] = find_vt_all(vt); assert _vtall[vt], f"vtable {vt:#x}: no instances"
            for inst in _vtall[vt]:
                w2 = dict(w); w2["addr"] = hex(inst + int(off, 16)); w2.pop("check", None); out.append(w2)
        else: out.append(w)
    return out
if "fixed" in spec: spec["fixed"] = expand(spec["fixed"])
for _k in spec["states"]: spec["states"][_k] = expand(spec["states"][_k])
for w in list(spec.get("fixed", [])) + [w for st in spec["states"].values() for w in st]: resolve(w)
items = list(spec.get("fixed", [])) + [w for st in spec["states"].values() for w in st]
for w in items:
    if "check" in w:
        got = struct.unpack("<Q", d.proc_read(pid, int(w["check"][0], 16), 8))[0]
        assert got == int(w["check"][1], 16), f"check failed for {w['addr']}: {got:#x} (game restarted / object moved?)"
orig = {}
orig_len = {int(w["addr"], 16): len(w["val"]) // 2 for w in items if w["fmt"] == "x" and w["val"] != "orig"}
for w in items:
    a = int(w["addr"], 16)
    if w["fmt"] == "x": orig.setdefault((a, "x"), rd(a, "x", len(w["val"]) // 2 if w["val"] != "orig" else orig_len.get(a, 1)))
    else: orig.setdefault((a, w["fmt"]), rd(a, w["fmt"]))
log = open(workpath("ab_loop.log"), "w")
def out(s): print(s, flush=True); log.write(s + "\n"); log.flush()
out(f"{time.strftime('%H:%M:%S')} host | start; originals " + ", ".join(f"{a:#x}={v.hex() if f == 'x' else v}" for (a, f), v in orig.items()))
S = None
if scene_names:
    import scenelib
    sdb = json.load(open(spec.get("scenes_file", os.environ.get("SCENES", workpath("scenes.json")))))
    missing = [n for n in scene_names if n not in sdb]; assert not missing, f"unknown scenes: {missing}"
    S = scenelib.Scenes(d, pid, sdb)
total = len(seq) * max(1, len(scene_names)); n = 0
if spec.get("shot_delay") is not None and shot is not None:      # pre-flight: is the screenshot automation armed? (ShellUI restart / console reboot resets it: press the screenshot button once)
    ok, ack_ms, st = shot.trigger()
    if not ok: sys.exit(f"screenshot automation NOT armed (status {st}): press the screenshot button once on the console, then rerun (nothing was written)")
    print(f"pre-flight shot ok (ack {ack_ms})", flush=True)
try:
    for w in spec.get("fixed", []): wr(int(w["addr"], 16), w["fmt"], w["val"], nv=w.get("noverify", False))
    if S:
        S.install()
        for k in range(int(spec.get("warmup", 1))):
            for sc in scene_names: out(f"{time.strftime('%H:%M:%S')} host | warm-up {k + 1}: scene {sc} (position error {S.go(sc, scene_wait):.3f} m)")
    for sc in (scene_names or [None]):
        if sc: out(f"{time.strftime('%H:%M:%S')} host | scene {sc} (position error {S.go(sc, scene_wait):.3f} m)")
        for name in seq:
            n += 1
            for w in spec["states"][name]: wr(int(w["addr"], 16), w["fmt"], w["val"], nv=w.get("noverify", False))
            label = f"{sc} :: {name}" if sc else name
            out(f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={cons_ms()} | state {n}/{total} = {label}")
            if use_toast: toast(f"{label} ({n}/{total}) - wait for the notification to disappear, then take a screenshot")
            sd = spec.get("shot_delay")          # seconds after the switch: remote screenshot (needs the patched onionHEN ShellUI payload + shot.py)
            if sd is not None and shot is not None:
                time.sleep(sd); ok, ack_ms, st = shot.trigger()
                out(f"    shot: ok={ok} status={st} ack_epoch_ms={ack_ms}")
                time.sleep(max(0.0, hold - sd))
            else:
                time.sleep(hold)
            bad = []   # did the game overwrite our writes during the hold?
            for w in spec["states"][name]:
                a = int(w["addr"], 16)
                if w.get("noverify"): continue
                if w["fmt"] == "x":
                    want = orig[(a, "x")] if w["val"] == "orig" else bytes.fromhex(w["val"]); got = rd(a, "x", len(want))
                    if got != want: bad.append(f"{a:#x} want {want.hex()} got {got.hex()}")
                    continue
                want = orig[(a, w["fmt"])] if w["val"] == "orig" else w["val"]; got = rd(a, w["fmt"])
                if abs(got - want) > 1e-6: bad.append(f"{a:#x} want {want} got {got}")
            out(f"    persisted after hold: {'YES' if not bad else 'NO -> ' + '; '.join(bad)}")
finally:
    first = [int(x, 16) for x in spec.get("restore_first", [])]           # e.g. a hook's call site, BEFORE its code cave is cleared
    order = [k for a in first for k in orig if k[0] == a] + [k for k in reversed(list(orig)) if k[0] not in first]
    for (a, f) in order:
        v = orig[(a, f)]
        try: wr(a, f, v if f != "x" else v.hex())
        except Exception as e: out(f"RESTORE FAILED {a:#x}: {e}")
    if S:
        try: S.remove(); out("scenes: camera released, pose-lock hook removed")
        except Exception as e: out(f"SCENE CLEANUP FAILED: {e}")
    out(f"{time.strftime('%H:%M:%S')} host | console_epoch_ms={cons_ms()} | RESTORED all")
    if use_toast: toast("A/B done, everything restored")
