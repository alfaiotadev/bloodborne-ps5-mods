# Research documentation

Technical write-up of the reverse-engineering behind the mods in this repository: Bloodborne
image-quality and gameplay-camera patches for a jailbroken PS5, applied at game start by the
onionHEN cheat engine.

These documents are the lab notes of the project cleaned up for other researchers. They keep the
**negative results** (supersampling, temporal AA, anisotropic filtering, LOD, ...) because they cost
real time to find and are the most reusable part.

> **Scope and disclaimers**
>
> - **All measurements were done on firmware 12.40 with a PS5 Pro**, running Bloodborne Game of the
>   Year Edition (`CUSA03173`, version 01.09, process `eboot.bin`) in backward-compatibility mode.
>   **Behaviour and performance on a base PS5 are unknown.** Other firmware versions, other game
>   versions and other regions are untested. See [`../compatibility.md`](../compatibility.md).
> - This is independent research. It is **not affiliated with or endorsed by Sony Interactive
>   Entertainment, FromSoftware or onionHEN**. The project is GPL-3.0 (see `LICENSE`).
> - No game assets, game binaries or memory dumps are included or described byte-for-byte. Short byte
>   patterns, addresses and offsets are given for interoperability. You need your own legitimate copy
>   of the game and your own console.
> - Third-party work this research builds on (the 60 FPS patch by Lance McDonald, onionHEN, ps5debug,
>   kstuff, the PS5 payload SDK, ...) is credited in [`../../CREDITS.md`](../../CREDITS.md).
> - How the console is jailbroken is out of scope; the docs start from "a console that runs
>   payloads".

## Documents

| # | File | One-line summary |
|---|------|------------------|
| 01 | [`01-platform-and-tooling.md`](01-platform-and-tooling.md) | Test setup, ps5debug protocol (ports 744 / 755, opcodes), reading/writing game memory, why cheat offsets are absolute virtual addresses, screenshot hook overview. |
| 02 | [`02-code-caves-and-hooks.md`](02-code-caves-and-hooks.md) | The code-cave / `jmp rel32` technique, apply order, restoring on "off", the cave and data layout of the release build, pointer-validation pitfalls and the SIGSEGV root-cause story. |
| 03 | [`03-anti-aliasing-and-image-quality.md`](03-anti-aliasing-and-image-quality.md) | The game's AA pass is already DLAA; FXAA/DLAA/TAA experiments, DLAA threshold sweep (chosen default 0.3), anisotropy, depth of field, LOD, FOV, resolution/supersampling, and the measurement method. |
| 04 | [`04-scene-automation-and-measurement.md`](04-scene-automation-and-measurement.md) | Screenshot automation, player warp and camera pose-lock, repeatable "scenes", texture-streaming gotchas, comparison tools (`analyze_ab`, `make_strips`, `make_slider`). |
| 05 | [`05-fps-head-camera.md`](05-fps-head-camera.md) | The FPS head camera from first attempt to final design: manager hook, head bone source, holder/slot scan, 30 Hz latch, collision cast hook, FACE2, lock-on aim, data block, every crash and what failed. |
| 06 | [`06-player-world-and-camera-structures.md`](06-player-world-and-camera-structures.md) | Reference tables of every structure found (WorldChrMan, player ChrIns, model/pose objects, physics body, camera manager and follow camera, parameter tables, YEBIS context, DLAA pass, ...), with confidence. |
| 07 | [`07-onionhen-integration.md`](07-onionhen-integration.md) | What the onionHEN patch changes, the cheat JSON format, exec-time auto-apply, runtime toggling and its limits. |
| 08 | [`08-experiment-log-and-negative-results.md`](08-experiment-log-and-negative-results.md) | Compact chronological table of every experiment and its outcome. |

## Suggested reading order

1. **01** then **02** - the platform and the patching technique; everything else builds on them.
2. **07** - how the patches get applied (short).
3. **03** and **04** - image quality and how it was measured. Read 04 before trusting any number in 03.
4. **05** and **06** - the camera work and the structure reference.
5. **08** - the one-page index of what was tried.

If you only want to port the mods to another game build, read 01 (address resolution), 02 (hook
rules) and 06 (what has to be re-found).

## Conventions

- **Addresses** are absolute virtual addresses in the `eboot.bin` process (image base `0x400000`),
  written `0x183F77B`. They are valid only for `CUSA03173` v01.09. Heap addresses (`0x2_0000_0000` and
  up) change on every run and are only given as examples.
- **Offsets** `[x+0x48]` means "read the 8-byte pointer at address `x + 0x48`"; `x+0x48` without
  brackets is the address itself. `[[0x593E878]+0x60]` is a pointer chain.
- **Floats** are IEEE-754 single precision, little-endian; Y is up in world space.
- **Confidence** is stated per fact where it matters:
  - *confirmed* - verified on the console (live memory reads/writes, crash reproduction, visual
    confirmation on hardware by the maintainer, or measured screenshots);
  - *inferred* - derived from disassembly, from indirect evidence, or from naming in the game's own
    debug strings; plausible, not exercised.
- **Percentages for image sharpness** are changes of a normalised Laplacian metric (defined in
  [03](03-anti-aliasing-and-image-quality.md#2-measurement-method)), not perceptual scores.
- **`tools/dev/...`** refers to the lab tooling (ps5debug client, scene/AB loops, analysis scripts).
  **`tools/mods/...`** are the release generators. Where a lab script is described but is not shipped
  in the repository, the description still stands as a record of the method.
- Where the lab notes and the release generators disagree, the generators (the current release build)
  are authoritative and the docs say so.

## What ships and what is research only

| Item | Where | Default in the release cheat file |
|------|-------|-----------------------------------|
| 60 FPS (derived from Lance McDonald's patch) | `tools/mods/data/base_mods.json` | on |
| No motion blur, no chromatic aberration, skip intro logos | `tools/mods/data/base_mods.json` | on |
| Wide FOV (x1.3) | `tools/mods/make_fov_mod.py` | off |
| DLAA threshold 0.3 | `tools/mods/make_dlaa_mod.py` | off |
| FPS head camera, FACE2, lock-on aim | `tools/mods/make_head_camera_mod.py` | off |
| Anisotropic filtering 16x | `tools/mods/make_aniso_mod.py` | off (no measurable effect, see 03) |
| No depth of field | `tools/mods/make_dof_mod.py` | off |
| DLC save requirement unlock | `tools/mods/data/base_mods.json` | off |
| Supersampling / resolution experiments, forced YEBIS FXAA, TAA init flags, LOD x4, SFX-off | research only | not shipped |

The release cheat file is produced by `tools/mods/build_cheats.py`, which also checks that no two mods
write overlapping memory.
