# Bloodborne PS5 live-memory dev tools

Research, test and automation tools that were used to build the mods in this repository. They talk to the **running game** (`eboot.bin`, Bloodborne `CUSA03173` v1.09) through the **ps5debug** payload, and to the patched **onionHEN** payload over FTP (remote screenshots, fps sample). Everything is plain Python 3 with no third-party dependencies, except the image/disassembly tools in `analysis/`.

> **Tested only on system software 12.40 with a PS5 Pro.** Behaviour on a base PS5 (or Slim / Digital) and on other firmware versions is **unknown**. All addresses are specific to Bloodborne GOTY `CUSA03173` v1.09. Use at your own risk, on a console and a game copy you own. See [`../../docs/compatibility.md`](../../docs/compatibility.md).

## Layout

| Folder | Contents |
|---|---|
| `core/` | `ps5dbg.py` (ps5debug client), `ps5env.py` (environment / work dir / toast helpers), scene library and CLI (`scenelib.py`, `scene.py`), screenshot automation (`shot.py`, `collect_shots.py`, `onion_sample.py`) |
| `mods-live/` | scripts that **write to the running game**: `ab_loop.py`, `apply_live.py`, `flag.py`, `flag_toggle.py`, `fov_live.py`, `code_patch.py`, `player_warp.py`, `time_freeze.py`, and the code-cave builder `make_cam_pose_cave.py` |
| `camera/` | follow-camera and head-camera tools (control, diagnostics, field finders) |
| `graphics/` | anti-aliasing, anisotropy, LOD, DOF and render-target tools |
| `probes/` | memory probes and structure finders (mostly read-only) |
| `analysis/` | offline tools: screenshot comparison (`analyze_ab.py`, `make_strips.py`, `make_slider.py`) and disassembly helpers over an eboot dump |
| `specs/` | example A/B spec files for `ab_loop.py` |
| `scenes.example.json` | one placeholder scene entry (schema of the file written by `scene.py record`) |
| `notify/` | source of the optional on-screen toast payload (`notify.cpp`, `Makefile`); no binary is shipped |

Scripts in the sub-folders add `core/` and `mods-live/` to `sys.path` relative to their own location, so they can be started from any working directory (`python3 tools/dev/camera/head_cam.py status`).

## Prerequisites

Host machine:

* Python 3.8 or newer. `curl` on the `PATH` for everything that uses FTP (`shot.py`, `collect_shots.py`, `onion_sample.py`, toasts).
* Optional, only for `analysis/`: `numpy`, `Pillow`, `imagecodecs` (decodes the console's JPEG XR screenshots), `capstone` (disassembly helpers). `pip install numpy pillow imagecodecs capstone`.

Console:

* The game running (process name `eboot.bin`; the tools use the last `eboot.bin` in the process list).
* The **ps5debug** payload (TCP 744 by default).
* An FTP server (the dev setup used port 2121) for the FTP-based tools.
* The patched onionHEN from [`../../onionhen/`](../../onionhen/) for `shot.py` / `collect_shots.py` / `onion_sample.py` (remote screenshot trigger and shared fps sample).
* Optional: an ELF loader on port 9021 plus a `notify.elf` built from `notify/` (needs the PS5 payload SDK: `make -C notify`) for on-screen toasts. Without it the toast text is just printed on the host.

## Warning: never leave a debugger attached

`probes/crash_catch.py` attaches the ps5debug debugger to the game. A game that is closed while a debugger is attached is killed by the system (`CRASH KILL`) instead of exiting; the save data stays mounted and the system marks it as broken (`is_broken = 1` in `/system_data/savedata/<userid>/db/user/savedata.db`), after which the game reports "The save data is corrupted". The script now detaches on exit, but always check that no watcher is still running before you close the game, and keep a backup of the save data (`/user/home/<userid>/savedata/<title>/`) before debugging sessions.

## Environment variables

| Variable | Meaning | Default |
|---|---|---|
| `PS5_HOST` | console address (**required**, no default) | - |
| `PS5_DEBUG_PORT` | ps5debug port | `744` |
| `PS5_FTP_PORT` | FTP port on the console | `2121` |
| `PS5_ELFLDR_PORT` | ELF loader port (toast payload only) | `9021` |
| `PS5_WORKDIR` | scratch directory: logs, snapshots (`*.pkl`), `scenes.json`, ... created on demand | `./work` |
| `PS5_NOTIFY_ELF` | path of a built `notify.elf`; enables on-screen toasts (optional) | unset |
| `SCENES` | scenes file used by `scene.py`, `ab_loop.py`, `aa_probe.py` | `$PS5_WORKDIR/scenes.json` |
| `PS5_EBOOT_DUMP`, `PS5_EBOOT_BASE` | flat memory image of the eboot and the virtual address of its first byte (default `0x400000`), only for `analysis/dump_xref.py`, `bb_ann.py`, `bb_ctx.py`, `dump_ctx.py` | - |

```sh
export PS5_HOST=<console ip address>
export PS5_WORKDIR=work              # optional
python3 tools/dev/core/ps5dbg.py     # connectivity check: prints the process list
```

## Typical workflow (A/B image-quality test)

1. Stand at a test spot in the game and record it: `python3 core/scene.py record my_spot "note"` (stores player position, yaw and final camera pose in `$PS5_WORKDIR/scenes.json`; `scenes.example.json` shows the schema). Scenes can only be replayed on the same map.
2. Arm the screenshot automation: press the console's screenshot button **once** after the ShellUI payload has loaded, then check `python3 core/shot.py state`.
3. Write or adapt a spec (see `specs/`) and run it: `python3 mods-live/ab_loop.py my_spec.json`. It writes the states, optionally warps to scenes and shoots screenshots, logs console time, and **restores every touched address at the end**.
4. Fetch and sort the photos: `python3 core/collect_shots.py work/ab_loop.log work/run1`.
5. Compare: `python3 analysis/analyze_ab.py work/run1 --ref "<state>"`, `python3 analysis/make_strips.py ...`, `python3 analysis/make_slider.py --out work/compare --set "Run 1=work/run1"`.

A plain warp never unloads textures, so `ab_loop.py` does warm-up passes over all scenes before the measured pass. Compare only shots from the same run.

## Script reference

Mode: **WRITES** = changes the running game (code caves, hooks, flags, positions) - read the safety notes below first. *read-only* = only reads game memory. *offline* = no console needed. *FTP only* = talks to the console's FTP server, not to game memory. *debugger* = attaches the ps5debug debugger.
Paths are relative to `tools/dev/`; the "usage" column omits the interpreter and the folder.

| Script | Purpose | Mode | Typical usage |
|---|---|---|---|
| `core/ps5dbg.py` | ps5debug client library (process list, maps, read, write, debugger attach); run directly to list the processes | library | `PS5_HOST=<ip> python3 core/ps5dbg.py` |
| `core/ps5env.py` | shared helpers: environment variables, work directory, FTP URLs, optional on-screen toast | library | `from ps5env import workpath` |
| `core/scenelib.py` | scene library: installs the pose-lock / call-service code cave, warps the player, locks the camera pose | **WRITES** (library) | used by scene.py, ab_loop.py and the camera tools |
| `core/scene.py` | record and replay repeatable test scenes (player position + yaw + camera pose) | **WRITES** | `scene.py record spot1`, `scene.py shot spot1`, `scene.py sweep spot1 spot2 --passes 2`, `scene.py list`, `scene.py remove` |
| `core/shot.py` | trigger a remote screenshot through the patched onionHEN ShellUI payload | FTP only | `shot.py state`, `shot.py 3 2` (3 shots, 2 s apart) |
| `core/collect_shots.py` | download the photos of an ab_loop run and sort them by scene and state (writes manifest.json) | FTP only | `collect_shots.py work/ab_loop.log work/run1 --n 40` |
| `core/onion_sample.py` | decode the daemon-to-ShellUI shared sample (fps, game memory, debug line) | FTP only | `onion_sample.py 20 2` |
| `mods-live/ab_loop.py` | generic live A/B loop driven by a JSON spec: holds fixed writes, alternates states, logs console time, optional scenes and screenshots, always restores every touched address | **WRITES** | `ab_loop.py specs/spec_aa_scenes.json` |
| `mods-live/apply_live.py` | write one mod's entries from a cheat JSON into the running game (mode flags off first, hooks after caves, flags last; keeps the head-camera cave's cached holder/slot fields so a re-apply does not force a rescan) | **WRITES** | `apply_live.py ../../cheats/CUSA03173_01.09.json "FPS head camera ("` |
| `mods-live/flag.py` | set the head-camera data flags live (NOCOLL, MODE, FACE2) and print them | **WRITES** | `flag.py MODE=1 FACE2=0` |
| `mods-live/flag_toggle.py` | temporarily set a 1/2/4-byte value, log, and always restore it (optional check qword guards against a moved object) | **WRITES** | `flag_toggle.py <addr_hex> 1 1 10 [<check_addr_hex> <check_qword_hex>] [label]` |
| `mods-live/fov_live.py` | set the wide-FOV multiplier live (rewrites the cave constant of the Wide FOV mod; apply that mod or `specs/spec_fov_scale.json` first) | **WRITES** | `fov_live.py 1.3` |
| `mods-live/code_patch.py` | read or write raw bytes at an address and verify the read-back | **WRITES** (or read) | `code_patch.py <addr_hex> ?3` (read), `code_patch.py <addr_hex> <hex_bytes>` (write) |
| `mods-live/make_cam_pose_cave.py` | builder of the pose-lock / call-service / head-camera / collision-off code caves and hooks (used by scenelib, head_cam, cam_lock); running it only prints sizes | library | `import make_cam_pose_cave as m` |
| `mods-live/player_warp.py` | read the player position or warp / turn the player by writing the physics position | **WRITES** | `player_warp.py read`, `player_warp.py nudge 0 0 2 1.5` |
| `mods-live/time_freeze.py` | freeze game time for N seconds via the fixed time-step field, then restore it | **WRITES** | `time_freeze.py <dt_field_addr_hex> 5` (find the field with find_timestep_obj.py) |
| `camera/head_cam.py` | head-bolted (first-person) camera control: install, on/off, offsets, squeeze hold, body-faces-camera, collision off | **WRITES** | `head_cam.py on --u 0.08 --f 0.15`, `head_cam.py off`, `head_cam.py remove` |
| `camera/cam_lock.py` | camera pose lock: record the current pose, lock to it (optionally orbited/spun), unlock, remove | **WRITES** | `cam_lock.py install`, `cam_lock.py lock --yaw 0.6`, `cam_lock.py remove` |
| `camera/cam_pose.py` | set the follow camera's orientation by writing its direction matrix (turn / absolute / read) | **WRITES** | `cam_pose.py read`, `cam_pose.py turn 0.5 0 2` |
| `camera/face_cam.py` | proof of concept: make the player's body face the camera direction every frame | **WRITES** | `face_cam.py 10` |
| `camera/cam_persist.py` | nudge every follow-camera float by 0.1 % and report which fields persist (inputs) or revert (computed per frame); restores them | **WRITES** (restores) | `cam_persist.py` |
| `camera/cam_chase_log.py` | head camera on; switch the follow-camera chase fields in 4 s blocks and log how the view yaw turns (circle with the left stick) | **WRITES** (restores) | `cam_chase_log.py` |
| `camera/cam_mode_log.py` | compare head-camera sub-features (collision, squeeze hold) in blocks while the right stick is wiggled; counts pitch jumps | **WRITES** (restores) | `cam_mode_log.py` |
| `camera/cam_pad_log.py` | right-stick pitch-flip ('tornado') diagnosis with the head camera on: logs rows, game camera direction and the pad fields | **WRITES** | `cam_pad_log.py 8` |
| `camera/cam_spin_log.py` | log the camera yaw rate while walking, toggling the head camera in 4 s blocks | **WRITES** | `cam_spin_log.py 4 4` |
| `camera/cam_tornado_log.py` | log game-camera distance, squeeze-hold state and view rates while the 'tornado' is provoked | **WRITES** (installs the cave) | `cam_tornado_log.py 12` |
| `camera/cam_diff.py` | find the camera yaw/pitch state fields by correlating float windows while you turn the camera | read-only | `cam_diff.py 15` |
| `camera/cam_snap.py` | wide object-graph snapshots of the camera (save / diff) to find the camera angle state | read-only | `cam_snap.py save work/a.pkl`, `cam_snap.py diff work/a.pkl work/b.pkl` |
| `camera/cam_quat.py` | search two cam_snap snapshots for an orientation stored as a quaternion | offline | `cam_quat.py work/a.pkl work/b.pkl` |
| `camera/find_cam_angles.py` | derive yaw/pitch from the camera rows and search the camera objects for matching floats or sin/cos pairs | read-only | `find_cam_angles.py` |
| `camera/read_cam.py` | raw dump of the camera manager's sub-objects (follow cam, aim cam, ...) | read-only | `read_cam.py` |
| `camera/dump_cam_params.py` | dump the LOCK_CAM_PARAM_ST rows (also written to work/cam_rows.json) | read-only | `dump_cam_params.py` |
| `camera/hc_state.py` | verify the live head-camera hooks, data block and pointer chain against the cheat JSON | read-only | `hc_state.py [cheat.json]` |
| `camera/head_axes.py` | which local axes of the head bone point forward/up in world space | read-only | `head_axes.py` |
| `camera/head_look_log.py` | does the head bone's look direction follow the camera (right stick) or the body? | read-only | `head_look_log.py 8` |
| `graphics/aa_loop.py` | alternate the forced-AA code patch OFF/ON in the live game and log every switch with console time | **WRITES** | `aa_loop.py 3 10` |
| `graphics/aa_probe.py` | read the game-side AA pass (DLAA/FXAA fields) in each recorded scene | read-only (+ scene warps) | `aa_probe.py scene_a scene_b` |
| `graphics/aniso_loop.py` | alternate MaxAnisotropy of the engine samplers in the live game (toast + log per switch); leaves the last state set | **WRITES** | `aniso_loop.py 4,16,4,16 10` |
| `graphics/sampler_loop.py` | same for sampler fields: `aniso` (MaxAnisotropy) or `bias` (mip LOD bias); leaves the last state set | **WRITES** | `sampler_loop.py bias 0,-0.75,0,-0.75 10` |
| `graphics/gfx_inspect.py` | snapshot of the graphics state: resolution globals, SprjGraphics, render-target table, memory map | read-only | `gfx_inspect.py > work/gfx.txt` |
| `graphics/scan_rt.py` | find engine texture descriptors of a given size and show how much of their GPU surface holds data | read-only | `scan_rt.py 1920 1080` |
| `graphics/yebis_probe.py` | read the YEBIS post-effect context: AA / temporal AA enables and parameters | read-only | `yebis_probe.py` |
| `graphics/read_dof.py` | read the depth-of-field parameter block with field names | read-only | `read_dof.py` |
| `graphics/read_lod.py` | walk LodBankMan to its parameter blob and print the header and sample rows | read-only | `read_lod.py` |
| `graphics/dump_lod_rows.py` | dump the LOD parameter rows (also written to work/lod_rows.json) | read-only | `dump_lod_rows.py` |
| `analysis/analyze_ab.py` | per scene and state sharpness metrics and pairwise differences (noise floors, shift) of a collect_shots output directory | offline (numpy, Pillow, imagecodecs) | `analyze_ab.py work/run1 --ref "AA off"` |
| `analysis/make_strips.py` | one image cut into vertical strips / horizontal bands, each from a different state of the same scene | offline (numpy, Pillow, imagecodecs) | `make_strips.py work/run1 scene_a "AA off" "FXAA"` |
| `analysis/make_slider.py` | interactive HTML comparison page (slider, strips, blink, difference) from collect_shots directories | offline (numpy, Pillow, imagecodecs) | `make_slider.py --out work/compare --set "Run 1=work/run1"` |
| `analysis/bb_ann.py` | annotated linear disassembly of a flat eboot memory dump (strings, rip-relative targets) | offline (capstone, numpy) | `PS5_EBOOT_DUMP=eboot.bin python3 bb_ann.py 183ac60 183ad00` |
| `analysis/bb_ctx.py` | disassembly around an instruction address (resynchronises the decode start) | offline (capstone, numpy) | `bb_ctx.py 183af56` |
| `analysis/dump_ctx.py` | annotated disassembly around addresses, marks the render-resolution globals | offline (capstone, numpy) | `dump_ctx.py 183af56` |
| `analysis/dump_xref.py` | library: xref / string / function-start helpers over the eboot dump (imported by bb_ann, bb_ctx, dump_ctx) | library (capstone, numpy) | `from dump_xref import *` |
| `probes/read_player.py` | WorldChrMan and player ChrIns: vtable, model mask, dirty byte | read-only | `read_player.py` |
| `probes/read_entity.py` | the player's draw entity: flags (draw bit) and first fields | read-only | `read_entity.py` |
| `probes/dump_entity.py` | draw-entity manager blocks and a raw dump of the first entities | read-only | `dump_entity.py` |
| `probes/dump_mod58.py` | raw dump of the player's module container ([pl+0x58], model-to-world rows) | read-only | `dump_mod58.py` |
| `probes/dump_model.py` | raw dump of [pl+0x48] and the model object behind it | read-only | `dump_model.py` |
| `probes/elem_dump.py` | raw dump of the body-position array elements (stride 0xa0) and holder header | read-only | `elem_dump.py` |
| `probes/scan_entities.py` | list the draw entities by name with flags and positions | read-only | `scan_entities.py` |
| `probes/find_entities.py` | locate the draw entities that belong to the player's model objects | read-only | `find_entities.py` |
| `probes/find_player_pos.py` | scan ChrIns (and one pointer level below) for float triples near the camera position | read-only | `find_player_pos.py 8` |
| `probes/find_player_yaw.py` | find other copies of the player's facing (yaw, sin/cos pairs) | read-only | `find_player_yaw.py` |
| `probes/find_head_bone.py` | BFS the player object graph for float triples at head height; saves work/head_hits.pkl | read-only | `find_head_bone.py 1.2 2.0` |
| `probes/find_bone_array.py` | find arrays of (x,y,z,1) bone world positions at a constant stride | read-only | `find_bone_array.py` |
| `probes/find_qs_pose.py` | find hkQsTransform pose arrays (translation, quaternion, scale; stride 0x30) | read-only | `find_qs_pose.py` |
| `probes/find_arrays_bfs.py` | BFS for world pose arrays (orthonormal 3x4 rows) near the model origin | read-only | `find_arrays_bfs.py` |
| `probes/head_chain.py` | pointer path from the player ChrIns to a body-position array, checked for stability | read-only | `head_chain.py <element0_addr_hex>` |
| `probes/find_timestep_obj.py` | find the fixed time-step object by its 1/60 s float constant | read-only | `find_timestep_obj.py` |
| `probes/find_vtable_instances.py` | list the heap instances of a vtable | read-only | `find_vtable_instances.py 0x56e7980` |
| `probes/player_chain.py` | follow the game's own player-warp read chain and print the position copies | read-only | `player_chain.py` |
| `probes/origin_state.py` | model origin, physics position and where else the position is stored | read-only | `origin_state.py` |
| `probes/respawn_state.py` | check hooks, data block, vtables and pose-array slots after a respawn | read-only | `respawn_state.py` |
| `probes/obj_layout.py` | layout of the model object: pointer slots, vtables, pose-array tests | read-only | `obj_layout.py` |
| `probes/holders.py` | which holder objects own pose arrays | read-only | `holders.py` |
| `probes/bone_probe.py` | bones of a pose array by height and motion (array address required) | read-only | `bone_probe.py <array_addr_hex>` |
| `probes/arr_state.py` | pose-array slots: non-zero and moving bones, bone 68 relative to the player | read-only | `arr_state.py` |
| `probes/lag_probe.py` | compare pose copies while running to find the newer copy and its lag in ms | read-only | `lag_probe.py` (then run around) |
| `probes/cadence_probe.py` | update cadence of every plausible pose slot (60 Hz vs 30 Hz copy) | read-only | `cadence_probe.py` (then run) |
| `probes/cadence2.py` | update cadence of model origin, physics position and game camera position | read-only | `cadence2.py` (then run) |
| `probes/bob_probe.py` | walking-bob peak-to-peak of head bone, smoothed offset and final camera | read-only | `bob_probe.py` (then walk straight for 20 s) |
| `probes/roll_probe.py` | sample head-origin geometry for 80 s and report which cave plausibility check would fail | read-only | `roll_probe.py` |
| `probes/plaus.py` | plausibility of the head origin per pose slot | read-only | `plaus.py` |
| `probes/lockon_probe.py` | sample the follow camera for 45 s to find the lock-on flag and look-at target | read-only | `lockon_probe.py` (lock on / release in 10 s phases) |
| `probes/lock_snapA.py` | lock-on series stage 1 (locked on): BFS snapshot of the player/camera graph to work/lockA.pkl | read-only | `lock_snapA.py` |
| `probes/lock_diff2.py` | stage 2 (released): changed pointer fields whose pointee looks like a ChrIns within 40 m | read-only (needs lockA.pkl) | `lock_diff2.py` |
| `probes/lock_diff3.py` | stage 2: changed small-integer / flag dwords versus lockA.pkl | read-only (needs lockA.pkl) | `lock_diff3.py` |
| `probes/lock_mgr_dump.py` | dump the camera manager entries from lockA.pkl | offline | `lock_mgr_dump.py` |
| `probes/find_target_ptr.py` | find references to the lock-on target pointer inside lockA.pkl | offline | `find_target_ptr.py` |
| `probes/rows_check.py` | orthonormality check of the manager's camera rows in lockA.pkl | offline | `rows_check.py` |
| `probes/lock_target3.py` | BFS from WorldChrMan listing ChrIns-like objects by distance to the view ray and to the player | read-only | `lock_target3.py` |
| `probes/lock_target_probe.py` | static snapshot while locked on: ChrIns-like objects and float triples near the view ray | read-only | `lock_target_probe.py` |
| `probes/stick_fields.py` | find float fields that react to the right / left stick | read-only | `stick_fields.py` (circle the right stick, then the left) |
| `probes/stick_scan.py` | map the left-stick values: 5 snapshots (idle, forward, back, left, right) with toast cues | read-only | `stick_scan.py 6` |
| `probes/list_params.py` | list the parameter tables of the SoloParamRepository (name, rows, blob address) | read-only | `list_params.py` |
| `probes/crash_catch.py` | wait for the game, attach the debugger (console connects back on TCP 755), log every stop; on a fatal signal print registers and context and leave the process stopped | debugger | `crash_catch.py` |

## Specs and scenes

`specs/*.json` are examples for `ab_loop.py`:

```json
{"hold": 20, "sequence": ["A", "B", "A", "B"],
 "fixed":  [{"addr": "vt:0x57b9080+0x5c6", "fmt": "B", "val": 1}],
 "states": {"A": [{"addr": "0x25d8034", "fmt": "x", "val": "0f95c0"}],
            "B": [{"addr": "0x25d8034", "fmt": "x", "val": "b00190"}]},
 "scenes": ["bridge_end_cobblestone"], "shot_delay": 2, "warmup": 1, "scene_wait": 5, "toast": false}
```

* `addr` is an absolute address, `vt:<vtable>+<offset>` (the single heap object with that vtable; survives game restarts) or `vtall:<vtable>+<offset>` (one write per live instance). `fmt`: `B` `H` `I` `f` or `x` (hex bytes, one atomic write: use it for code patches). `val` may be `"orig"` (the value read before the run). `check: [addr, qword]` must match before anything is written; `noverify: true` skips the read-back; `restore_first` lists addresses to restore first (call sites before code caves).
* The scene names used in the specs (`bridge_end_cobblestone`, `under_bridge_brick_wall`, `sickroom_fences_aa`, `ladder_top_horizon`) are **not shipped**: record your own scenes with `scene.py record` and edit the `scenes` list. The recorded positions are not included.
* Four specs (`spec_aa_falloff_scenes`, `spec_taa_scenes`, `spec_taa_weight_scenes`, `spec_aniso_scenes`) contain heap addresses from one game session (see their `note` field): re-resolve them (for example from `graphics/yebis_probe.py` output) before use.

## Safety notes

* **Scripts marked WRITES change the running game.** Tell whoever is playing before you start: the camera can jump, the player is warped, effects flip on and off, and a bad write can crash the game. A crash dialog on the console must be dismissed; leaving it open can make the console shut itself down.
* **Never toggle enemy-AI cheats or flags at runtime** (not through `ab_loop.py` specs, `flag_toggle.py`, `apply_live.py` or `code_patch.py`): it can crash the game or corrupt its state. Apply such cheats before the game starts.
* **Keep a backup of your save data** before using any WRITES script, and play offline while memory is modified.
* `ab_loop.py`, `flag_toggle.py` and `time_freeze.py` restore what they changed in a `finally` block, but a killed process (Ctrl-C twice, lost connection) can leave values changed: re-run with the original value, or restart the game. Scripts that install code caves (`scene.py`, `head_cam.py`, `cam_lock.py`, the camera logs, `aa_probe.py`) must be cleaned up with their `remove` command (or `scene.py remove`) before you stop.
* Addresses and structure offsets are valid only for `CUSA03173` v1.09. On another build they point at unrelated memory and writing there can crash the game.
* ps5debug has no authentication: use it only on a trusted network. `probes/crash_catch.py` opens a listening socket on TCP 755 on all interfaces while it runs.
* `$PS5_WORKDIR` collects memory snapshots (`*.pkl`), screenshots and logs. They are working data: do not publish or commit them (`.gitignore` in this folder excludes `work/`).

## What is not included

* No eboot dump or any other game data: `analysis/` expects you to provide a flat memory image of the eboot (`PS5_EBOOT_DUMP`); no dumper is shipped.
* No payload binaries (ps5debug, onionHEN, `notify.elf`); `notify/` is source only.
* The research scripts for the abandoned hood-view camera, resolution / supersampling experiments and texture-creation diagnostics are not part of this folder.
