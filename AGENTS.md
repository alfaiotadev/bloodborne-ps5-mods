# AGENTS.md - start here (AI coding agents and humans)

This repository contains image-quality and gameplay mods for **Bloodborne: Game of the Year Edition (`CUSA03173`, v01.09)** on a **jailbroken PS5**, delivered as **onionHEN cheats** (memory patches applied to the running game at start-up), together with the tools and the reverse-engineering knowledge needed to continue the work. This file is the entry point: purpose, orientation, rules, quick starts, the verification checklist and the index of the detailed agent documentation in [`docs/agents/`](docs/agents/).

> ## Disclaimer - read this before you claim anything
>
> **All testing was done on firmware 12.40 with a PS5 Pro** (Bloodborne runs in backward-compatibility mode, native 1080p). **Behaviour and performance on a base PS5 (or Slim/Digital), on other firmware versions and on other game versions or regions are UNKNOWN.** Do not claim, imply or extrapolate otherwise; write "untested" and say what would have to be done to test it. Image-quality numbers were measured on 4K screenshots of a 1080p render. Use only on a console and a game copy you own; this project is not affiliated with Sony Interactive Entertainment, FromSoftware, onionHEN or any person or project named in [CREDITS.md](CREDITS.md). See also [docs/compatibility.md](docs/compatibility.md).

## 1. Orientation in one screen

| Path | What it is |
|---|---|
| `cheats/CUSA03173_01.09.json` | The shipped onionHEN cheat file (defaults: 60 FPS, no motion blur, no chromatic aberration, skip intro on; everything else opt-in). `cheats/profiles/` = `quality` and `fps` selections. **Generated - never hand-edit.** |
| `tools/mods/` | **Authoritative generators**: `make_*_mod.py` (one per mod), `caves.py` (tiny x86-64 assembler: `Asm`, `rip`, `hook5`, `hook`), `build_cheats.py` (assembles the JSON, checks overlaps), `verify_against_dump.py` and `fill_off_from_dump.py` (need an unpatched dump you make yourself), `data/base_mods.json` (60 FPS etc.). Pure Python 3 (+ `capstone` for verification). |
| `tools/dev/` | Live research tools over the **ps5debug** payload (`core/`, `mods-live/`, `camera/`, `graphics/`, `probes/`, `analysis/`, `specs/`, `notify/`); reference: [tools/dev/README.md](tools/dev/README.md). |
| `onionhen/` | `onionhen-bloodborne.patch` on top of upstream onionHEN `b23ffe6` (exec-time auto-apply, XOM-safe cave mapping, per-mod `enabled`, screenshot hook, DBG overlay), build notes, checksums. |
| `docs/agents/` | **Agent documentation** (index in section 8) incl. machine-readable [`registry.json`](docs/agents/registry.json): every known address, structure, cave, hook and data-block field with confidence. |
| `docs/research/` | Human-readable research write-ups, including negative results. |
| `docs/*.md` | End-user docs: install, features, known issues, compatibility. |

How a mod gets into the game: **generator** (`tools/mods/make_x_mod.py`) -> `build_cheats.py` -> `cheats/*.json` -> FTP to `/data/OnionHEN/cheats/CUSA03173_01.09.json` -> game launch -> patched onionHEN suspends the game, writes every `"enabled": true` mod (data, caves, then hooks), resumes it -> the mods are live from the first frame. Live research uses ps5debug (TCP 744) from a **bridge host** (any Linux/macOS machine that can reach the console; address in `PS5_HOST`, placeholder `<console-ip>`).

## 2. Golden rules (technical)

1. **Generators are the source of truth.** Change `tools/mods/make_*_mod.py`, regenerate with `python3 tools/mods/build_cheats.py [--all-profiles]`, never edit `cheats/*.json` by hand. Where notes and generators disagree, the generators (current release build) win.
2. **Addresses are absolute virtual addresses of `CUSA03173` v01.09.** Every cheat entry needs `"absolute": true`. Another build needs a new address map and can crash the game.
3. **Apply order: data -> caves -> hooks last -> flag bytes last.** Remove in reverse: flags, hooks (restore original bytes), then caves. Never clear or rewrite a live cave; unhook first. Write each code patch with **one** write call. Hooks carry the original bytes as `off`; caves/data get `off = on` from `build_cheats.py` (never zeros).
4. **Every cave must be load-safe.** Hooks are live from the first frame, while saves and maps load. Range-check every pointer (heap high dword `2..3` and low dword >= `0x10000`; `0x1_0000_0003` and `0x5_0000_0000` are packed integers, not pointers - both crashed the game), check vtables, check alignment, NaN-guard float compares; if any check fails do nothing and let the game run its original code.
5. **Do not trust layouts.** Slot offsets and holders of the pose arrays change per session and after respawn; the model matrix is zero after respawn. Search, validate, fall back.
6. **Never write the follow camera's own state.** Override only the camera manager's output copy (`0x1836C54`). Rows written from outside are overwritten within 12 ms.
7. **Values the game rewrites every frame cannot be changed by data writes** (scene params, derived camera fields). Patch the consumer code or a persistent PARAM row.
8. **Keep every cheat `memory` entry <= 1024 bytes** (onionHEN skips longer ones but still writes the hooks -> crash at the first run of the cave). `tools/mods/build_cheats.py` splits caves/data automatically and asserts the cap; live ps5debug writes do not have the cap, so always finish with a cold start (restart the game, load a save).
9. **Do not run the lab tools (`scene.py`, `scenelib.py`, `head_cam.py`, `cam_lock.py`, `ab_loop.py` with `scenes`) while the release head-camera mod is active**: they share hooks, caves and the data block with different contents ([docs/agents/10](docs/agents/10-memory-map.md) section 1).
10. **Timing patches (60 FPS) are exec-time only.** Never toggle them mid-run.
11. **Image-quality claims need measurement:** warm-up, fog off (`SFX-OFF`), noise floor, positive and negative controls, a cold start ([docs/agents/80](docs/agents/80-experiments-log.md)).
12. **Mark confidence honestly:** `confirmed-live` (read/written on the running game and observed), `inferred`, `static-only`. Do not promote a label without a recorded probe.
13. **Release defaults stay conservative:** only 60 FPS, No Motion Blur, No CA, Skip Intro are on by default; experiments are opt-in and say so in their name.

## 3. Safety rules (people, console, repository)

* **Tell the user before any visible or disruptive console action**, in the message that precedes it: game kill/restart, ShellUI restart (screen black about 5 s), teleports/warps, camera locks or jumps, toasts, flashing effects, anything that needs a reboot. Prefer the no-reboot update path ([docs/agents/20](docs/agents/20-tooling.md) section 5). Confirm the game is closed before restarting ShellUI.
* **Do not write to the console memory or files you were not asked to touch.** Back up the console's cheat file (`curl` download) before replacing it; keep old ELFs under other names; never delete what you cannot restore.
* **Never print or log tokens, passwords or keys** (the repository has none; never create `.env` files with secrets in the tree; never commit secrets). ps5debug has no authentication: trusted network only.
* **Do not toggle AI/enemy cheats at runtime while testing other mods**: toggling "enemy movement" crashed the game in its own `CSChrThread4` within seconds, repeatedly. Apply such cheats before launch or not at all.
* **System processes are not game memory.** `SceSysAvControl.elf` can be read and, narrowly, written through ps5debug ([docs/agents/75-avcontrol-vrr.md](docs/agents/75-avcontrol-vrr.md)); write only the fields you identified, read back, and expect that a console restart is the only reset. Its code can be patched too (`tools/vrr/vrr120_patch.py`): verify the original bytes first, keep a restore path, and never scan the whole memory of the running game while saves may be written (see known-issues). Never read the code of system libraries inside the game process (execute-only, can crash the game).
* **Keep a backup of the save data** before experiments that can crash the game (a crash during an autosave can damage a save). Play offline while memory is modified.
* A **console crash dialog must be dismissed** by the user; left open it can make the console shut itself down.
* **No game assets, no memory dumps, no copyrighted binaries** in the repository (dumps are game code: `.gitignore` them; payload ELFs are only referenced by checksum).
* **Commit only when the user asks.** Do not push, tag, publish or rewrite history on your own initiative. No personal names, e-mail addresses, home-directory paths, console IPs or private hostnames in code, docs or commit messages (use `<console-ip>`, `PS5_HOST`, repository-relative paths).
* Known hazards of the delivery path: [docs/known-issues.md](docs/known-issues.md) and [docs/agents/70](docs/agents/70-onionhen-cheat-engine.md) section 4.

## 4. Quick start A: add or modify a cheat mod (no console needed for steps 1-4)

```bash
cd tools/mods
python3 build_cheats.py --out /tmp/bb_test.json          # builds all mods, prints "no overlaps" or fails
python3 verify_against_dump.py /tmp/bb_test.json <your_unpatched_eboot_dump.bin>   # every 'off' matches the dump, hooks end on instruction boundaries
```

1. Read [docs/agents/30-code-cave-playbook.md](docs/agents/30-code-cave-playbook.md) (API, template, mistakes that happened) and [10-memory-map.md](docs/agents/10-memory-map.md) (free cave space, hook sites).
2. Copy the pattern of the closest generator (`make_dlaa_mod.py` for a hook+constant, `make_fov_mod.py` for an operand redirect, `make_dof_mod.py` for an inline patch, `make_head_camera_mod.py` for the full style), register it in `build_cheats.py`.
3. Disassemble your cave with capstone and read it twice (playbook section 6).
4. Build, check overlaps, verify against your dump.
5. With the user's consent: back up the console file, upload (`curl -gsS -T <json> ftp://$PS5_HOST:2121/data/OnionHEN/cheats/CUSA03173_01.09.json`), ask the user to launch the game, watch the kernel log (`nc $PS5_HOST 3232`) for `auto-applied '<name>'`.
6. Test live details with `tools/dev/mods-live/apply_live.py <json> "<mod name prefix>"`, then **always** repeat from a cold start.
7. Run the verification checklist (section 6), update the docs and `registry.json`.

## 5. Quick start B: investigate game memory live

```bash
export PS5_HOST=<console-ip>                      # the console must run ps5debug (port 744) and the game
python3 tools/dev/core/ps5dbg.py                  # connectivity: prints the process list (look for eboot.bin)
python3 tools/dev/mods-live/code_patch.py 593E878 ?8      # read 8 bytes at an address (writing: <addr> <hex bytes>)
python3 tools/dev/probes/read_player.py           # WorldChrMan -> player ChrIns
python3 tools/dev/camera/read_cam.py              # camera manager and its cameras
```

* Protocol, pointer-chain idiom, vtable scanning, dumping, the debugger: [docs/agents/20-tooling.md](docs/agents/20-tooling.md). Structures: [10-memory-map.md](docs/agents/10-memory-map.md).
* Loop: hypothesis -> smallest live write that restores itself (`flag_toggle.py`, `ab_loop.py`) -> does the game rewrite it (`persisted after hold`)? -> measure -> persistent patch -> cold start.
* Stuck or crashed: `tools/dev/probes/crash_catch.py` (needs root to listen on TCP 755) and the klog.
* Disassembly needs your own dump: `PS5_EBOOT_DUMP=<dump> python3 tools/dev/analysis/bb_ctx.py <addr_hex>`.

## 6. Verification checklist - before you say "it works"

Tick every line you can, state which you could not, and report the scope ("PS5 Pro, firmware 12.40, CUSA03173 v01.09").

1. [ ] `build_cheats.py` ran without `OVERLAP` and every hook entry has an `off` that restores the original bytes.
2. [ ] `verify_against_dump.py` reports `all match` and every hook `OK` against an **unpatched** dump (or state that no dump was available).
3. [ ] The cave disassembles cleanly end to end; every RIP target is in the data block or a known global; push/pop balanced on every exit path; every dereference validated; NaN-safe compares.
4. [ ] Entry sizes <= 1024 bytes (the builder asserts it) and a **cold-start test** passed: restart the game, load a save, read the caves back (`hc_state.py` for the camera mods).
5. [ ] Live apply: read-back identical; fps still 60 (overlay or `core/onion_sample.py`).
6. [ ] **Cold start from the JSON**: klog shows `auto-applied '<name>'`; main menu, load save, map load, walk, run, roll, ladder, **death and respawn**, **teleport between maps**, lock on/off, 10 minutes of play.
7. [ ] Runtime behaviour: say exactly what you tested for toggling (menu toggle, flag byte, touchpad). Menu toggle-off of cave mods relies on `off = on` entries and is untested on hardware (70, hazard 2).
8. [ ] For image-quality or other measured claims: scenes with warm-up, SFX-OFF, repeats for the noise floor, positive and negative control, `persisted after hold: YES`, no death during the run, effect reported with its noise floor.
9. [ ] No AI/enemy cheat was toggled during the tests; save backed up; console state restored (cheat file, any live writes, lab hooks removed with `scene.py remove` / `head_cam.py remove`).
10. [ ] Docs updated: [features](docs/features.md) / [known issues](docs/known-issues.md) if user-visible, [10](docs/agents/10-memory-map.md) + [registry.json](docs/agents/registry.json) if an address, hook or data field changed, [80](docs/agents/80-experiments-log.md) for the experiment and its negative results.
11. [ ] Confidence labels set honestly; nothing claimed for a base PS5, other firmware or other game versions.

## 7. Quick start C: build the patched onionHEN

```bash
git clone https://github.com/aydencharles/onionHEN && cd onionHEN && git checkout b23ffe6
git apply --check ../<this repo>/onionhen/onionhen-bloodborne.patch && git apply ../<this repo>/onionhen/onionhen-bloodborne.patch
docker build -t onionhen-build .        # once (about 20 min); then the payload build (about 4 min): see onionhen/BUILD.md
```

Read [docs/agents/70-onionhen-cheat-engine.md](docs/agents/70-onionhen-cheat-engine.md) first: it lists what the patch changes, **a gap in the shipped patch** (two new source files for the DBG probes are not in the diff), the cheat-engine limits derived from the source (1024-byte entries, toggle-off needing non-empty `off`), and the no-reboot update procedure (visible: the screen goes black for about 5 s - warn the user). Prebuilt ELFs are on the Releases page; verify them with `sha1sum -c onionhen/SHA1SUMS`.

## 8. Index of `docs/agents/`

| File | Content |
|---|---|
| [00-orientation.md](docs/agents/00-orientation.md) | Architecture (console, bridge host, ps5debug, onionHEN, cheat JSON), ports, game facts, **glossary** (cave, hook, holder, slot, manager, follow camera, pose object, YEBIS, DLAA ...). |
| [10-memory-map.md](docs/agents/10-memory-map.md) | Every known address, structure and offset with confidence and where it was verified; cave allocation map; data block; console files; source disagreements. |
| [20-tooling.md](docs/agents/20-tooling.md) | ps5debug protocol and opcodes, reading/writing memory, FTP upload of the cheat file, launching/restarting, dumping, screenshots, A/B loop and scenes, crash catching, script map. |
| [30-code-cave-playbook.md](docs/agents/30-code-cave-playbook.md) | Step-by-step recipe with `caves.py`, template, hook-site and cave-space choice, verification with capstone, apply order, **catalogue of mistakes that happened**. |
| [40-camera-system.md](docs/agents/40-camera-system.md) | Camera pipeline, FOV mod, FPS head camera (design, data block, AIM, FACE2, touchpad toggle), limitations, ideas. |
| [50-aa-and-graphics.md](docs/agents/50-aa-and-graphics.md) | The game's DLAA pass, FXAA/TAA/aniso/DOF/LOD/resolution results (incl. negative), measurement method, ideas. |
| [60-player-and-world.md](docs/agents/60-player-and-world.md) | Object graph, position/warp, model/pose, enemies, time step, input, hazards, ideas. |
| [70-onionhen-cheat-engine.md](docs/agents/70-onionhen-cheat-engine.md) | onionHEN structure, our patch, exec-time apply, cheat JSON semantics and **hazards**, build/deploy, stock vs patched. |
| [75-avcontrol-vrr.md](docs/agents/75-avcontrol-vrr.md) | The system video service (`SceSysAvControl.elf`): per-app capability record and its bits, mode enum/structure, how VRR 60 was enabled for a PS4 game, the frame timer behind `fps_cap.py`, the (unshipped) vsync-off experiment, open questions (120 Hz), hazards. |
| [80-experiments-log.md](docs/agents/80-experiments-log.md) | Methodology, evidence rules, table of experiments with outcomes. |
| [90-open-questions.md](docs/agents/90-open-questions.md) | Repository inconsistencies to fix, verification gaps, platform coverage, feature and graphics ideas, each with a first probe. |
| [registry.json](docs/agents/registry.json) | Machine-readable `{schema, game, addresses, structures, caves, hooks, data_block, system_processes}`. |
| [02-tooling.md](docs/agents/02-tooling.md) | Redirect stub (old name referenced by two generator docstrings). |

Reading order for a cold start: this file -> `00` -> `30` (if you will write code) or `20` (if you will probe) -> the subsystem file -> `90`.

**Known traps in this repository** (details and first probes in [docs/agents/90-open-questions.md](docs/agents/90-open-questions.md) section A): the 1024-byte cheat-entry cap versus the 1761-byte head-camera cave; the onionHEN patch lacks two new source files; README/install claim stock onionHEN suffices; menu toggle-off of cave mods is untested; the lab tools collide with the release head camera; the touchpad double-click toggle has no verification record.

## 9. Credits and license

Third-party work (Lance McDonald's 60 FPS patch, onionHEN, etaHEN, kstuff-lite, ps5-payload-dev, ps5debug and more) is credited in [CREDITS.md](CREDITS.md); do not re-list or alter attributions without the maintainer. The repository is GPL-3.0 ([LICENSE](LICENSE)). Contribution rules: [CONTRIBUTING.md](CONTRIBUTING.md).
