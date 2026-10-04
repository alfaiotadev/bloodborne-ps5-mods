#!/usr/bin/env python3
"""Repeatable test scenes for Bloodborne (needs tools/dev/core: ps5dbg.py, scenelib.py, shot.py; and mods-live/make_cam_pose_cave.py).
A scene = player world position + yaw + the final camera pose. Replay: lock the camera to the stored absolute pose (pose-lock cave), game-warp the player, wait, optionally shoot.
  scene.py record <name> [note...]     store the CURRENT player position, yaw and camera pose (file: $SCENES or $PS5_WORKDIR/scenes.json)
  scene.py goto <name> [--wait 5.0]    lock camera, warp player (same map only), wait; camera stays locked          (--keep-yaw: keep current facing)
  scene.py shot <name> [--wait 5.0]    goto + remote screenshot + release the camera                                  (--keep: stay locked)
  scene.py sweep <scene...> [--passes N] [--warmup W] [--wait 5.0] [--log f.jsonl]   W warm-up passes (no shots) then N measured passes with a shot per scene
  scene.py settle <name> [t1 t2 ...]   warp, then a shot at each given second after the warp (texture-streaming settle measurement)
  scene.py nowarp | release | list | install | remove
A plain warp never unloads textures (the elevator does): a warm-up pass makes the texture state repeatable. Compare only shots from the same visit/run."""
import sys, os, struct, json, math, time
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5env import workpath
FILE = os.environ.get("SCENES", workpath("scenes.json"))
a = sys.argv[1:]; cmd = a[0] if a else "list"
val = lambda k, dflt: float(a[a.index(k) + 1]) if k in a else dflt
db = json.load(open(FILE)) if os.path.exists(FILE) else {}
if cmd == "list":
    for k, v in db.items(): print("%-26s map %#x  player %s  yaw %.3f   %s" % (k, v["map"], ["%.2f" % x for x in v["player_pos"]], v["player_yaw"], v.get("note", "")))
    sys.exit()
from ps5dbg import Dbg
import scenelib, make_cam_pose_cave as m
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
S = scenelib.Scenes(d, pid, db); rd = S.rd
wait = val("--wait", 5.0)
if cmd == "record":
    pl, X, cam = S.chain(); name = a[1]
    db[name] = {"map": struct.unpack("<I", rd(pl + 0x3f8, 4))[0], "player_pos": list(struct.unpack("<3f", rd(X + 0x1e0, 12))),
                "player_yaw": struct.unpack("<f", rd(X + 0x1d4, 4))[0], "cam": rd(cam + 0x10, 0x40).hex(), "note": " ".join(a[2:]),
                "recorded": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(db, open(FILE, "w"), indent=1); print("recorded", name, "->", FILE, db[name]["player_pos"], "yaw %.3f" % db[name]["player_yaw"])
elif cmd in ("goto", "shot"):
    err = S.go(a[1], wait, "--keep-yaw" in a); print("at scene %s (err %.3f m)" % (a[1], err))
    if cmd == "shot":
        import shot
        ok, ms, st = shot.trigger(); print("shot ok=%s status=%d ack_epoch_ms=%d" % (ok, st, ms))
        if "--keep" not in a: time.sleep(0.5); S.release(); print("camera released")
elif cmd == "sweep":
    import shot
    names = [x for x in a[1:] if x in db]; passes = int(val("--passes", 1)); warm = int(val("--warmup", 1)); log = a[a.index("--log") + 1] if "--log" in a else None
    for w in range(warm):
        for n in names: print("warm-up %d/%d %s err %.3f m" % (w + 1, warm, n, S.go(n, wait)), flush=True)
    for p in range(passes):
        for n in names:
            err = S.go(n, wait); ok, ms, st = shot.trigger(); row = {"pass": p + 1, "scene": n, "err_m": round(err, 3), "ok": ok, "status": st, "ack_epoch_ms": ms}
            print(json.dumps(row), flush=True)
            if log: open(log, "a").write(json.dumps(row) + "\n")
    S.release(); print("camera released")
elif cmd == "settle":
    import shot
    n = a[1]; times = [float(x) for x in a[2:]] or [1, 2, 3, 5, 8, 12]; S.go(n, 0.0); t0 = time.time()
    for t in times:
        time.sleep(max(0, t0 + t - time.time())); t1 = time.time() - t0; ok, ms, st = shot.trigger(); print("t=%5.1fs (trigger at %.2fs) ok=%s ack=%d" % (t, t1, ok, ms), flush=True)
    S.release()
elif cmd == "nowarp":                                   # harmless test: game warp to the CURRENT position and yaw
    pl, X, cam = S.chain(); p = struct.unpack("<3f", rd(X + 0x1e0, 12)); S.install(); print("call returned", hex(S.warp(p)))
elif cmd == "release": S.release(); print("camera released")
elif cmd == "install": S.install(); print("installed")
elif cmd == "remove": S.remove(); print("removed")
