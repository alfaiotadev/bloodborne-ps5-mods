# Installation guide

> **Tested only on firmware 12.40 with a PS5 Pro.** Other consoles/firmware are untested - see [compatibility.md](compatibility.md).

## Requirements

- A PS5 that is already **jailbroken** and able to run payloads, **system software 12.40**. Setting up the jailbreak itself is outside the scope of this repository; see the projects listed in [CREDITS.md](../CREDITS.md) (WebKit autoloader, kstuff-lite, ps5-payload-dev elfldr, ...).
- The **patched onionHEN** from [`../onionhen/`](../onionhen/) (prebuilt ELFs on the Releases page, checksums in `onionhen/SHA1SUMS`). It provides the cheat engine, the in-game cheat menu and the Toolbox, plus what these cheats rely on: applying cheats at game launch, a code-cave allocator for the extra code, execute-only page handling and the per-cheat `enabled` flag. Stock onionHEN does not have these and was **not** tested with this file; the code-cave mods (Wide FOV, DLAA, anisotropic, head camera) are not expected to work on it.
- **Bloodborne Game of the Year Edition**, title id `CUSA03173`, **version 01.09** (the process is `eboot.bin`). Other versions/regions need different addresses.
- An FTP client (or any way to copy a file to the console's `/data` partition).

## Install the cheats

1. Copy `cheats/CUSA03173_01.09.json` from this repository to the console as
   `/data/OnionHEN/cheats/CUSA03173_01.09.json` (the folder already exists once onionHEN has run; create it if it does not).
   The file name must match the title id and version exactly.
   **Profiles:** `cheats/profiles/CUSA03173_01.09_quality.json` (Wide FOV x1.3 and DLAA threshold 0.3 on top of the defaults) and `cheats/profiles/CUSA03173_01.09_fps.json` (the same with FOV x1.5, the experimental FPS head camera with its death camera and death slow motion, and the lock-on aim). Pick one and copy it to the path above under the name `CUSA03173_01.09.json`. Any combination can be generated with `tools/mods/build_cheats.py` (see its docstring); the FOV multiplier is `--fov-scale`.
2. Start Bloodborne. onionHEN applies the cheats that are marked enabled in the file **at launch** (the process is paused for an instant while the patches are written).
3. Open the cheat menu to toggle the optional mods on or off. The shortcut is configured in onionHEN's `config.ini` on the console (`/data/OnionHEN/config.ini`, section `[shortcuts]`, key `cheats_menu`; values: `off`, `r3_l3`, `l2_triangle`, `long_options`, `long_share`, `share`).

**Defaults:** 60 FPS, no motion blur, no chromatic aberration and skip-intro logos are enabled; everything else is opt-in. To change what is enabled at launch, edit the `"enabled"` flags in the JSON, or regenerate it with [`tools/mods/build_cheats.py`](../tools/mods/build_cheats.py).

## Using the FPS head camera

- Switch on **FPS head camera (experimental)** after the game has loaded into the world (it also works if it is enabled at launch). The camera jumps to the character's head.
- **Aim at the lock-on target** and **body faces the view** are extras that need the head camera. Read the notes in [features.md](features.md) and [known-issues.md](known-issues.md) first (the second one hides the coat/hood cloth while it is on).
- **Double-click the touchpad** (two clicks within half a second) to switch between the first-person and the normal camera at any time; the field of view follows (x1.3 third person, x1.5 first person in the `_fps` profile). The game's personal-effects menu flashes open and closed with the clicks.
- If the camera ever misbehaves (for example after an unusual cutscene), double-click the touchpad twice (off, then on) or toggle **FPS head camera** in the cheat menu: that resets its state.

## Updating and uninstalling

- **Update:** overwrite `/data/OnionHEN/cheats/CUSA03173_01.09.json` with the new file and restart the game.
- **Uninstall:** delete that file (or set every `"enabled"` to `false`) and restart the game. Nothing else on the console was changed by the cheats; the patched onionHEN can be replaced by the stock one at any time.

## Troubleshooting

- **The game crashes at launch:** one of the mods does not fit your setup. Disable mods one by one (edit `"enabled"` flags) starting with the optional ones. Dismiss the console's crash dialog; leaving it open can make the console shut down.
- **A cheat has no effect:** check that the title id/version in the file name and the file header (`CUSA03173`, `01.09`) match the running game, and that the game process is `eboot.bin`.
- **The game crashes shortly after you toggle a cheat in the menu:** avoid toggling enemy/AI related cheats (for example "enemy movement") while playing; toggling those at runtime crashed the game in testing. The mods in this repository are fine to toggle.
- **Textures look blurry after dying or after many warps:** a known game streaming issue, not a mod effect; reloading the area fixes it.
- Anything else: open an issue with the console model, firmware version, game version and which mods were enabled (templates provided).
