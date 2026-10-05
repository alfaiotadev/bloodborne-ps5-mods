# VRR for PS4 games - host tools

Three small Python 3 tools that make the PS5 drive an HDMI-VRR display in **variable refresh rate (48-60 Hz)** while a **PS4 (backward-compatible) game** runs. They talk to the console through the **ps5debug** payload, like the tools in [`../dev`](../dev/README.md), and they reuse its `core/ps5dbg.py` client. Full explanation, safety notes and results: [`../../docs/vrr.md`](../../docs/vrr.md).

> **Back up your save data first** (see [`docs/vrr.md`](../../docs/vrr.md#safety): the save was once flagged broken during the test session, cause unknown).
>
> **Tested only on system software 12.40, a PS5 Pro and Bloodborne.** Other games, firmware versions, consoles and displays are untested. The tools write into a **system process** (`SceSysAvControl.elf`), narrowly, but use them at your own risk, on your own console.

| Tool | What it does |
|---|---|
| [`vrr_watch.py`](vrr_watch.py) | Start it **before** the game. It watches the system's per-app capability table and, as soon as a PS4 game appears, sets the "VRR supported" bit so the console switches the HDMI output to VRR 60 Hz when the game starts. |
| [`fps_cap.py`](fps_cap.py) | Caps Bloodborne at a frame rate inside the VRR window (for example 55 FPS) so the display refresh visibly follows the game. Bloodborne v1.09 with the 60 FPS mod only. |
| [`avctl_attr.py`](avctl_attr.py) | Manual `scan` / `set` / `restore` of the capability record, for experiments. |

## Quick start

```sh
export PS5_HOST=<console ip address>        # the ps5debug payload must be running (TCP 744)
python3 tools/vrr/vrr_watch.py &            # 1. leave this running, then start the PS4 game
                                            # 2. the screen goes black for a second or two at launch (HDMI mode change)
python3 tools/vrr/fps_cap.py set 55         # 3. once in game: cap at 55 FPS (48..60 stays inside the VRR window)
python3 tools/vrr/fps_cap.py off            #    back to the normal 60 FPS cap
```

Stopping `vrr_watch.py` (Ctrl-C) or closing the game ends everything; nothing is stored on the console. After a console restart load ps5debug again and restart the watcher.

Requirements: Python 3.8+, the ps5debug payload on the console, a display that supports HDMI VRR (the console must report it under *Settings > Screen and Video > Video Output > Information for the Connected HDMI Device*), and the PS5 settings *VRR: Automatic* and *ALLM: Automatic*. Environment variables are the same as for the dev tools (`PS5_HOST` required, `PS5_DEBUG_PORT`, `PS5_WORKDIR`).
