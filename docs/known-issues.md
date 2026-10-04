# Known issues and limitations

> **Tested only on firmware 12.40 with a PS5 Pro.** Everything below was observed there. Other consoles and firmware are unknown territory.

## General

- **Base PS5 / PS5 Slim / Digital: untested.** Frame timings and the stability of the 60 FPS patch may differ. Please report results with the templates in `.github/ISSUE_TEMPLATE/`.
- **Game version:** the addresses belong to `CUSA03173` v01.09 only. Another version or region needs new addresses and can crash if the file is applied to it.
- **Texture streaming:** after the player dies, or after repeated warps/teleports, some textures stay low-resolution until the area is reloaded. It was met repeatedly while measuring with the mods enabled; it is not verified whether it also happens without them. Reloading the area fixes it.
- **Enemy / AI cheats at runtime:** toggling an "enemy movement" style cheat in the onionHEN menu while playing crashed the game within seconds in the game's own character-system thread (observed more than once). The mods in this repository do not touch AI; just do not flip AI cheats while testing them.
- **Crash dialog:** dismiss it. A crash dialog left open can make the console shut itself down.
- **Saves:** a crash during an autosave can leave a damaged save (this happened during development while experimenting with code that crashed the game). Keep a backup of the save data before trying experimental mods.

## FPS head camera (experimental)

- **Body faces the view hides the coat/hood.** The cloth simulation reacts to the rotated model rows; the cloth is back when the camera is off (third person) or the option is off. The option is active only in the head-camera view and was tested from a cold start (PS5 Pro, firmware 12.40).
- **Lock-on aim** is a first iteration: it aims at the target's lock point from the head. Close to an enemy while strafing the view can twitch; the aim offset persists after releasing the lock until you turn the camera.
- **Silhouette spin when backpedalling starts:** the game plays a turning animation that rotates the body in front of the camera for a moment (only visible with "body faces the view").
- **Cutscenes and scripted cameras:** the head camera only replaces the position when the head is within a sane distance of the game's own camera, so most cutscenes play normally, but unusual scripted cameras were not exhaustively tested.
- **Toggling:** the camera can be switched off and on at any time (double-click the touchpad, or the cheat menu). If something looks wrong, that resets it. Each touchpad click also opens/closes the game's personal-effects (gesture) menu for a moment.
- **Animation rate:** where the game updates animation at 30 Hz the head bobbing is interpolated; it is smooth but follows the animation, not the display refresh.

## Not supported / out of scope

- Anything online. Use the mods offline.
- Game assets or save editing: this repository has none.
