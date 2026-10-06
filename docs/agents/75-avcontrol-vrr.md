# 75 - The system video service (SceSysAvControl), VRR for PS4 games, and the frame timer

> **Tested only on system software 12.40 with a PS5 Pro, Bloodborne `CUSA03173` v01.09 and one HDMI display (1080p, FreeSync Premium, console-reported VRR range 48-240 Hz).** Addresses below are for that firmware and game. Do not extrapolate. Confidence levels as in [registry.json](registry.json): **confirmed-live** (observed or written on the running console), **inferred**, **static-only** (seen only in the disassembly or strings of a memory dump).

User-level description: [../vrr.md](../vrr.md). Tools: [../../tools/vrr](../../tools/vrr/README.md).

## 1. What this file covers

1. **SceSysAvControl.elf**: the system service that decides the HDMI output mode. It keeps a per-app capability record (`attr`). Setting one bit of that record for a PS4 game makes the console drive the display with VRR 60 Hz (48-60 Hz). Confirmed-live.
2. The **frame timer** of Bloodborne, which the shipped `fps_cap.py` patches, and an **unlock experiment** (vsync off) that is not shipped.
3. How **120 Hz VRR** (1080p, link `1080P_11988`) was reached with a three-part code patch (section 4b), what did not work before it, and the ideas that follow.

## 2. Reading and writing the service

* The process is listed by ps5debug as `SceSysAvControl.elf`. Its memory can be read with the normal ps5debug read command (confirmed-live): text `0x400000-0x4ac000` (688 KB, prot r-x), read-only data `0x4ac000-0x4ec000`, data/bss `0x4ec000-0x560000`, plus the shared-memory mapping `/SceAvControl` (16 KB at `0x200044000` in the tested session).
* A 1.4 MB dump of `0x400000-0x560000` is enough for static analysis with capstone (the log format strings give every function a name; find the strings, then the `lea reg, [rip+disp]` references). **Do not commit such dumps** (system software).
* Writes with the ps5debug write command worked (confirmed-live) for single dwords. Keep them narrow and verify by reading back.
* The service writes to the console kernel log (visible on the log server, TCP 3232 in the dev setup): `[AvControl] ...` lines. Capture the log before you launch the game.
* **Hazard:** a wrong value in a system process may confuse the video pipeline until the console is restarted. **Never read the code of system libraries inside the game process** (`libSceVideoOut.sprx`, `libSceAvSetting.sprx` are mapped there): it is execute-only memory and reading it from the game can crash the game (see [10-memory-map.md](10-memory-map.md) and the XOM lesson in [30](30-code-cave-playbook.md)).

## 3. The capability record ("attr")

Log line printed at app launch / suspend / resume (function `0x42ebc0`):

```
[AvControl] -- app[0](appid=0xe018 attr=0x82e0057)(GAME RUNNING)(HDR:x HFR:x VR:x VRR:x 8K:x) SpecialModeInBg(none) HDCP23(none) supInfo(0x0)
```

Every PS4 game seen (Bloodborne, two app ids) had `attr = 0x082E0057`. A new session is logged as `New session(appid=0x.. pid=0x..) system:0 bc:1 attr:0x82e0057` (function `0x413de0`; it prints the value the service computed **before** an external edit).

**Table.** Entries are three dwords `{key, appid, attr}`; `key` is the process id or `0xFFFFFFFE`; each app has two entries (adjacent). The lookup is function `0x4305c0` (entries every 12 bytes, up to 32). The table exists **twice**: in the service's data (`0x4f94f4...` region in the tested session; polled window `0x4f9000-0x4fa000`) and in the shared mapping `/SceAvControl` (`0x2000447f8...`). The slot used depends on the free slot at launch. Both copies were edited together in the experiments; **which copy the mode decision reads was not isolated** (confirmed-live that editing both works). System apps appear in the same table (for example attr `0x08240057`, `0x08040057`).

**Bits** (decoded from the printer `0x42ebc0` and the composer `0x42f430`; polarity differs per flag):

| Mask | Meaning | PS4 game | Confidence |
|---|---|---|---|
| `0x00800000` | VRR supported (`VRR:TypeA`; with `0x01000000` `TypeB`) | clear | **confirmed-live** (setting it gave VRR 60) |
| `0x01000000` | VRR type B (when `0x00800000` is set) | clear | static-only (not tried) |
| `0x04000000` | "boost" (`VRR:Boost` when `0x00800000` is clear): the system's VRR for unsupported games | clear | inferred |
| `0x00040000` | HFR (120 Hz) forbidden: HFR shows `o` only when the bit is clear | set | inferred; clearing it alone changed nothing (confirmed-live negative) |
| `0x00000040` | HDR forbidden | set | static-only |
| `0x08000000` | 8K forbidden | set | static-only |
| `0x00200000` / `0x00000010` | VR related (`VR:` field) | set | static-only |
| `0x00080000` / `0x00100000` / `0x00400000` | app type GAME / MEDIA / NA_MEDIA | GAME | static-only |
| `0x00000200` | app suspended | clear while running | static-only (seen as `0x82e0257` in the suspend log line) |
| `0x00008000` | force SDR (`fSDR`) | clear | static-only |

**Where the bits come from** (static-only): `0x42f5f0` computes the record per session: it calls `0x42e710` (a title-workaround check, `sceKernelTitleWorkaroundIsEnabled` id `0x5a` "DISABLE_VRR_APPLY_TO_UNSUPPORTED_GAME", logs "vrr ApplyToUnsupported feature is disabled") and `0x42f430`, which builds the bits from the app type word `[info+0x50]`, flags `[info+0x28]`, the supplementary info word `[info+0x4c]` (bits 18-20 = VRR parameter 0/1/2/7, otherwise "unknown vrr parameter" is logged) and the BC flag. With parameter 0, `0x4000000` ("boost") is set only when the app type word is below `0x1000` and bit 0 of a cached flag is clear. Why this did not apply to Bloodborne although *Apply to Unsupported Games* was on is **not known**.

## 4. Mode enum and structure

Refresh enum (field `+0x10` of a mode request; static-only from the conversion function `0x432170` and its strings, `3` and `0x8003` confirmed-live): `3` = 59.94 Hz, `6` = 29.97 Hz, `0xd` = 119.88 Hz; **VRR = `0x8000 | enum`** (`0x8003` VRR 60, `0x800d` VRR 120). Resolution code `0xb` = 1080p (inferred from the `ready-scanin` line of a 1080p mode).

Current-mode record (confirmed-live that the `ref` dwords change): `{1, 2, col=0xd, bpp=0x24, ref, res=0xb, 0, 0}`; before the VRR edit `ref = 3`, afterwards `0x8003`. Copies in the data segment (`0x4f5590`, `0x4f57d0`), in `/SceAvControl` (`0x200044978`, `0x200044bb8`) and on stacks. A before/after diff of the whole data segment showed no other mode-related change (only app-id bookkeeping).

Log after the change (confirmed-live):

```
[AvControl] ** set_mode(0) ** -1/-1
[AvControl]  video: port:HDMI 1080P_5994 RGB444 full RGB2100_PQ 36bpp 16:9 allm-nodata o--tv-sf1
[AvControl]       : VRR(peg:60 range:48 - 60) capable(allm 1 mdelata 0 range 48 - 240) (-)
[AvControl] notify ready-scanin(idx:-1) port0(res: 0xb ref:0x8003(48-60) col:0xd sup:0x280) ...
```

The service also contains the modes `1080P_11988` (1080p 119.88 Hz) and many others as strings; a 120 Hz VRR mode exists in the code (`0x800d`, "119.88Hz request is converted to VRR 119.88Hz") but is only reached by an **app request**.

## 4b. The hardware timing id, the mapper and the 120 Hz patch

Status of this section: confirmed-live unless marked otherwise (firmware 12.40, PS5 Pro, Bloodborne, one 1080p monitor).

**Timing id.** The status printer `0x424b20` (log line `video: port:HDMI 1080P_5994 ...`) reads a qword at `[mode_record+0xc]`; byte `+0xd` is the **timing id**, an index into a name table of relative int32 offsets at `0x4dbac8`: `8` = `1080P_5994`, `0x2e` = `1080P_11988` (both confirmed-live), `0x29` / `0x2a` = `1080P_5994_VR` / `1080P_11988_VR`, `0x2c` = `720P_11988`, `0x2f` = `3840_2160P_5994`, `0x36` = `2160P_11988` (static-only). Several fixed writers exist (`mov byte [rbx+0xd], 8` in the fall-back to 1080p60 at `0x42d611`, `mov byte [rsi+0xd], 0x2f` at `0x42a8a5`), the normal path is the mapper below.

**Mapper `0x42ae50`.** Fills the hardware record from the REQUESTED mode: the resolution code `[req+0x14]` selects a branch through the jump table at `0x4dc8a0` (1080p = res `0xb` -> `0x42b102`), then the refresh enum `[req+0x10]` through the table at `0x4dccdc`. For 1080p: refresh 3 -> `mov r14d, 0x800` (id 8, `0x42bb42`), refresh `0xd` -> `mov r14d, 0x2e00` (id `0x2e`, `0x42bb37`); `r14d >> 8` becomes byte +0xd. VRR refresh values (`0x8003`, `0x800d`) are above the table range and are not seen by this branch.

**VRR converter `0x42d690`.** Runs afterwards on the same record. For refresh 3 or 9 it stores `0x8003` (`mov r8d, 0x8003` at `0x42d87c`, imm32 at `0x42d87e`), for `0xd` / `0xe` it stores `0x800d` (`0x42d927`); then `mov [r14+0x10], r8d` (`0x42d88a`), the VRR marker `or byte [rbx+4], 0x80` (`0x42d88e`), the VRR type byte `[rbx+0x18]` (1 or 2), the range (`0x30` .. `0x3c`, or `0x30` .. `0x78` for `0x800d`) and the "peg" word `[rbx+0x1e] = 0x3c` (always 60 here, also for `0x800d`). It does **not** touch byte +0xd. It writes only when the service allowed VRR for the app (register `sil` clear; depends on the attr bit), which is why apps without the bit are unaffected. The comparer `0x432170` (requested vs. actual mode) only has a VRR equivalence for 8K at refresh 3 (`0x8003`), so 1080p VRR 60 already counted as a mismatch before the patch without visible harm (inferred).

**Consequence.** Changing only the VRR enum (3 -> `0x800d`, P1) printed `VRR(peg:60 range:48 - 120)` and `ref:0x800d(48-120)`, but the link stayed `1080P_5994` and the monitor stayed at 60 Hz: the timing id is chosen before the conversion from the unconverted request.

**The patch (shipped as `tools/vrr/vrr120_patch.py`).** P1 imm32 `0x42d87e` `0x8003` -> `0x800d`. P2 code cave at `0x4a2844` (60 bytes of `int3` padding, 32 used): `or byte [rbx+4],0x80 ; cmp r8d,0x800d ; jne L ; cmp dword [r14+0x14],0xb ; jne L ; mov byte [rbx+0xd],0x2e ; L: mov r12d,r11d ; jmp 0x42d895`. P3 at `0x42d88e` (7 bytes): `jmp 0x4a2844 ; nop`, replacing `or byte [rbx+4],0x80 ; mov r12d,r11d` (both re-executed by P2). The cave only changes the id when the converted refresh is `0x800d` AND the request resolution is 1080p (`0xb`), so other resolutions keep their timing (their `0x800d` handling is untested). Apply order P1, P2, P3; restore order P3, P2, P1. `vrr_watch.py --hz120` sets the attr to `0x08AA0057` (VRR bit set, HFR-forbidden bit `0x00040000` cleared).

## 5. Experiments (see also [80](80-experiments-log.md))

| # | Procedure | Outcome |
|---|---|---|
| V1 | Game limited to 45 and 30 FPS with vsync on, watch the monitor's refresh readout and the log | readout stayed 60; no ALLM/VRR event in the log: no VRR for the PS4 game with *Apply to Unsupported Games* on |
| V2 | Find the table in the service memory (scan for `{appid, 0x082e0057}`), write `attr = 0x082e0057` (same value) | writes to the service work, system stable |
| V3 | `attr = 0x08ae0057` (VRR bit) with the game at a 55 FPS cap, then Home and back to the game | `set_mode`, `VRR(peg:60 range:48 - 60)`, `ref:0x8003(48-60)`; monitor readout followed 55 Hz, smooth; no game restart needed. At 45 FPS the readout jumped (below 48) |
| V4 | `attr = 0x08aa0057` (VRR + HFR allowed), Home and back | **no** `set_mode`, mode unchanged: HFR permission alone does not select 120 Hz, because the game requests no mode |
| V5 | A watcher that rewrites new entries at 50 Hz (`vrr_watch.py`), then launch the game | the log shows `attr=0x8ae0057 ... VRR:TypeA` for the new app, then `set_mode` and VRR 48-60 at launch; black screen for a second or two. The watcher also rewrote the entries of a second Bloodborne app id that was launched first by mistake (its video mode was not examined) |
| V6 | Closing the game | black for a moment, output back to 59.94 Hz (the entry disappears) |

| V8 | Save-data log analysis of a session that ended with `is_broken = 1` (no debugger) | first failure mid-session: mount+umount ok, then `0x809f8057`, then `0x809f8709` on the immediate retry; the save image was last written at that moment; cause not found (suspects: a second app with the same save directory started earlier, rapid autosaves, live writes, HDMI mode switches) |
| V9 | 29-minute VRR session with the shipped watcher, autosave-heavy play, monitor power-cycled twice, Home screen / library trips | 237 mounts, 3 x `0x809f805d` (PFS mount ok + unmount, call returns the error, the next call succeeds), flag stayed 0, VRR re-established after every HDMI reconnect |
| V10 | Control session without VRR or tools, about 12 minutes | 157 mounts, 0 errors, flag 0 |
| V11 | App suspend duration with and without VRR | with VRR `Completed suspending ... (1829-1854 msec)` (the output returns to 59.94 Hz, `POST_SUSPEND elapse ~1.75 s`), without 77-84 ms (four measurements). Going to the Home screen / game library from a game does not suspend it and does not trigger `set_mode` |

| V12 | `attr = 0x8aa0057` and only P1 (VRR enum `0x800d`), game launched with the watcher running | log `ref:0x800d(48-120)` but link `1080P_5994` (`VRR(peg:60 range:48 - 120)` printed); monitor stayed at 60 Hz; a vsync-on cap of 90 FPS stayed at 59 FPS; vsync off at 100 FPS on this link was not smooth |
| V13 | P1 + P2 + P3 applied with the game closed, watcher `--hz120`, game launched | `video: port:HDMI 1080P_11988 ... VRR(peg:60 range:48 - 120)`, `ref:0x800d(48-120)`; `fps_cap.py set 100` with vsync on: 99.3 FPS, median 10.00 ms, stdev 0.00 ms, no hitches in 3 s; picture judged smooth by eye |
| V14 | same, cap 110 | 106.0 FPS, median 9.09 ms, stdev 0.73 ms, 2 hitches in about 330 frames (0.6 %): 1080p is GPU-bound at about 106-111 FPS in the tested scene |

Method note: the monitor's refresh readout is the cheap, independent confirmation; the `VRR(peg ... range ...)` log line is the console's side.

### Save-data observations (read this before repeating the tests)

* The save data (installDir `CUSA00207`, dir `SPRJ0005`) is shared by the licensed Bloodborne and the fpkg GOTY (the same installDir): starting the licensed app on a save of the other flavour gives a mount error (`0x809f805d`) and the "corrupted" prompt (answer NO).
* Log signatures: `[libSceSaveData] api_id: 1 ... mountMode=0x0a` is a mount, `Mounted >` a successful one, `GetResult : ExecResult : 0x809f....` an error. `0x809f8709` is the broken state; once the system flag `is_broken = 1` exists in `/system_data/savedata/<userid>/db/user/savedata.db` every mount fails. Clear it with the game closed, as described in [known-issues.md](../known-issues.md).
* Transient `0x809f805d` errors (mount ok, unmount, error, next attempt ok) occurred 3 times in 237 mounts during a VRR session and never in 157 mounts without VRR; the only broken-save event happened in a VRR session, where the first error was `0x809f8057` and the retry failed too. **Not enough data for a causal claim.** Always back up `sdimg_SPRJ0005`, `SPRJ0005.bin` and `savedata.db` before a session.
* **Second incident (no VRR tool, no system-process write):** in a development session a 30 s scan of all writable mappings of the running game with `proc_read` (a dev tool searching for item ids) coincided, within the log's time resolution, with the first failed mount (`0x809f8057`, then `0x809f8709` on every retry; the save image and the database mtime were last written at that moment). Weapon, attribute and camera edits made in that session came after it or were followed by 28 successful saves. Treat reading the whole memory of the running game while saves may be written as a suspect, independent of VRR. Two later sessions with the VRR tools active (one on the 120 Hz link) and without such a scan did not flag the save (112 mounts, no errors).
* The console clock ran about 11 minutes ahead of the helper host in the tests; correlate log times with a known event (for example `Big App started`).

## 6. The frame timer (used by `fps_cap.py`)

All Bloodborne v01.09, confirmed-live unless noted.

| Address | What |
|---|---|
| `0x59404F8` | global pointer to the frame-timer object |
| `0x2434770` | `FrameTimer::Update` (static-only for the full structure) |
| `[obj+0x18]` | target frame time (float seconds); **rewritten every frame** from a code immediate of the mode switch in `Update` (`0x243485A`, `0x243487E`, `0x2434840`, `0x24348B3`), so a data write is undone within a frame (0.3 ms measured) |
| `0x2434883` | the imm32 behind `mov dword [r12+0x18], imm32` for the default mode: `3c888889` = 1/60 s with the 60 FPS mod, `3d088889` = 1/30 s in the stock game. Patching it changes the software limiter |
| `[obj+0x260]` | ring index, steps once per frame (mod 32) |
| `[obj+0x60 + i*16]` | ring of the last 32 frame durations (u64 microseconds + flag byte); reading the whole ring every 50 ms yields every frame |
| `[obj+0x264]` | measured duration of the last frame (float seconds); the 60 FPS mod replaces several hard-coded 1/30 s constants with it |
| `[obj+0x28]` | current timestamp in microseconds; **also rewritten inside the limiter's wait loop**, do not use it to count frames |
| `[obj+0x26c]` | averaging window (30 stock, 1 with the 60 FPS mod) |

The limiter waits until the frame is `target` long (sleeps while more than 5 ms remain, then spins). **Lowering the target alone does not raise the frame rate**: with vsync on the game is locked to the display refresh (16.68 ms at 59.94 Hz); raising the target to a larger value caps the rate, which is what `fps_cap.py` does.

### Unlock experiment (not shipped, shown for completeness)

The present path (`Present` at `0x2AD6E50`, wrapper `0x25B2FB0`) passes an interval to the flip: interval 0 selects an immediate (HSYNC) flip instead of a vsync flip. Patching `0x25B3271` (`44 89 e6` -> `48 31 f6`, `xor rsi, rsi`) together with the limiter immediate (target 1 ms or 1/120 s) raised the frame rate from 60 to about 110-140 FPS depending on the render resolution, and the game speed stayed correct (running speed measured 3.99 m/s versus 3.97 m/s). **The display stayed at 60 Hz** (its refresh readout did not move), so the extra frames only showed up as tearing; the result was not smooth. A cap of 120 FPS gave a steady 8.33 ms frame time but the same tearing. This is why `fps_cap.py` refuses to run while the vsync site is modified.

## 7. Open questions and ideas

| # | Idea | First probe |
|---|---|---|
| V-A | **DONE (see section 4b, V13)** - 120 Hz (VRR 48-120) for a 1080p PS4 game. Original idea: | the game sends no output-mode request. Build a synthetic request for `ref = 0xd` / `0x800d`, `res = 0xb` on behalf of the game: either find where the service stores the app's requested mode (IPC handler `0x443e40`, request handler `0x40ccb0`, validator `0x432170`) and write it there, or call the equivalent output-mode API from inside the game process (the video libraries are mapped there; their code is XOM, never read it - resolve exports by name hashes instead) |
| V-B | The boost bit `0x04000000` instead of `0x00800000` | try it with the same procedure; it may be what the system sets for unsupported games and might include a low-frame-rate path |
| V-C | A persistent implementation | react to the app-launch event inside the console-side payload (onionHEN has a lifecycle event for the big app start) and write the same dwords with its kernel read/write primitives; removes the host computer |
| V-D | Why *Apply to Unsupported Games* does not engage for Bloodborne | read the app type word `[info+0x50]` and the cached flag the composer receives for this title; compare with a PS4 game for which the system option works |
| V-E | Other games, other displays/TVs, base PS5 | repeat V1-V5; record the log lines |
| V-G | Other resolutions at 120 Hz (the cave handles 1080p only; the mapper has its own ids per resolution, e.g. `0x36` 2160P_11988) and other PS4 games / displays | extend the cave per resolution and check the link line and the monitor readout |
| V-H | A persistent patch without the host computer | the console-side payload (onionHEN) could write the same bytes at the app-launch event instead of ps5debug |
| V-F | Behaviour below 48 FPS (low-framerate compensation) | the 48-60 window cannot double frames; measure what the console and the display do |
