# Compatibility and test disclaimer

**Everything in this repository has only been tested on:**

| | |
|---|---|
| Console | **PS5 Pro** (Bloodborne runs in backward-compatibility mode) |
| System software | **12.40** |
| Game | Bloodborne **Game of the Year Edition**, `CUSA03173`, **version 01.09** (`eboot.bin` process) |
| Payload chain | onionHEN (patched, see `onionhen/`) running on top of kstuff-lite, loaded by the WebKit autoloader |
| Display output | 4K output, game renders at native 1080p |

**What this means for you**

- **Performance has only been measured on a PS5 Pro.** The original PS5 (and PS5 Slim/Digital) may behave differently — in particular the 60 FPS patch, anything that changes how much work the GPU/CPU does, and the in-game frame timings. We simply do not know. If you test on a base PS5, please report the results (see the issue templates) — they are very welcome.
- **Other firmware versions are untested.** The mods are code patches at fixed virtual addresses inside `eboot.bin`, so they do not depend on the firmware itself, but the payload chain (kstuff-lite, onionHEN, the autoloader) may behave differently on other firmware versions.
- **Other game versions or regions are untested.** The addresses in the cheats are specific to `CUSA03173` v01.09. A different title ID or version needs a different set of addresses (the research docs describe how to find them). Every cheat checks nothing by itself: applying it to another build can crash the game.
- **Image-quality numbers** (sharpness, anti-aliasing comparisons) were measured on a 4K output of a native 1080p render captured with the console's own screenshot function; results on other output resolutions may differ.

**Safety notes**

- Cheats are applied at game start (`exec` time) and can be toggled in the onionHEN Toolbox. If the game crashes at start-up, switch the offending mod off by editing or removing `/data/OnionHEN/cheats/CUSA03173_01.09.json`.
- A crash dialog on the console must be dismissed; leaving it open can make the console shut itself down.
- Use these mods only on a console you own, with a game copy you own. Online play with modified game memory may violate the terms of service of the platform; we recommend playing offline.

## VRR tools

The VRR tools in [`tools/vrr`](../tools/vrr/README.md) were tested on the same console and firmware (PS5 Pro, 12.40) with Bloodborne and one HDMI monitor (1080p, FreeSync Premium, the console reported VRR range 48-240 Hz, ALLM supported; PS5 settings VRR, 120 Hz output and ALLM on Automatic, *Apply to Unsupported Games* on). Other PS4 games, other displays or TVs, other firmware and the base PS5 are untested. Details: [vrr.md](vrr.md).
