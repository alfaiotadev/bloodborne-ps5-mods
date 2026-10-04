# Changelog

All notable changes to this repository. Dates are release dates; the versions follow [Semantic Versioning](https://semver.org/) loosely (a new minor version adds mods or options, a patch version fixes bugs).

> **Tested only on firmware 12.40 with a PS5 Pro.** See [docs/compatibility.md](docs/compatibility.md).

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
