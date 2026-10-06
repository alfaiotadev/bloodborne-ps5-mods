# VRR for PS4 games on the PS5 (48-60 Hz, optionally 48-120 Hz)

> **Tested only on system software 12.40 with a PS5 Pro, one game (Bloodborne GOTY `CUSA03173` v01.09) and one display.** Other games, other consoles (base PS5, Slim, Digital), other firmware versions and other displays are **untested**. Do not assume the results carry over. See [compatibility.md](compatibility.md).

## In short

On a PS5, PS4 games run in backward-compatibility (BC) mode. In the tested setup Bloodborne was sent to the display at a fixed 59.94 Hz even though the PS5 setting *Apply to Unsupported Games* was on. With the tools in [`tools/vrr`](../tools/vrr/README.md) the console switches the HDMI link to **VRR with a 48-60 Hz range** when the game starts, and the display refresh then follows the game's frame rate (a game capped at 55 FPS is shown at 55 Hz instead of being judged against a fixed 60 Hz clock).

* It needs a **host computer** (any machine with Python 3 that can reach the console) running `vrr_watch.py`, and the **ps5debug** payload on the console. Nothing is installed permanently: closing the game or restarting the console removes it.
* With the plain tool the VRR window is 48-60 Hz. The optional second tool `vrr120_patch.py` raises it to **48-120 Hz** on a 119.88 Hz link (1080p); it patches code in a system process, see [120 Hz](#120-hz-optional-more-invasive).
* It is **not** a cheat in the in-game menu. It changes the console's video mode decision, not the game.

## What was observed

Setup: PS5 Pro, firmware 12.40, HDMI to a 1080p FreeSync Premium monitor that the console reported as VRR-capable (range 48-240 Hz) and ALLM-capable; PS5 settings *VRR*, *120 Hz output* and *ALLM* on **Automatic**, *Apply to Unsupported Games* **on**. Bloodborne with the 60 FPS mod.

1. **Without the tools** the monitor's refresh readout stayed at 60 Hz when the game was limited to 45 and to 30 FPS, and the console log showed no ALLM or VRR event at launch: the game was not driven with VRR, although *Apply to Unsupported Games* was on. The capability record of the game in the system video service read `attr=0x82e0057` with `VRR:x`.
2. **With the "VRR supported" bit set** (`attr=0x8ae0057`, `VRR:TypeA`) the video service re-evaluated the output and logged:

   ```
   ** set_mode(0) **
    video: port:HDMI 1080P_5994 RGB444 full RGB2100_PQ 36bpp 16:9 allm-nodata ...
         : VRR(peg:60 range:48 - 60) capable(allm 1 mdelata 0 range 48 - 240)
   notify ready-scanin ... port0(res: 0xb ref:0x8003(48-60) ...)
   ```

   i.e. the mode became **VRR 60 Hz (48-60)**. With the game limited to 55 FPS the monitor's refresh readout followed it at 55 Hz and the picture was described as smooth. At 45 FPS (below the 48 Hz floor) the readout jumped around.
3. Started **before** the game (the `vrr_watch.py` way) the bit is set during the launch, before the mode is chosen, so no Home-button round trip and no game restart is needed. The screen goes black for a second or two at launch (the HDMI mode change) and again, briefly, when the game is closed and the output returns to 59.94 Hz.

### Save data during the tests

The save-data behaviour was watched in the console log (every `sceSaveDataMount` result) and in the system database flag, because two sessions ended with the save flagged as broken (see [Safety](#safety)); only the first of them involved a VRR tool.

| Session | Length | Save mounts | Mount errors | Save flagged broken |
|---|---|---|---|---|
| First VRR test session (VRR via the watcher, many manual experiments, monitor power-cycled once, Home-button round trips) | about 10 minutes until the failure | about 40 | `0x809f8057` then, on the immediate retry, `0x809f8709` | **yes** (cause not found) |
| Second VRR test session (the shipped `vrr_watch.py`, a 55 FPS cap, teleports, deaths, the monitor power-cycled twice, trips to the Home screen and the game library) | 29 minutes | 237 | 3 x `0x809f805d`, each fixed by the very next attempt | no, also not after closing the game |
| Control session (no VRR, no tools) | about 12 minutes | 157 | 0 | no |
| Development session **without any VRR tool** (live memory edits of the game, camera and frame-limiter writes, one 30 s whole-memory scan of the game with a dev tool) | not known (the log capture started during the session) | 37 logged before the failure | first failure `0x809f8057`, then `0x809f8709` on every retry (same signature as the first incident), in the same seconds as the whole-memory scan | **yes** |
| The next two sessions (VRR tools active: 21 minutes with the first 120 Hz attempt, link still at 59.94 Hz, then 12 minutes with the 120 Hz link; frame-limiter writes; no whole-memory scan) | 33 minutes together | 112 together | none | no |

The `0x809f805d` errors look like this in the log: a PFS mount succeeds and is unmounted at once, the call returns `0x809f805d`, and the next call succeeds. In the failing session the first error was followed by a second failed attempt, and that one flagged the save. 3 errors in 237 mounts with VRR against 0 in 157 without is **too small a sample to say whether VRR changes anything**. Going to the Home screen or the game library from a VRR session does not suspend the game and does not change the HDMI mode; an actual app suspend takes about 1.8 s with VRR (log: `Completed suspending ... (1829-1854 msec)`) against about 80 ms without it (four measurements), because the output returns to 59.94 Hz.

Not measured: other games, other displays or TVs, base PS5 behaviour, input latency, how the console treats games below 48 FPS.

## 120 Hz (optional, more invasive)

With only the "VRR supported" bit the link is **1080p 59.94 Hz with a 48-60 Hz VRR range**: the display never runs faster than 60 Hz, so a game that renders faster than 60 FPS only tears. The optional patch `tools/vrr/vrr120_patch.py` makes the link **1080p 119.88 Hz (HDMI timing `1080P_11988`) with a 48-120 Hz VRR range** for a 1080p PS4 game, so the game can run above 60 FPS with vsync on and the display follows it. It **writes code** into the system video service, which is why it is separate and optional.

**What was observed** (same setup as above, Bloodborne, 1080p, `vrr_watch.py --hz120` running before the game, patch applied while the game was closed):

* Console log: `video: port:HDMI 1080P_11988 ...`, `VRR(peg:60 range:48 - 120)` and `notify ready-scanin ... ref:0x800d(48-120)` (with the plain VRR bit it was `1080P_5994` and `ref:0x8003(48-60)`).
* With `fps_cap.py set 100` (vsync stays on): measured 99.3 FPS, median frame time 10.00 ms, standard deviation 0.00 ms, no hitches over the 3 s measurement; the picture was judged smooth by eye. With a cap of 110 the game reached 106 FPS (1080p is GPU-bound in the tested scene, about 106-111 FPS uncapped) with 0.6 % hitches. The monitor's own refresh readout followed the frame-rate counter of the onionHEN overlay closely at these frame rates (it updates every frame, so it is hard to read when the frame time jitters); at a 60 FPS game it flickered between 59 and 61 Hz.
* Before the patch, the same frame rates on the 60 Hz link were not smooth: with vsync on a cap above 60 changes nothing (the game stays locked to 59.94 Hz), and with vsync off 99 FPS only tears.
* Temperatures (the maintainer's reading from the console overlay, not a measurement series): about 40 C for CPU and GPU at the normal 60 FPS, about 50 C (CPU) and 45 C (GPU) at 100-110 FPS; higher frame rates mean more work per second, so a rise is expected.
* Why it matters: lowering the render resolution is no longer needed to get above 60 FPS on a 60 Hz link. The game can stay at its native 1080p; the console's frame rate is then limited by the GPU. Because even the PS5 Pro is near its limit at 1080p (about 106-111 FPS), the frame rate varies and a fixed 120 Hz refresh would not present it evenly either; the VRR range up to 120 Hz is what lets the display follow. Measurements are from the PS5 Pro only; a base PS5 is untested and may reach less.

**How it works.** The service chooses the HDMI timing from the *requested* refresh enum (a table index in byte +0xd of its hardware mode record: `8` = `1080P_5994`, `0x2e` = `1080P_11988`) before it converts the request to VRR (`0x8003` = VRR 59.94, `0x800d` = VRR 119.88). Changing only the VRR enum therefore raised the bookkeeping range to 48-120 Hz but left the link at 59.94 Hz and the display at 60 Hz. The patch has three parts: P1 changes the VRR conversion of refresh 3/9 to `0x800d`; P2 is a 32-byte code cave in padding that sets the timing index to `0x2e` when the converted refresh is `0x800d` and the resolution is 1080p; P3 is a 7-byte jump to P2. The conversion only runs for apps the service allows VRR for (the attr bit set by `vrr_watch.py`), so other apps are not affected. `vrr_watch.py --hz120` writes `0x08AA0057` (VRR supported, HFR allowed) instead of `0x08AE0057`. Addresses, the table and the analysis: [agents/75-avcontrol-vrr.md](agents/75-avcontrol-vrr.md).

**Usage.** With the game closed: `python3 tools/vrr/vrr120_patch.py plan` (writes nothing), then `apply`; start `python3 tools/vrr/vrr_watch.py --hz120`, then the game; in game `python3 tools/vrr/fps_cap.py set 100` (up to 118). `python3 tools/vrr/vrr120_patch.py restore` puts the original bytes back; a console restart clears the patch too. Apply it again after every console restart. Every original byte is verified before writing; on another firmware nothing is written.

**Risk.** It is a code patch in a system process on a console you own, tested on one firmware and one display. A wrong patch can confuse the video pipeline until the console is restarted. Read [Safety](#safety) first and back up your save data.

## How to use it

1. Prepare the console as for the other live tools: the **ps5debug** payload running (TCP 744, see [tools/dev/README.md](../tools/dev/README.md)). Do not attach a debugger (see [known-issues.md](known-issues.md)).
2. On the host:

   ```sh
   export PS5_HOST=<console ip address>
   python3 tools/vrr/vrr_watch.py
   ```

   It prints `connected to SceSysAvControl.elf` and then waits.
3. **Start the PS4 game.** The watcher logs `session appid=0x...: attr 0x082E0057 -> 0x08AE0057`; the screen goes black for a second or two while the HDMI mode changes.
4. Optional, Bloodborne only: `python3 tools/vrr/fps_cap.py set 55` caps the game inside the VRR window so that the refresh visibly follows it; `fps_cap.py off` restores 60 FPS. The cap needs the 60 FPS mod (the tool refuses otherwise) and is removed when the game closes.
5. Close the game normally. Stop the watcher with Ctrl-C when you are done (it can stay running for several games).

How to confirm that VRR is active: the monitor's own refresh-rate or VRR indicator (if it has one), or the system log line `VRR(peg:60 range:48 - 60)` (the console's kernel log is available on the log server port 3232 of the dev setup).

Keep a frame rate of **48 FPS or more**. Below 48 the display leaves its VRR window; the readout then jumps and flicker is possible on some panels. A game that runs at a fixed 60 FPS gains nothing from VRR (the point is variable frame times between 48 and 60).

## How it works

The system video service `SceSysAvControl.elf` keeps a small **capability record ("attr")** for every running app, one 32-bit word. For PS4 games it is always `0x082E0057`. The bits that matter here. Their meaning was decoded from the service's own log printer and mode code; **only the VRR bit (`0x00800000`) was exercised by experiment**, the others are inferred and not verified:

| Bit | Meaning | PS4 game |
|---|---|---|
| `0x00800000` | app supports VRR (shown as `VRR:TypeA`; with `0x01000000` also set, `TypeB`) | clear |
| `0x04000000` | "boost" (inferred: the system's VRR for unsupported games) | clear |
| `0x00040000` | HFR (high frame rate, 120 Hz) **forbidden** | set |
| `0x00000040` | HDR forbidden | set |
| `0x08000000` | 8K forbidden | set |
| `0x00080000` / `0x00000200` | app type "game" / app is suspended | game |

When the video owner switches to a new app, the service computes the output mode from the system default (1080p 59.94 Hz here) and the app's record; with the VRR bit set the refresh enum becomes `0x8003` (the VRR flag `0x8000` OR'd on the 59.94 Hz enum `3`) and the HDMI output is reconfigured for VRR (the black screen). `vrr_watch.py` polls the two copies of the table (one in the service's data, one in the shared memory mapping `/SceAvControl`) and writes the bit as soon as an entry shows the PS4 default.

Technical details, addresses, the mode structure and the experiment log: [agents/75-avcontrol-vrr.md](agents/75-avcontrol-vrr.md).

## Is this specific to Bloodborne?

* **`vrr_watch.py` and `vrr120_patch.py` contain nothing game-specific.** The watcher changes the capability record of every new session whose record is exactly the PS4 default (every PS4 game seen had it), and the 120 Hz patch changes the timing choice for every VRR-enabled 1080p PS4 session. In principle any backward-compatible game gets the VRR link; in practice **only Bloodborne was tested** (two app ids of the same game). Whether other games, or games at other output resolutions, behave is unknown.
* **A VRR link only helps a game whose frame rate varies or exceeds 60 FPS.** Most PS4 games lock their frame rate to 30 or 60 FPS in their own frame limiter, so there is nothing for the display to follow, and exceeding 60 FPS needs a game-specific change of that limiter (for Bloodborne: the community 60 FPS patch plus `fps_cap.py`).
* **`fps_cap.py` is Bloodborne-specific** (v01.09 addresses, and it refuses to run without the 60 FPS mod).
* **Everything is firmware-specific:** the addresses are for system software 12.40; the tools check them and refuse or warn on another build.

## Safety

* The tools **read and write memory of a system process**. Reading it with ps5debug worked without problems. The writes are narrow (a 32-bit field in entries that hold exactly the PS4 default; `avctl_attr.py set` only touches the dwords its own scan found), but an unexpected value could confuse the video pipeline until the console is restarted. Use them at your own risk, on your own console.
* **The 120 Hz patch writes code** (a 5-byte jump, a 32-byte cave in padding, and a 4-byte immediate) into `SceSysAvControl.elf`. `vrr120_patch.py` checks that the bytes match the firmware 12.40 build before writing anything, verifies every write and can restore the originals, but only a console restart is a guaranteed reset.
* **A save-data incident happened during testing.** In the session in which these tools were developed the console once flagged the game's save data as broken (`is_broken = 1`) in the middle of play, with **no debugger attached**. The cause was **not found** and was **not shown to be related** to these tools; other suspects are a second Bloodborne app that shares the same save directory and was started by mistake, and many rapid autosaves around Home-button presses. **A second incident** with the same log signature happened later in a session in which **no VRR tool was running and nothing in a system process was written**, in the same seconds as a 30-second read of the running game's whole writable memory through ps5debug (a dev tool scanning for item ids); the edits made to the game's memory in that session (a weapon, attributes, camera values) either came after the first failed mount or were followed by many successful saves, so they do not explain the first failure. Reading the whole memory of the running game while saves may be written is therefore a suspect, independent of VRR. Clearing the flag fixed both (see [known-issues.md](known-issues.md)). **Back up the save data (`sdimg_*`, the `.bin` file and `savedata.db`) before you use these tools**, and treat them as a risk until more testing has been done. The later test sessions (237 and 157 save mounts, see above) did not repeat it, which is not a proof of safety.
* Nothing is persistent: the entry exists only while the game runs, and a console restart clears every change.
* Never read the code of **system libraries** (`libSceVideoOut.sprx` etc.) inside the game process: it is execute-only memory and reading it can crash the game.
* Do not close the game while a ps5debug debugger is attached ([known-issues.md](known-issues.md)). The VRR tools never attach a debugger.

## Limits

* **120 Hz needs the code patch and works for 1080p only.** Bloodborne never asks the system for a video mode (the log shows `VideoOut: shared` and no output-mode requests), so the mode stays the system default; allowing HFR (clearing `0x00040000`, `attr=0x8aa0057`) alone did not change it, the timing choice had to be patched (see [120 Hz](#120-hz-optional-more-invasive)). Other resolutions are not covered by the patch and untested; other PS4 games were not checked.
* **Not persistent and needs a host.** After every console restart ps5debug and `vrr_watch.py` have to be started again. A cleaner solution would live in the console-side payload (onionHEN) and react to the app launch event; not implemented.
* **Firmware specific.** The built-in table window of `vrr_watch.py` is for firmware 12.40. The tool checks the window and warns when it does not look like the table; use `avctl_attr.py scan` while a PS4 game runs to find the entries on another firmware, and pass the window with `--window`.
* **Only the PS4 default value is touched.** PS5 games and system apps are left alone.
* The built-in PS5 option *Apply to Unsupported Games* did not engage for Bloodborne even though it was on; why is not known (the title-workaround check that can disable it logged nothing).

## Revert

If the 120 Hz patch was applied, `python3 tools/vrr/vrr120_patch.py restore` first (the game closed). Stop `vrr_watch.py` (Ctrl-C), close the game: the output returns to 59.94 Hz. If a manual edit was made with `avctl_attr.py`, `avctl_attr.py restore` writes the remembered original back. A console restart clears everything.
