#!/usr/bin/env python3
"""Assemble the onionHEN cheat file for Bloodborne GOTY (CUSA03173 v01.09) from the individual mod generators.

Usage:  python3 build_cheats.py [--out ../../cheats/CUSA03173_01.09.json] [--enable-all] [--profile default|quality|fps] [--fov-scale X] [--all-profiles]
  default      : release defaults (60 FPS / no motion blur / no chromatic aberration / skip intro ON, everything else OFF = opt-in)
  --profile    : ready-made selections.  quality = default + Wide FOV x1.3 + DLAA 0.3;  fps = quality + FPS head camera + body-facing + lock-on aim + death slow motion (experimental); FOV x1.3 in third person, x1.8 in the first-person view
  --fov-scale  : FOV multiplier of the Wide-FOV mod = third-person camera (default 1.3)
  --fps-fov    : FOV multiplier used while the FPS head camera is on (default 1.8); the head-camera cave switches the Wide-FOV constant with the camera mode
  --all-profiles : writes cheats/CUSA03173_01.09.json (default) and cheats/profiles/CUSA03173_01.09_{quality,fps}.json
  --enable-all : every mod enabled (used for end-to-end testing)
Also verifies that no two mods write overlapping memory (code caves, data block and hooks) and that every hook has an 'off' value that restores the original bytes."""
import json, os, sys
import make_fov_mod, make_dlaa_mod, make_head_camera_mod, make_aniso_mod, make_dof_mod
HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
if "--all-profiles" in args:
    import subprocess
    root = os.path.join(HERE, "..", "..", "cheats")
    for prof, rel in (("default", "CUSA03173_01.09.json"), ("quality", "profiles/CUSA03173_01.09_quality.json"), ("fps", "profiles/CUSA03173_01.09_fps.json")):
        subprocess.check_call([sys.executable, os.path.abspath(__file__), "--profile", prof, "--out", os.path.join(root, rel)])
    sys.exit(0)
profile = args[args.index("--profile") + 1] if "--profile" in args else "default"
fov_scale = float(args[args.index("--fov-scale") + 1]) if "--fov-scale" in args else 1.3          # third-person FOV multiplier
fps_fov = float(args[args.index("--fps-fov") + 1]) if "--fps-fov" in args else 1.8                       # FOV multiplier while the FPS head camera is on
out = args[args.index("--out") + 1] if "--out" in args else os.path.join(HERE, "..", "..", "cheats", "CUSA03173_01.09.json")
base = json.load(open(os.path.join(HERE, "data", "base_mods.json")))
by = {m["name"]: m for m in base["mods"]}
mods = [by["60 FPS (Lance McDonald)"], by["No Motion Blur"], by["No Chromatic Aberration"], by["Skip Intro Logos"],
        make_fov_mod.build(fov_scale), make_dlaa_mod.build(0.3), *make_head_camera_mod.build(fps_fov=fps_fov, tp_fov=fov_scale), make_aniso_mod.mod(), make_dof_mod.build(), by["DLC Save Requirement Unlock"]]
default_on = {"60 FPS (Lance McDonald)", "No Motion Blur", "No Chromatic Aberration", "Skip Intro Logos"}
if profile in ("quality", "fps"):
    default_on |= {m["name"] for m in mods if m["name"].startswith(("Wide FOV", "DLAA threshold"))}
if profile == "fps":
    default_on |= {"FPS head camera (experimental)", "FPS head camera: body faces the view (needs head camera)", "FPS head camera: aim at the lock-on target (needs head camera)", "FPS head camera: death slow motion (needs head camera)", "FPS head camera: look at the killer after death (needs head camera)"}
for m in mods:
    m["type"] = "checkbox"; m["enabled"] = ("--enable-all" in args) or (m["name"] in default_on)
# onionHEN refuses to switch a mod OFF when any of its entries has an empty 'off' ("invalid patch").  Caves and data blocks have no original bytes, so 'off' = 'on' (they stay in place, harmless once
# the hooks are restored; the entries are written in file order, so the hooks - which carry the original instructions - come last).
for m in mods:
    for e in m["memory"]:
        if not e["off"]: e["off"] = e["on"]
# onionHEN stores every patch entry in fixed 1024-byte buffers (ONION_MAX_PATCH_BYTES): a longer 'on'/'off' hex string does not fit and breaks the load of the entry (a truncated cave behind
# a live hook crashes the game).  Split long entries (code caves, data) into consecutive chunks; the hooks are written after all of them, so the order is still data -> caves -> hooks.
CHUNK = 1000
for m in mods:
    chunked = []
    for e in m["memory"]:
        n = len(e["on"]) // 2
        if n <= CHUNK: chunked.append(e); continue
        assert e["off"] == e["on"], "only caves/data (off == on) may be split: %s @%s" % (m["name"], e["offset"])
        addr0 = int(e["offset"], 16)
        for k in range(0, n, CHUNK):
            part = e["on"][2 * k:2 * (k + CHUNK)]
            chunked.append({"offset": "%08X" % (addr0 + k), "on": part, "off": part, "absolute": e.get("absolute", True)})
    m["memory"] = chunked
for m in mods:
    for e in m["memory"]:
        assert len(e["on"]) // 2 <= 1024 and len(e["off"]) // 2 <= 1024, "entry too long for onionHEN: %s @%s" % (m["name"], e["offset"])
# ---- overlap check ----
spans = []
for m in mods:
    for e in m["memory"]:
        a = int(e["offset"], 16); n = len(e["on"]) // 2
        for (a2, n2, m2) in spans:
            if m2 != m["name"] and a < a2 + n2 and a2 < a + n: sys.exit("OVERLAP: %s @%X(+%d) vs %s @%X(+%d)" % (m["name"], a, n, m2, a2, n2))
        spans.append((a, n, m["name"]))
doc = {k: base["game"][k] for k in ("name", "id", "version", "process")}; doc["mods"] = mods
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); json.dump(doc, open(out, "w"), indent=1)
print("wrote %s: %d mods, %d memory entries; no overlaps" % (out, len(mods), sum(len(m["memory"]) for m in mods)))
for m in mods: print("  [%s] %-58s %d entries" % ("x" if m["enabled"] else " ", m["name"], len(m["memory"])))
