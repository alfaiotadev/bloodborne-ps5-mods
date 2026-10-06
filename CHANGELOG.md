# Changelog

All notable changes to this repository. Dates are release dates; the versions follow [Semantic Versioning](https://semver.org/) loosely (a new minor version adds mods or options, a patch version fixes bugs).

> **Tested only on firmware 12.40 with a PS5 Pro.** See [docs/compatibility.md](docs/compatibility.md).

## [1.2.0] - 2026-10-07

VRR for PS4 games - 48-60 Hz, and optionally **1080p 119.88 Hz VRR (48-120 Hz)** - plus new defaults for the first-person camera. The release adds host tools and documentation; **the patched onionHEN is unchanged** from 1.1.0, and the cheat file and the profiles differ from 1.1.0 only in the two head-camera values listed under *Changed*.

### Changed
- **FPS head camera defaults: field of view x1.8 (was x1.5) and camera height `OFF_U` 0.30 m (was 0.17 m).** Play-testing with a large weapon (the Whirligig Saw) showed the first-person view too low and the weapon too far outside the picture. Third person is still x1.3. Only two data entries of the head-camera mod change (`0x54A0E04` and `0x54A0E80`), in the default file and in all profiles; nothing else in them differs. Tunable with `make_head_camera_mod.py --u` and `build_cheats.py --fps-fov`; at runtime with the ps5debug writes described in `docs/agents/40-camera-system.md`.
- Documentation tip (no default change): the forward offset `OFF_F` stays 0.32 so that a worn hood stays out of the picture; with the head slot empty it can be lowered to about 0.05 (0.02 let the hair flicker into view).
- `fps_cap.py` accepts caps up to 118 FPS (needs the 120 Hz link, see below); `vrr_watch.py` has a `--hz120` mode and polls the console lightly while a session is running.

### Added
- **`tools/vrr/vrr_watch.py`**: makes the console drive a VRR display (48-60 Hz) while a PS4 game runs. It watches the per-app capability table of the system video service (`SceSysAvControl.elf`) through ps5debug and sets the "VRR supported" bit (`attr` 0x082E0057 -> 0x08AE0057) of a new PS4 session before the console chooses the video mode. The screen goes black for a second or two at launch (HDMI mode change). Start it before the game; nothing is stored on the console.
- **`tools/vrr/vrr120_patch.py`** (optional, more invasive): a three-part **code patch** in the system video service (`plan` / `apply` / `restore`, original bytes verified, firmware 12.40 only) that makes the VRR link of a 1080p PS4 game `1080P_11988` with a 48-120 Hz range. Use it with `vrr_watch.py --hz120` (attr `0x08AA0057`).
- **`tools/vrr/fps_cap.py`**: caps Bloodborne at a frame rate inside the VRR window (for example 55 FPS on the 60 Hz link, 100 FPS on the 120 Hz link; vsync stays on) so the display refresh visibly follows the game; `off` restores 60 FPS. Bloodborne v1.09 with the 60 FPS mod only; refuses to run otherwise.
- **`tools/vrr/avctl_attr.py`**: manual `scan` / `set` / `restore` of the capability record for experiments.
- `docs/vrr.md` (results, usage, safety, limits) and `docs/agents/75-avcontrol-vrr.md` (the capability record bits, the mode enum and structure, the hardware timing id, the mapper and converter, the patch, log lines, the frame timer, experiments, open questions, hazards); registry entries for the system video service, the frame timer and the vsync site.

### Results (PS5 Pro, firmware 12.40, Bloodborne, one 1080p FreeSync Premium monitor)
- Without the tool the display stayed at a fixed 60 Hz at 45 and 30 FPS, although the PS5 option *Apply to Unsupported Games* was on. With the tool the console logged `VRR(peg:60 range:48 - 60)` and the monitor's refresh readout followed a 55 FPS cap; the picture was described as smooth. Below 48 FPS the readout jumped.
- **120 Hz:** changing only the VRR refresh value left the link at 59.94 Hz, because the service chooses the HDMI timing from the requested refresh before the VRR conversion. With the three-part patch the console logged `video: port:HDMI 1080P_11988 ... VRR(peg:60 range:48 - 120)`; with a 100 FPS cap and vsync on the game ran at 99.3 FPS with a flat 10.00 ms frame time (standard deviation 0.00 ms) and the picture was described as smooth; at a 110 FPS cap it reached 106 FPS (GPU-bound at 1080p, 0.6 % hitches). The HDFury 8K Arcana 2 in the HDMI path reported `1080PVRR 442MHz RGB 12b HDR ALLM` on the 120 Hz link (about 445 MHz is expected for 1080p at 119.88 Hz and 36 bpp, about 222 MHz at 59.94 Hz) and the monitor's own counter showed 120. Lowering the render resolution is no longer needed to exceed 60 FPS. The monitor's own refresh readout followed the onionHEN overlay's frame-rate counter closely (it updates every frame, so it is hard to read when the frame time jitters).
- Save data: two test sessions ended with the save flagged as broken (no debugger either time). The first was a VRR session (cause not found). The second had **no VRR tool and no system-process write** and coincided with a 30-second scan of the running game's whole memory by a dev tool, which makes such scans the main suspect. A 29-minute VRR session (237 save mounts, three transient mount errors that recovered on retry), a 12-minute control session without VRR (157 mounts, no errors) and two later VRR sessions (21 and 12 minutes, 112 mounts, no errors; the second on the 120 Hz link) did not repeat it. Details and the small-sample caveat in `docs/vrr.md`.

### Limits
- **Back up your save data before using the tools** (see above); the cause of the broken-save events is not established. Do not scan the whole memory of the running game while saves may be written.
- The 120 Hz patch **writes code into a system process**: verified and restorable, but a wrong patch can confuse the video pipeline until the console is restarted. It covers **1080p only**; other resolutions, other PS4 games, other displays and the base PS5 are untested.
- Needs a host computer and ps5debug after every console restart; firmware-specific addresses (the tools warn or refuse when the layout is not recognised); only Bloodborne and one display were tested.
- A frame-rate unlock experiment (vsync off, 110-140 FPS, correct game speed) on the 60 Hz link is documented in the agent notes but **not shipped**: the display stays at 60 Hz there, so it only tears.

## [1.1.0] - 2026-10-05

The FPS head camera now handles dying. Everything new is part of the `_fps` profile (and optional in the cheat menu); the stable mods are unchanged.

### Added
- **Death camera** (in "FPS head camera"): when HP reaches 0 the first-person view follows the head to the ground instead of hovering at standing height with a fixed view direction. The height floor is lifted, the view direction follows the head bone (eased, no sudden jumps), and the camera never sinks below the feet + 0.30 m. Death is read from the HP field `[[player+0x3b0]+0x20]+0xf8`.
- **Look at the killer after death** (new option): from the moment of death the view stays on the enemy that killed the player (the locked-on target, else the nearest living character within 20 m) instead of tumbling with the head.
- **Death slow motion** (new option): the death plays at normal speed until the "YOU DIED" screen arrives, then every character drops to 5 % speed for about 6 seconds (a GTA-style effect). It scales the per-character speed factor read at `0x1E196BB`; tunable phases (`PH1SCALE`, `PH1END`, `PH2SCALE`, `PH2END`).
- **Close-character guard** (in "FPS head camera"): when the camera would be inside a living character's body (visceral attacks after a parry put the player inside the victim) the game's own camera is used for a moment.
- New demonstration clip as the README hero image and first item of the gallery.
- `docs/known-issues.md`: warning and recovery steps for a save flagged as broken after closing the game with a debugger attached.

### Changed
- The head search also scans pose holders hosted by `[model container+0x10]` (seen once in a session where the usual holders had no world-space bone arrays; the camera then fell back to a fixed head height without head bobbing).
- The `_fps` profile enables the new options; the manager cave is now 3847 bytes (four cheat entries of at most 1000 bytes each); the data block is 0x200 bytes.
- `tools/dev` live tools: `apply_live.py` restores the hook bytes before it rewrites a cave (rewriting a cave whose code shifted while the game ran it crashed the game); `crash_catch.py` always detaches the debugger on exit.
- Documentation for AI agents: memory map, registry, camera system notes and the experiments log cover the new fields and findings.

### Fixed
- FACE2 (body faces the view) is suspended while dead and while the close-character guard is active.
- A flat grey screen after death in an early killer-camera build (the w lane of the look direction was not zeroed) - never released.

### Notes
- The patched onionHEN files (`OnionHEN.elf`, `bootstrapper.elf`, `shellui.elf`) are **unchanged** from v1.0.0; they are attached again for convenience (same `SHA1SUMS`).
- **Never close the game while a ps5debug debugger is attached.** The system kills the game instead of letting it exit, and the save data is flagged as broken (see `docs/known-issues.md` for the fix). The cheats themselves do not attach anything.

## [1.0.0] - 2026-10-04

First public release: 60 FPS (based on Lance McDonald's patch), no motion blur, no chromatic aberration, skip intro, wide FOV, DLAA threshold 0.3, anisotropic filtering and no depth of field (both with little or scene-specific effect), DLC save unlock, an experimental first-person head camera (touchpad double-click toggle) with body-facing and lock-on aim, the patched onionHEN, generators, research notes, agent documentation and the feature site.
