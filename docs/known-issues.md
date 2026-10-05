# Known issues and limitations

> **Tested only on firmware 12.40 with a PS5 Pro.** Everything below was observed there. Other consoles and firmware are unknown territory.

## General

- **Base PS5 / PS5 Slim / Digital: untested.** Frame timings and the stability of the 60 FPS patch may differ. Please report results with the templates in `.github/ISSUE_TEMPLATE/`.
- **Game version:** the addresses belong to `CUSA03173` v01.09 only. Another version or region needs new addresses and can crash if the file is applied to it.
- **Texture streaming:** after the player dies, or after repeated warps/teleports, some textures stay low-resolution until the area is reloaded. It was met repeatedly while measuring with the mods enabled; it is not verified whether it also happens without them. Reloading the area fixes it.
- **Enemy / AI cheats at runtime:** toggling an "enemy movement" style cheat in the onionHEN menu while playing crashed the game within seconds in the game's own character-system thread (observed more than once). The mods in this repository do not touch AI; just do not flip AI cheats while testing them.
- **Crash dialog:** dismiss it. A crash dialog left open can make the console shut itself down.
- **Never close the game while a ps5debug debugger is attached.** The system then kills the game instead of letting it exit (`CRASH KILL` in the console log, `mDBG: Process stopped`), the save data stays mounted and the system flags it as broken: the next start shows "The save data is corrupted. Recreate save data?". The save file itself can be fine; the flag lives in the system database (`/system_data/savedata/<userid>/db/user/savedata.db`, table `savedata`, column `is_broken`). Answer NO, close the game, restore a backup of the save file if you have one, and with the game closed set `is_broken` to 0 for that title/directory (keep a copy of the database first). The cheats themselves do not attach anything; this only concerns the research tools in `tools/dev`.
- **Saves:** a crash during an autosave can leave a damaged save (this happened during development while experimenting with code that crashed the game). Keep a backup of the save data before trying experimental mods.

## FPS head camera (experimental)

- **Body faces the view hides the coat/hood.** The cloth simulation reacts to the rotated model rows; the cloth is back when the camera is off (third person) or the option is off. The option is active only in the head-camera view and was tested from a cold start (PS5 Pro, firmware 12.40).
- **Lock-on aim** is a first iteration: it aims at the target's lock point from the head. Close to an enemy while strafing the view can twitch; the aim offset persists after releasing the lock until you turn the camera.
- **Death camera:** the view is the head's view, so it can end up lying on its side or looking at a wall at an odd roll angle - that is the point of the effect, but it can be disorienting. The camera is kept 0.30 m above the feet (`DFLOOR`, live-tunable); on strongly sloped ground it can still dip into geometry. Death is detected from the HP field `[[pl+0x3b0]+0x20]+0xf8` (HP <= 0); other game states that zero the HP momentarily would trigger it too. Tested on a PS5 Pro with a death by falling and with HP set to 0 by a debugger, with the build applied to a running game; a cold-start test of this exact build is still pending.
- **Death slow motion** hooks the same instruction (`0x1E196BB`) as a stock "Player's Speed x2" cheat found in older community cheat lists for this game; do not enable both (the last one written wins, and switching either off restores the original instruction, which removes the other). The stock cheat's player check reads an address that is zero on this setup, so it does nothing here anyway. Only characters are slowed: effects such as cloth, blood particles and the camera smoothing run in real time. The game's death sequence (text, fade, unload) runs partly on game time, so a profile that runs the death much faster or slower than normal changes when those parts arrive. Developed and tested live on a PS5 Pro with deaths by enemies, falls and HP written to 0.
- **Killer camera** picks the nearest living character when the player was not locked on, which is usually, but not always, the one that struck the last blow. It reads the character list of the game's WorldChrMan (`+0x1490`); if that layout does not match your game version the option does nothing and the head-following death camera is used. Tested live on a PS5 Pro; a cold-start test of this build is still pending.
- **Close-character guard:** when the camera gets within 0.5 m of a living character's torso point the game's normal camera is used for a moment (visceral attacks, very close hugging of a large enemy). If that happens too often for your taste lower `NEARR2` (0 disables the guard, then the camera can end up inside the enemy during visceral attacks).
- **Silhouette spin when backpedalling starts:** the game plays a turning animation that rotates the body in front of the camera for a moment (only visible with "body faces the view").
- **Cutscenes and scripted cameras:** the head camera only replaces the position when the head is within a sane distance of the game's own camera, so most cutscenes play normally, but unusual scripted cameras were not exhaustively tested.
- **Toggling:** the camera can be switched off and on at any time (double-click the touchpad, or the cheat menu). If something looks wrong, that resets it. Each touchpad click also opens/closes the game's personal-effects (gesture) menu for a moment.
- **Animation rate:** where the game updates animation at 30 Hz the head bobbing is interpolated; it is smooth but follows the animation, not the display refresh.

## VRR tools (`tools/vrr`)

* **Black screen for a second or two** when the game starts (the HDMI output switches to VRR) and again briefly when it is closed. Expected.
* **48 FPS floor.** The VRR window is 48-60 Hz. Below 48 FPS the display leaves it, the refresh readout jumps and flicker is possible on some panels. Keep `fps_cap.py` caps at 48 or more.
* **Not persistent.** ps5debug and `vrr_watch.py` must be started again after every console restart, and `vrr_watch.py` must be running **before** the game starts (otherwise use `avctl_attr.py set` and press the PS button and go back to the game).
* **Writes into a system process** (`SceSysAvControl.elf`). Narrow and reversible, but at your own risk; a console restart clears everything. Never read system-library code inside the game process (execute-only memory, can crash the game).
* **Save data was once flagged broken during the test session** (no debugger attached, cause unknown, not shown to be related to these tools; a later 29-minute VRR session with 237 save mounts and a 12-minute control session without VRR did not repeat it, but the VRR session logged three transient mount errors that recovered on retry, see [vrr.md](vrr.md#save-data-during-the-tests)). Back up the save data before use; if the game reports "The save data is corrupted", choose **NO**, close the game and clear the `is_broken` flag as described in the section above about debuggers.
* **Firmware 12.40 only** (tested). On other firmware the table window of `vrr_watch.py` may differ; the tool warns instead of writing blindly.
* **No 120 Hz**, and `fps_cap.py` works only for Bloodborne v1.09 with the 60 FPS mod on. Other PS4 games, other displays and a base PS5 are untested.

## Not supported / out of scope

- Anything online. Use the mods offline.
- Game assets or save editing: this repository has none.
