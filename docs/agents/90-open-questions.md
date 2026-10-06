# 90 - Open questions and next steps

> All results so far are from **firmware 12.40 and a PS5 Pro**, game `CUSA03173` v01.09. Every "unknown" below is genuinely unknown, not "probably fine". Each item has a **first probe** an agent can run. Safety rules apply to all of them ([../../AGENTS.md](../../AGENTS.md)): warn the user before visible console actions, back up the cheat file and the save, never toggle AI/enemy cheats at runtime, never print tokens.

Conventions: `$PS5_HOST` is the console address; paths are repo-relative; `tools/dev` scripts read `PS5_HOST` (see [20](20-tooling.md)). Replace `<unpatched dump>` with a dump you made yourself ([20](20-tooling.md) section 6).

## A. Repository inconsistencies to resolve first (cheap, high value)

| # | Problem | Evidence | First probe / fix |
|---|---|---|---|
| A1 | **Verify on hardware that the chunked manager cave (three entries, 1000 + 1000 + 391 B) applies completely from a cold start** (the earlier two-entry build did; the death-camera build was only applied to a running game so far). The 1024-byte entry cap (`ONION_MAX_PATCH_BYTES`) was the likely cause of a cold-start crash with the unchunked cave | [70](70-onionhen-cheat-engine.md) hazard 1 | restart the game with the fps profile, load a save, then `python3 tools/dev/camera/hc_state.py cheats/profiles/CUSA03173_01.09_fps.json` (reports mismatching entries) |
| A2 | `onionhen-bloodborne.patch` has no new-file sections, but calls `daemon_probes_init()` defined in files that are untracked in the lab tree (`daemon_probes.cpp`, `debug_probes.hpp`) | `grep -c "new file" onionhen/onionhen-bloodborne.patch` -> 0 | `git apply --check` on a clean `b23ffe6` checkout, build; regenerate the patch with the two files included |
| A3 | README/`install.md` say stock onionHEN suffices; the patch shows that `enabled`, exec-time auto-apply and the non-destructive cave mapping are not in stock | [70](70-onionhen-cheat-engine.md) section 7 | test the default profile on stock onionHEN with klog open (`nc $PS5_HOST 3232`): are any mods applied at launch? Fix the wording either way |
| A4 | `docs/features.md` says every mod can be toggled in the menu. Cave/data entries used to have empty `off`, which onionHEN rejects when switching off; `build_cheats.py` now sets `off = on` (mitigation derived from the source, **untested on hardware**) | `cheat_applier.cpp` (`off_len == 0` -> invalid patch); `build_cheats.py` | toggle each mod off and on in the menu with klog open (`nc $PS5_HOST 3232`); confirm hooks are restored (`code_patch.py 1836C54 ?5` must read the original `c5 f8 29 5b 40`) and the mod can be re-enabled |
| A5 | Lab tools (`scene.py`, `scenelib.py`, `head_cam.py`, `cam_lock.py`, `ab_loop.py` with `scenes`) share hooks, caves and the data block with the release head camera | [10](10-memory-map.md) section 1 | move the lab caves to other addresses (for example `0x54A2000+`) and the lab data block, or add a guard that refuses to install when the release hooks are present |
| A6 | Docstrings of `verify_against_dump.py` and `fill_off_from_dump.py` point to `docs/agents/02-tooling.md` | | a redirect stub exists; fix the docstrings to `20-tooling.md` |
| A7 | `make_head_camera_mod.py` docstring still says "two mods", `ARROFF 0x430`, and does not mention the touchpad toggle fields | generator vs docstring | update the docstring (the code returns three mods, initial `ARROFF` is `0x320`) |
| A8 | `CREDITS.md` credits Lance McDonald for the 60 FPS list; the lab notes also mention a community PS4/PS5 game-patch XML for `CUSA03173` as the immediate source of the 128 entries | lab notes | ask the maintainer to add the correct attribution |
| A9 | Cave-owned state in the head camera data block (`ARROFF`, `COOL`, `HOLD`) must never be part of a cheat entry (re-applying or toggling would reset it and force a scan) | `make_head_camera_mod.py` `build()` writes the tunables in three pieces | keep this rule when adding runtime-state fields to the block; `apply_live.py` relies on it |

## B. Verification gaps in shipped features

### B1. Touchpad double-click toggle of the head camera (new in the generator)

* Why: the lab notes said the pad bitmask was not found; the generator now reads the DualSense report ring through a libScePad import slot. No live-verification record exists in the notes available here.
* First probe: use a profile with the head camera enabled, launch, load a save, then read the state block while double-clicking the touchpad:

```bash
python3 tools/dev/mods-live/code_patch.py 57E5B30 ?8      # libScePad function address (high dword should be 0x8)
python3 tools/dev/mods-live/code_patch.py 54A0E70 ?16     # NOCOLL MODE AIM FACE2 | +5 PADTOG +6 PADPREV | +8 FRAME | +12 PADLAST
# double-click the touchpad, read again: MODE (byte 1) must flip; FRAME must keep increasing
```

* Done when: toggle works, no false triggers during normal play (the game's own touchpad use), behaviour documented including the effect on the game's menu opened by the touchpad. Failure modes to check: the libScePad prologue check rejects the layout (FRAME stays 0), different firmware layout, ring offset wrong.

### B2. FACE2 from a cold start

* Why: the final guarded code (cos^2+sin^2 >= 0.5, strict pointer checks) was never cold-start tested; the earlier version may have contributed to load crashes. The mod hides coat/hood cloth.
* First probe: copy `cheats/profiles/CUSA03173_01.09_fps.json`, set `"enabled": true` on "FPS head camera: body faces the view", upload (backing up the old file), launch the game with `python3 tools/dev/probes/crash_catch.py` running as root, then run the stress list in [30](30-code-cave-playbook.md) section 8.
* Done when: three clean cold starts with load/death/teleport, then update the docs and the known-issues text.

### B3. Wide FOV and the head camera together (profile `fps`, FOV x1.8)

* First probe: look at the FOV in the head camera view with weapons drawn, rolls, ladders; measure with `fov_live.py 1.3` versus `1.5` and decide the default; check for stretched weapons at the edges.

### B4. Long-session stability of 60 FPS and the mods

* Listed as open since the first successful run: elevators, cloth, blood, loads, a late boss, long sessions. A cutscene of a DLC boss (Laurence) is reported to soft-lock at 60 FPS (a property of the patch).
* First probe: play a defined route with the overlay running and `python3 tools/dev/core/onion_sample.py 600 2 > fps.log` in parallel (fps, game memory, DBG line); note every stutter/hang with the klog.

### B5. DLC Save Requirement Unlock

* Entry `0x23B67B3` comes from a community cheat file; no maintainer test is recorded. First probe: enable on a save that requires the DLC, with a save backup.

## C. Platform coverage (all unknown)

### C1. Base PS5 / Slim / Digital

* Question: do the 60 FPS patch, the head camera and the AA mods behave and perform the same?
* Protocol for a tester: install the default profile and the `quality` profile; record the overlay FPS/CPU/GPU values in the same two scenes on each console; run `onion_sample.py` for 10 minutes; report with the issue template `.github/ISSUE_TEMPLATE/base_ps5_report.yml` (firmware, model, game version, enabled mods, crash dialogs, klog excerpt).
* First probe on the new console (read-only): `python3 tools/dev/core/ps5dbg.py` (is `eboot.bin` listed?), then `python3 tools/mods/verify_against_dump.py cheats/CUSA03173_01.09.json <dump from that console>` (addresses identical?).
* Do **not** state any base-PS5 conclusion without such a report.

### C2. Other firmware

* The patches are address-based and should not depend on firmware, but the chain (kstuff-lite, onionHEN's kdirect backend for firmware >= 8.40, ps5debug-NG, the screenshot hook's ShellUI internals, the libScePad layout used by the touchpad toggle) may differ.
* First probe: read-only tools first (`core/ps5dbg.py`, `code_patch.py <addr> ?8`), then a single non-visible mod (No Motion Blur) before the camera caves; keep klog open.

### C3. Other game versions and regions

* Question: is `CUSA00207` (original release) 1.09 the same binary as `CUSA03173` 1.09? The 60 FPS list comes from the original release's patcher and matched the GOTY except for one write that assumes the next original byte; the update's param.sfo suggests the same build machine. Unknown.
* First probe: dump the other title (unpatched), then `python3 tools/mods/verify_against_dump.py cheats/CUSA03173_01.09.json other_dump.bin` (each MISMATCH is an address that moved) and a byte-wise diff of the two dumps restricted to code (`0x400000..`).
* Porting recipe if they differ: for each anchor in [10](10-memory-map.md) section 7 take the `off` bytes plus 16-32 bytes of context and search the new dump; re-derive globals from the code that uses them (WorldChrMan `0x593E878`, camera root `0x593E860`, SprjGraphics `0x59406C8`); re-find vtables by instance scanning and compare layouts with `probes/read_player.py`, `obj_layout.py`, `hc_state.py`; re-validate structures one by one.

### C4. Performance data

* Only overlay FPS was collected. No frame-time distribution, no GPU/CPU load, no power/thermal data. First probe: sample `fps_sample` at 2 Hz during a fixed route and compute percentiles; the overlay CPU meter (`SceIdleCpu` method) is usable, the GPU % is hidden (no load source known).

## D. Camera and gameplay features

| # | Idea | First probe |
|---|---|---|
| D1 | **Lock-on aim profiles** (aim at chest/head, soft assist, per-boss offsets) | tune `BETA`, `AIMCOS`, `AIMMIN2/AIMMAX2` live (`code_patch.py 54A0EA0 <floats>`), read the lock point `mgr+0x120` / local `mgr+0x180`, record with a scene; add parameters to `build()` |
| D2 | Third-person **camera distance multiplier** | hook `0x183AE68` (see the lab "hood view" cave for the 5-byte hook + re-emitted next instruction); or edit `LOCK_CAM_PARAM_ST` `f0` rows after boot (`probes/list_params.py`, `camera/dump_cam_params.py`) |
| D3 | FPS for aim cameras / telescope | dump `mgr+0x68`, `mgr+0x78` live (`camera/read_cam.py`) while aiming; fields `ZoomInFovY/ZoomOutFovY`, `ZoomIn/OutOrg` |
| D4 | Silhouette-spin damping when backpedalling | log body yaw `R2` vs camera yaw around the event |
| D5 | Idle-animation / roll sway damping in FPS | find the player's animation time scale; first read-only: `probes/arr_state.py`, `probes/bob_probe.py` |
| D6 | Properly hide the player's head/hood | test clearing bit 14 of the draw entity flags (`+0x1FC`) via `mods-live/flag_toggle.py` (restores) |
| D7 | Cutscene detection to leave FPS automatically | difference a flag before/after a cutscene (`probes/lock_snapA.py`/`lock_diff*.py` method) |
| D8 | Player/enemy scale multipliers (fun mod) | `probes/read_entity.py`, `scan_entities.py`: look for a scale in the 0x2E0-byte draw entity; try a live write |
| D9 | Other toggle chords (long press, touchpad + button) | extend the pad block in the manager cave (all buttons are in the ring; add a second edge detector); or find the left-stick/axes in the report |
| D10 | Safe enemy-AI freeze for testing | only at start-up through a cheat (never runtime); or find the global enemy list (`probes/lock_target3.py`) |
| D11 | Invulnerability for test runs | find the player's HP by differencing hit/heal; freeze it live; verify side effects |

## E. Graphics

| # | Idea | First probe |
|---|---|---|
| E1 | Permanent DLAA lambda/epsilon (not only threshold) | `PS5_EBOOT_DUMP=<unpatched dump> python3 tools/dev/analysis/bb_ctx.py 125970f`; find the other field copies in `0x12596F0`; extend `make_dlaa_mod.py` |
| E2 | YEBIS FXAA2 distance-falloff as an option (3-15 m) | cave calling `0xFD3270` once after init + force enable at `0x25D8034` + DLAA off; measure with a falloff spec |
| E3 | Working TAA | find the projection upload (jitter), wire the TAA output; large and risky |
| E4 | Real anisotropy | find the sampler creation code; patch before creation |
| E5 | True >1080p | finish the `computeSurfaceInfo` / `CreateTexture2D` diagnostic hook (log size + error), bisect the rejection |
| E6 | Animation LOD and culling flags | follow the registration of `Disable Entity Culling`, `Enable Primitive Culling`, `Prim Culling Model Count`; toggle live; look at pop-in with scenes |
| E7 | Fog wall, foliage wind | trace readers of `FogA/FogB`/`Fog Param`; a static SFX-OFF toggle (`0x26FD9F2`) is untested |
| E8 | DOF far-only tweak | find the consumer of the near/far values (YEBIS struct copy reader) |
| E9 | Post-effect options (glare, bloom quality) | debug-menu registrations around `0x25E02B0` |
| E10 | Texture streaming after death/warps | compare streaming manager state before/after; `graphics/scan_rt.py <W> <H>` |

## F. onionHEN and tooling

| # | Idea | First probe |
|---|---|---|
| F1 | Persistent toggles (menu state survives relaunch) | write `enabled` back to the JSON after a successful toggle (`CheatService`); keep `enabled` as the persistent source today |
| F2 | Reapply/hot reload of the cheat file without relaunch | read upstream `docs/util_arch/cheats_cpp.md`; frame-rate patches stay exec-time |
| F3 | A packaged lab: pose-lock caves in a non-colliding region | see A5 |
| F4 | Unit tests for the generators | assert disassembly of every cave decodes fully, every RIP target lies in the data block or a known global, push/pop balance; run in CI without a console |
| F5 | An offline emulator test of caves (for example Unicorn) | feed synthetic WorldChrMan/pose memory, check outputs |
| F6 | Regenerate `registry.json` from the generators automatically | add a script under `tools/mods` that emits caves, hooks and data-block fields (they are derivable) |

## H. VRR and display output

| # | Idea | First probe |
|---|---|---|
| H1 | 120 Hz (VRR 48-120) for a PS4 game | the game requests no mode; synthesize a request for refresh enum `0xd` / `0x800d` (see [75](75-avcontrol-vrr.md) section 7, V-A) |
| H2 | The boost bit `0x04000000` instead of the VRR bit | same procedure as V3 |
| H3 | A persistent implementation in the console-side payload (onionHEN app-launch event) | write the same dwords with its kernel read/write primitives |
| H4 | Why *Apply to Unsupported Games* does not engage for Bloodborne | read the app type word and flag the composer receives |
| H5 | Other PS4 games, other displays/TVs, base PS5, other firmware | repeat V1-V5 and record the log lines |
| H6 | Behaviour below 48 FPS | measure what the console and the display do |

## G. Documentation tasks

* Keep [registry.json](registry.json) in sync when a generator changes (cave sizes, hook bytes, data fields are derived from `tools/mods/make_*_mod.py`).
* Add every new experiment to [80](80-experiments-log.md) with controls and noise floor, including negative results.
* Promote `inferred` / `static-only` entries to `confirmed-live` only with a recorded probe (script, scene/procedure, date).
