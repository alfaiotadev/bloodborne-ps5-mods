# 07 - onionHEN integration

What the patch in `onionhen/onionhen-bloodborne.patch` changes in onionHEN, how the cheat JSON is
interpreted, and what limits apply to runtime toggling. onionHEN is a third-party cheat engine,
ShellUI toolbox and in-game overlay (GPL-3.0); the authors and the rest of the PS5 payload ecosystem
are credited in [`CREDITS.md`](../../CREDITS.md). This project is independent research and is not
affiliated with or endorsed by onionHEN.

> Platform: firmware 12.40, PS5 Pro, onionHEN on top of kstuff-lite ([01](01-platform-and-tooling.md)).
> The patch is a set of changes on top of upstream commit `b23ffe6` (the first working builds were
> called v0.0.13 to v0.0.15 in the lab notes).

## 1. Why a patched onionHEN

The stock engine can toggle JSON cheats from the toolbox, but the 60 FPS patch (and every camera mod)
needs more:

1. The patches must be in place **before the game runs its initialisation** (frame-rate patches).
2. A mod must be written **atomically**: a partially patched frame loop crashes the game.
3. Code pages are **execute-only (XOM)**; the engine's pre-read for its rollback snapshot failed, and
   its "code cave" fallback destroyed the page it was meant to unprotect.
4. Experiments need **a screenshot at an exact moment** and a **live status line** in the overlay.

## 2. Summary of the changes

| File (under `source/`) | Change |
|------------------------|--------|
| `util/source/cheats/memory_backends.cpp` | `mapCodeCaveCommon` made **non-destructive** (section 4) |
| `util/source/cheats/cheat_applier.cpp` | **XOM fallback** for the snapshot read (section 5) |
| `util/source/cheats/json_cheat_parser.cpp` | Optional per-mod **`"enabled": true`** (section 6) |
| `util/source/cheats/cheat_service.cpp` | **Auto-apply** of enabled mods when the session is created, game frozen (section 3) |
| `daemon/source/app_lifecycle_runtime.cpp` | New lifecycle subscriber: on `BigAppStarted` create the cheat session; background retry (section 3) |
| `shellui/src/hook_capture.cpp`, `hooked_funcs.hpp`, `prx_overlay.cpp` (2 lines in `OnRender_Hook`) | **Remote screenshot** replay (section 9) |
| `daemon/.../main.cpp`, `daemon_ops.hpp`, `libonion_fps/...`, `shellui/.../prx_overlay.cpp`, `shellui_overlay_widgets.cpp`, `shellui_types.hpp`, `onpress_overlay.cpp` | **DBG overlay group**, game memory in the RAM field, corrected CPU meter (section 10) |

## 3. Exec-time auto-apply

```
daemon lifecycle: BigAppStarted event (the game process has just been exec'd)
  -> ask the util daemon (IPC) for the runtime cheat list   -> creates the cheat session
       -> session creation: for every file / mod with "enabled": true
            SIGSTOP the game
            toggle each mod in file order (snapshot, write, read-back verify)
            SIGCONT the game
```

Details:

- **Event, not menu.** Previously a mod had to be toggled by opening the toolbox. The new
  `CheatSessionLifecycleSubscriber` (priority 50) primes the session at `BigAppStarted`. The IPC
  client is shared with other lifecycle work, so use is serialised with a mutex.
- **Retry thread.** The "which big app is running?" query can be unavailable at the event (observed:
  return code -1, session never created, no mods applied). The subscriber then starts a detached
  thread that polls every **10 ms for up to 3000 ms**, aborts if the pid exits or the running app is a
  different pid, and primes the session when the identity appears. The game is still in early start-up
  then, so this is still "exec time".
- **Freeze.** When any mod is enabled in the file, `kill(pid, SIGSTOP)` is sent before the first
  write and `SIGCONT` after the last; a failed SIGSTOP is only logged. A 128-write mod applied in about
  **23 ms**.
- **Per mod.** `entry.enabled` is cleared and `toggle()` is called, which flips it to enabled on success;
  a failure is logged with the file, the mod index and name, and the mod stays off. Other mods continue.
- **Order.** Mods apply in file order, entries inside a mod in file order. The generators rely on this
  ([02](02-code-caves-and-hooks.md#4-apply-order-and-restoring-on-off)).
- **Confirmed result:** with this pipeline the 60 FPS patch is active from the first menu on, and the
  camera/AA mods are active across loads.

## 4. Non-destructive code-cave mapping

`mapCodeCaveCommon(pid, addr, len)` is used when a page needs to be made writable/executable. The
stock implementation attached with ptrace, **`mmap`ed an anonymous page over the target page**, and
then `mprotect`ed it. The anonymous mapping **replaced the page with zeros**: all the game code in
that page vanished, and the game crashed as soon as it executed it. This single bug caused the early
"crash at start" and "crash mid-run" symptoms, which were first attributed to timing and to executable
variants.

The patched version only calls `kernel_mprotect(pid, page_start, page_len, PROT_READ | PROT_WRITE |
PROT_EXEC)` in place: the contents survive. (No ptrace attach is needed any more.)

Note on the write path: the engine's write backend (`onion_proc_copyin`, the "kdirect" backend) uses a
CR3 page-table walk plus a physical copy through the direct map, so reading and writing XOM pages
normally works without mprotect; `kernel_mprotect` is only triggered when the read or the verify
fails.

## 5. XOM fallback for the rollback snapshot

Before writing, the applier reads the bytes it is about to overwrite (the snapshot for rolling back a
failed toggle). On execute-only pages that read can fail. The patch changes the failure path:

1. Map the page RWX (`mapCodeCave`) and retry the read.
2. If that fails too and the JSON supplies `off` bytes of exactly the snapshot length, use the `off`
   bytes as the snapshot.
3. Only then abort with a "snapshot failed" status.

Together with the verify step (which also falls back to `mapCodeCave` on a failed verify) this removed
the "snapshot read failed" error seen on the 60 FPS block.

## 6. The cheat JSON format

Path on the console: `/data/OnionHEN/cheats/<TITLEID>_<VERSION>.json`, here
`CUSA03173_01.09.json`.

```json
{
  "name": "Bloodborne: Game of the Year Edition",
  "id": "CUSA03173",
  "version": "01.09",
  "process": "eboot.bin",
  "mods": [
    {
      "name": "No depth of field",
      "type": "checkbox",
      "enabled": false,
      "memory": [
        { "offset": "025D7A8B", "on": "31c090", "off": "0f95c0", "absolute": true }
      ]
    }
  ]
}
```

| Key | Level | Meaning |
|-----|-------|---------|
| `name`, `process` | file | Required strings (`process` is also copied to each mod) |
| `id`, `version` | file | Informational (they also name the file) |
| `credits` / `authors` | file | Optional string arrays |
| `mods` | file | Array of mods; mods with no memory entries are dropped |
| `name`, `description` | mod | Display name / text |
| **`enabled`** | mod | **Added by the patch.** `true` = auto-apply at game start. Absent or `false` = off until toggled; existing cheat files behave as before |
| `type` | mod | `"checkbox"`; emitted by the generators, not read by the parser code reviewed |
| `memory` | mod | Array of patches |
| `offset` | patch | Hex string. With `"absolute": true` it is the virtual address; otherwise `base + offset` with `base` = `0x400000` for `eboot.bin` |
| `on` / `off` | patch | Hex strings: the bytes to write when enabling / disabling. Both keys must be present |
| `absolute` | patch | Optional boolean. **Always `true` in this project** ([01](01-platform-and-tooling.md#3-why-cheat-json-offsets-are-absolute-virtual-addresses)) |
| `section` | patch | Optional section index for relative offsets |

Rules from the source:

- Patches apply in order; the engine writes, reads back and compares each one.
- **Overlap check:** enabling a mod whose ranges overlap an already-enabled mod (of a different
  owner) is refused with a conflict notification, except for "master code" dependencies. The
  generators verify overlap-freedom themselves.
- **Toggling off needs a non-empty `off` on every patch.** See section 11.
- `absolute` addresses skip the base entirely.

## 7. The shipped mods

The release cheat file (`cheats/CUSA03173_01.09.json`) is produced by `tools/mods/build_cheats.py`.
Default-on mods come from `tools/mods/data/base_mods.json`; the others are generated.

| Mod | Entries | On by default | Notes |
|-----|---------|---------------|-------|
| 60 FPS | 128 writes (270 bytes) | yes | Derived from Lance McDonald's patch ([credits](../../CREDITS.md)); frame-rate cap and time step, for example `0xFBC40F` (`7F 1D` -> `EB 1D`), `0x243487E` (`mov dword [r12+0x18], 0x3D088889` -> `0x3C888889`, 1/30 s -> 1/60 s), `0x2434887` (a `movabs rcx` immediate), `0x2483EC1` (`call` -> `ret`, a vsync stub), `0x2FBF178` (a thunk -> `xor rax,rax; ret`). Applied at exec time only |
| No motion blur | 1 | yes | `0x26A057B` `74 16` -> `EB 16` |
| No chromatic aberration | 1 | yes | `0x269FAA8` |
| Skip intro logos | 3 | yes | Three 4-byte string edits at `0x4D99138`, `0x4D99154`, `0x4D9916E` (`4C 00 6F 00` -> zeros) |
| Wide FOV x1.3 | 2 | no | [02](02-code-caves-and-hooks.md), [03](03-anti-aliasing-and-image-quality.md#6-field-of-view) |
| DLAA threshold 0.3 | 3 | no | [03](03-anti-aliasing-and-image-quality.md) |
| FPS head camera (core, FACE2, aim) | 13 + 1 + 1 | no | [05](05-fps-head-camera.md) |
| Anisotropic filtering 16x | 2 | no | Technically works, no measurable effect |
| No depth of field | 1 | no | Scene-dependent effect |
| DLC save requirement unlock | 1 | no | `0x23B67B3`, 8 bytes |

Lab notes (not re-verified in the current build): the 60 FPS patch changes game timing and a cutscene
of a DLC boss can soft-lock at 60 FPS (a property of the patch, not of the loader); a 120 Hz variant
was judged unstable.

## 8. Updating the payload without a reboot

The lab procedure for replacing the onionHEN ELFs while the console stays on (the ShellUI payload is
injected into ShellUI, so ShellUI has to restart):

1. Upload the new `OnionHEN.elf` to `/data/ps5_autoloader/onionHEN.elf` and the new bootstrapper to
   `/data/OnionHEN/onionhen.elf` over FTP; verify SHA-1. (On a case-insensitive host the file names
   differ only in case: keep backups under different names.)
2. **Close the game.** Send the onionHEN control port (9048) the frame `struct.pack("<II",
   0x4F4E494F, 1)` (`cmd_shutdown_onion_stack`): it kills the utility process and the private elfldr,
   **restarts SceShellUI (the display goes dark for about 5 seconds)**, and the daemon exits. kstuff
   stays loaded.
3. About 15 seconds later send `OnionHEN.elf` to elfldr (port 9021): the bootstrapper starts the daemon
   and utility and injects the fresh ShellUI payload into the new ShellUI.

Re-sending only the launcher updates the daemon but does not re-inject ShellUI ("toolbox already
active"). The original (pre-patch) build is restored by uploading the original ELFs to both paths and
rebooting.

## 9. Screenshot hook

Summarised from [04](04-scene-automation-and-measurement.md#2-screenshot-automation). In
`shellui/src/hook_capture.cpp`:

- The existing `CaptureScreen_old` / `CaptureScreen_new` hooks call `shot_cache(...)` which stores the
  instance, user id, device id, capture type, format string and capture-info object of a **real**
  press; the managed objects are pinned with GC handles. A flag keeps our own replay from
  overwriting the cache.
- `shellui_poll_screenshot_request()` runs on the UI thread every sixth frame (two lines added in
  `prx_overlay.cpp` `OnRender_Hook`). If `/system_tmp/onionhen/screenshot_request` exists it is deleted
  and the *original* capture function is called with the cached arguments; the result is written to
  `screenshot_ack` (`<epoch_ms> <status>`; 0 = called, 1 = no cached arguments, 2 = original missing).
  `screenshot_state` reports `valid=1 presses=N ...`.
- Arming = one real screenshot press after ShellUI loads. Resets with ShellUI.
- The toolbox's own screenshot shortcut (the `long_share` binding) uses the same hook and can be rebound,
  for example to L2+R3.

## 10. Overlay changes

- **DBG group.** A new overlay group (label `DBG`, salmon colour) shows text supplied by the daemon,
  from the probe file `/data/OnionHEN/debug_probes.txt` (hot-reloaded about every 5 s). One probe per
  line, `#` starts a comment:

  ```
  # <title_id> <label> <base_hex> <deref 0|1> <name:size:offset_hex>...
  # AA: YEBIS context; FXAA2 enable (+0xBBC) and temporal AA enable (+0xB8C)
  CUSA03173 AA  5865ED0 1 FX:1:BBC TA:1:B8C
  # RES: render resolution globals
  CUSA03173 RES 55289F8 0 W:4:0 H:4:4
  # GX: W/H captured by SprjGraphics at creation (differs from RES if the patch landed late)
  CUSA03173 GX  59406C8 1 W:4:F0 H:4:F4
  ```

  `deref = 1` reads the 8-byte pointer at `base` first and applies the field offsets to the pointee;
  size is 1, 2, 4 or 8; values print as unsigned decimals; the text is capped at 71 characters.
  Addresses are absolute eboot virtual addresses. This was the live instrument for the resolution and
  AA experiments (for example, `RES` versus `GX` showed when the resolution patch landed too late).
- **FPS sample.** The daemon's per-sample file (`/system_tmp/onionhen/fps_sample`, 128 bytes) gained
  `game_mem_mb` (the game's mapped/resident memory in MB; the RAM field shows it) and `dbg[72]` (the
  probe text). The decorator runs before the sequence-lock write window so readers never see an odd
  sequence number while it works.
- **CPU meter (root cause).** The original code looked for idle threads named `SceIdleCpu0..7`. On
  this console there are 16 hardware threads named `SceIdleCpu8..15` (plus `SceIdleCpuRv`), so nothing
  was found and the numbers were random; the units were also mixed (seconds plus nanoseconds / 1e6).
  Now every `SceIdleCpu*` thread is found and the figure is `1 - idle_time / capacity` over an 8-second
  sliding window. Sanity checks: the home menu about 10 %, Bloodborne's main menu about 11-13 %, and the
  sum over non-idle threads agrees. Known: the first about 8 seconds after ShellUI starts are wrong
  (the window is filling). The GPU percentage was hidden: no load source was known (the old value was
  the VRAM fill level, always about 0).
- Slot widths in the overlay bar are now max(live text, widest expected text) so the layout does not
  jitter.

## 11. Runtime toggling and its limits

| Limit | Detail | Confidence |
|-------|--------|------------|
| Frame-rate patches cannot be toggled mid-run | The game has already initialised its frame loop at the old rate; applying/removing later crashes on gameplay entry. That is why apply happens at exec time | confirmed |
| Enemy-AI cheats crash when toggled during play | Toggling an AI-disable cheat mid-run crashed the game in its own thread `CSChrThread4`. Unrelated to the camera mods | confirmed |
| **Toggling off a mod whose entries have an empty `off`** | The applier rejects a toggle as "invalid patch" if the mod is currently enabled and **any** patch has `off_len == 0`. The cave/data entries of Wide FOV, DLAA, anisotropy and the head-camera core mod have empty `off` (their contents are dead storage once hooks are restored), so they would not toggle off from the toolbox; edit `enabled` in the file and restart the game instead. FACE2, aim, DOF, motion blur, chromatic aberration, intro logos and the 60 FPS mod have real `off` bytes | inferred from the source, not tested on hardware |
| Overlap conflicts | A mod overlapping an active mod's memory is refused | inferred from the source |
| Live writes bypass the engine | Tools that write through ps5debug do not update the toolbox's idea of which mods are on | inferred |
| Partial failure | If a write or verify fails, already written ranges of that mod are restored from the snapshots in reverse order | from the source; not forced in tests |
| Engine bookkeeping | After a successful toggle the engine records the active ranges (for the overlap check) and the pid | inferred from the source |

Practical rule: **configure through the cheat file and a game restart**; use the toolbox toggle only
for the simple in-place mods.

## 12. Build

onionHEN builds with the PS5 payload SDK inside a container (the image takes about 20 minutes to
build once; the payload build about 4 minutes). The build produces `OnionHEN.elf` (daemon + launcher)
and `bootstrapper.elf`, which are deployed as in section 8. The patch in this repository is the diff
against upstream commit `b23ffe6` for the source files listed in section 2.
