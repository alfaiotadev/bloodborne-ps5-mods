# 70 - onionHEN and its cheat engine

> Tested only with onionHEN on kstuff-lite on **firmware 12.40, PS5 Pro**. onionHEN is a third-party project (GPL-3.0, credited in [../../CREDITS.md](../../CREDITS.md)); this repository carries a **patch** on top of upstream commit `b23ffe6`, not a fork. Companion documents: [../research/07-onionhen-integration.md](../research/07-onionhen-integration.md), [../../onionhen/BUILD.md](../../onionhen/BUILD.md). Statements marked "from the source" were derived by reading code and were **not** exercised on hardware.

## 1. What onionHEN is, as used here

A modular payload stack for the jailbroken PS5: `OnionHEN.elf` (unpacker) -> `bootstrapper.elf` (raises privileges, remounts, blocks the update partition, starts a private ELF loader on 9020) -> `util.elf` (tool services incl. the **cheat engine**) -> `kstuff.elf` -> `daemon.elf` (core daemon, app lifecycle events, ShellUI injection of `shellui.elf` = Toolbox, overlay bar). It does not contain a kernel exploit (the first hop is provided by the chain described in [CREDITS.md](../../CREDITS.md)).

Cheat engine (upstream `source/util/source/cheats/`): `CheatService` (facade, mutex, session), `CheatRepository` (path resolve/load), parsers by extension (`json`, `shn`, `mc4`, `ShnExt`), `CheatApplier` (applies patches), memory backends (`mdbg` for firmware < 8.40, **`kdirect` for >= 8.40**: CR3 page-table walk + physical copy through the direct map, so reads/writes ignore page protections and XOM). Cheat files: `/data/OnionHEN/cheats/<TITLE_ID>_<VERSION>[_<PROCESS>][_<SOURCE_ID>].{json,shn,mc4,ShnExt}`. Upstream host tests for the parsers: `cd source/util/tests && make test` (no PS5 SDK needed).

## 2. What our patch changes (`onionhen/onionhen-bloodborne.patch`, 16 files)

| File (under `source/`) | Change | Why |
|---|---|---|
| `util/source/cheats/memory_backends.cpp` | `mapCodeCaveCommon` made **non-destructive**: only `kernel_mprotect(RWX)` on the existing page | the stock version `mmap`ed an anonymous page over the target page -> zeros -> crash when the code ran |
| `util/source/cheats/cheat_applier.cpp` | snapshot read failure (XOM): map RWX and retry; else use the JSON `off` bytes as the rollback snapshot | "snapshot failed" on code pages |
| `util/source/cheats/json_cheat_parser.cpp` | optional per-mod `"enabled": true` | mark mods for auto-apply |
| `util/source/cheats/cheat_service.cpp` | on session creation: `SIGSTOP` the game, apply every `enabled` mod in file order, `SIGCONT` | patches must precede game initialisation; partially patched frame loop crashes |
| `daemon/source/app_lifecycle_runtime.cpp` | `CheatSessionLifecycleSubscriber` (priority 50): on `BigAppStarted` ask util for the runtime cheat list (creates the session); retry thread polls every 10 ms up to 3000 ms | auto-apply without opening the menu |
| `daemon/source/main.cpp`, `daemon/include/daemon_ops.hpp` | `daemon_probes_init()` | probe decorator |
| `libonion_fps/...` (`fps_publish.hpp/.cpp`, `fps_sample.h`) | decorator hook before the seqlock write; sample gets `game_mem_mb` (offset 48) and `dbg[72]` (offset 52) | overlay probes |
| `shellui/src/prx_overlay.cpp`, `shellui_overlay_widgets.cpp`, `shellui_types.hpp`, `onpress_overlay.cpp` | DBG overlay group; RAM field = game memory; **CPU meter fix** (idle threads are `SceIdleCpu8..15` + `Rv` on this console, not `0..7`; mixed units fixed; 8 s window; GPU % hidden) | live instrument |
| `shellui/src/hook_capture.cpp`, `hooked_funcs.hpp` (+2 lines in `prx_overlay.cpp` `OnRender_Hook`) | remote screenshot replay | A/B automation |

### Known gap in the shipped patch (verify before building)

`daemon_probes_init()` is declared and **called**, but its definition lives in two **new** files of the lab tree that are not part of a `git diff` of tracked files: `source/daemon/source/daemon_probes.cpp` and `source/daemon/include/debug_probes.hpp` (the probe-file parser/decorator; lab tests: `tests/test_debug_probes.cpp`). As of this writing `onionhen-bloodborne.patch` contains modifications only (no `new file` sections), so a build from the patch alone will fail to link (or find `debug_probes.hpp`) unless those files are added. Check with `git apply --check` and `grep -c "new file" onionhen/onionhen-bloodborne.patch`; if missing, re-create the files from the probe format in [10](10-memory-map.md) section 10 (`<title_id> <label> <base_hex> <deref 0|1> <name:size:offset_hex>...`, max 12 probes x 6 fields, 0.5 s refresh, 2 s memory-map refresh, 5 s file mtime check, file `/data/OnionHEN/debug_probes.txt`) or regenerate the patch with `git add -N` / `git diff --binary` including new files.

## 3. Exec-time auto-apply (the delivery path)

1. Game launch -> daemon event `BigAppStarted` -> subscriber asks util for the runtime cheat list -> `ensureRuntimeLocked` creates the session.
2. If any mod has `enabled: true`: `kill(pid, SIGSTOP)`; for each file, each mod in file order with `enabled`: set `entry.enabled = false`, call `toggle()` (snapshot -> write -> read-back verify -> record active ranges); log `[Cheat] auto-applied '<name>' (<file>)` or `[service] auto-apply failed <file> index=<i> (<name>): <status>`; `kill(pid, SIGCONT)`; log `[service] auto-apply complete, resumed pid=<pid>`. A 128-write mod took about 23 ms.
3. A failed mod is logged and stays off; the others still apply. No exception stops the game from resuming.
4. The 60 FPS patch is active from the first menu on; camera/AA mods are active across loads (their caves must be load-safe: [30](30-code-cave-playbook.md)).
5. If the "running big app" query is not ready at the event (observed once: rc -1, session never created, no mods applied), the retry thread polls until the identity appears (up to 3 s) or the pid dies: still exec time.

## 4. Cheat JSON semantics derived from the source

Schema and keys: [00](00-orientation.md) section 2. Rules and limits (from `cheat_applier.cpp`, `json_cheat_parser.cpp`, `cheat_engine_utils.c`, `cheat_engine.h`):

* **Module lookup:** the mod's `module_name` (= file `process`, `eboot.bin`) is resolved in the game process; `base = sections[0].vaddr` (`0x400000`). Without `"absolute": true` the address is `base + offset` (4 MB wrong for our offsets).
* **Order:** patches are applied in array order, each one read-back verified; the whole mod is rolled back from the snapshots (reverse order) when one write/verify fails.
* **Enable vs disable:** enabling writes `on`, disabling writes `off`, **in the same array order**.
* **Overlap/conflict check:** enabling a mod whose ranges (`max(on_len, off_len)`) overlap another enabled mod's ranges is refused (conflict notification), except for "master code" dependencies. `build_cheats.py` checks overlap at build time. Two mods may therefore not write the same bytes - which is why companions (FACE2, AIM) are separate mods writing only their own flag byte.
* **`type`/`description`:** `type` is emitted but not read by the parser code reviewed.

### Hazard 1: entries longer than 1024 bytes (fixed in the generator; verify new caves with a cold start)

`ONION_MAX_PATCH_BYTES` is **1024** in `source/util/include/cheats/cheat_engine.h` (`onion_patch_t` holds fixed `on[1024]`/`off[1024]`; the applier also rejects `max(on_len,off_len) > 1024` as "invalid patch"). `onion_cheat_hex_decode(hex, out, max_len, &len)` returns **-1** when the input does not fit; `parseMemoryObject` then returns false and `parseModObject` **silently skips that memory entry** (`if (parse...) ++patch_count`). The head camera's manager cave grew to 1761 bytes, so its entry was dropped while the hook entry (a `jmp` into it) was still written: the first run of the camera manager executed zeros and the game crashed at the save load (a live apply with ps5debug, which has no such cap, had hidden the problem).

**Fix:** `tools/mods/build_cheats.py` splits every entry above 1000 bytes (only caves/data, where `off == on`) into consecutive entries and asserts that no entry exceeds 1024 bytes. The manager cave is now two entries (`0x54A1600` +1000 B and `0x54A19E8` +596 B). Check after any change of cave size:

```bash
python3 tools/mods/build_cheats.py --all-profiles        # asserts the cap
# on the console, after a cold start with the profile:
python3 tools/dev/camera/hc_state.py cheats/profiles/CUSA03173_01.09_fps.json   # prints MISMATCH lines if an entry is missing
```

### Hazard 2: toggling off a mod with empty `off` entries (mitigated in the generator, untested on hardware)

`CheatApplier::toggle` rejects a patch as "invalid patch" when `(!entry.enabled && patch.on_len == 0) || (entry.enabled && patch.off_len == 0)`, before writing anything. Cave and data entries have no original bytes, so earlier builds of the generators emitted `"off": ""` and **disabling** such a mod from the Toolbox would have failed (the mod just stays on). `tools/mods/build_cheats.py` now fills every empty `off` with the entry's `on` bytes: disabling rewrites identical bytes into the caves/data (harmless even if torn) in array order and then restores the hooks and flag bytes, which carry real `off` values and come last. `verify_against_dump.py` skips entries with `off == on`. **Status: the logic follows from the source; toggling each mod off and on from the menu has not been verified on the console** ([90](90-open-questions.md) A4). Note the size interplay with hazard 1: for the 1761-byte manager cave the `off` is now also 1761 bytes. Do **not** use zeros as `off` for caves (the array order would clear a cave before its hook is restored). Safe runtime switches in any case: the `MODE`/`FACE2`/`AIM` flag bytes by ps5debug (`tools/dev/mods-live/flag.py`) and the touchpad double click.

### Hazard 3: runtime toggling of frame-rate patches or AI cheats

Frame-rate patches crash when toggled mid-run (the frame loop was initialised at the old rate). AI/enemy cheats toggled at runtime crashed the game in `CSChrThread4`. Neither is a camera issue; do not toggle them while testing.

## 5. Console configuration relevant to the mods

* `/data/OnionHEN/config.ini`: `[shortcuts]` `cheats_menu` (`off`, `r3_l3`, `l2_triangle`, `long_options`, `long_share`, `share`) opens the cheat menu; Toolbox shortcuts (`l2_r3`, `long_share`, `share`) open the Toolbox. The Toolbox's `long_share` shortcut takes a screenshot through the same `CaptureScreen` hook the remote trigger uses and can be rebound (for example to L2+R3). None of the built-in shortcuts can run an arbitrary action; the touchpad double click that toggles the head camera is implemented inside the camera cave.
* Overlay: FPS/CPU/GPU/RAM/temperature/network bar plus the patched **DBG** group (probe text from `/data/OnionHEN/debug_probes.txt`, hot reload about 5 s). RAM shows the game's memory. CPU % = `1 - idle_time / capacity` over an 8 s window (the first ~8 s after ShellUI start are wrong); GPU % is hidden (no load source known).
* Files written by the patched daemon/ShellUI: `/system_tmp/onionhen/fps_sample`, `screenshot_request` / `screenshot_ack` / `screenshot_state` ([20](20-tooling.md) section 7, [10](10-memory-map.md) section 10).

## 6. Build and deploy

```sh
git clone https://github.com/aydencharles/onionHEN && cd onionHEN && git checkout b23ffe6
git apply --check ../bloodborne-ps5-mods/onionhen/onionhen-bloodborne.patch    # then: git apply ...
docker build -t onionhen-build .                                               # once, about 20 min
# PS5 payload SDK pacbrew packages (curl, ca-bundle) into .docker/pacbrew-ps5:
#   tar xzf ps5-payload-dev.tar.gz --strip-components=5 opt/ps5-payload-sdk/target/user/homebrew   (the lab used the pacbrew-repo release v0.40.2)
docker run --rm -v $PWD:/workspace -v $PWD/.docker/pacbrew-ps5:/opt/ps5-payload-sdk/target/user/homebrew:ro -w /workspace onionhen-build /bin/bash -c '...'   # ~4 min; command in onionhen/BUILD.md
```

Outputs `build/bin/OnionHEN.elf`, `bootstrapper.elf`, `shellui.elf`, ... Checksums of the v0.0.15-screenshot build are in `onionhen/SHA1SUMS`. Deploy and the no-reboot update procedure (VISIBLE: ShellUI restarts, screen black about 5 s): [20](20-tooling.md) section 5. Keep the previous ELFs under other names; restoring the original means uploading the original ELFs to both paths and rebooting.

After a rebuild always re-verify: klog shows `cheat session primed` and `auto-applied` lines, the 60 FPS mod is active from the first menu, the overlay DBG group shows probes, the screenshot hook arms (`shot.py state`), and the camera mod entries match memory (`hc_state.py`).

## 7. Stock onionHEN versus the patched build (documentation inconsistency to fix)

`README.md` and `docs/install.md` say that stock onionHEN is enough to use `cheats/CUSA03173_01.09.json`. From the patch this cannot hold for the default-on mods: stock has **no** `enabled` flag and **no** exec-time auto-apply, so nothing would be applied at launch; the 60 FPS patch cannot be toggled mid-run; stock `mapCodeCaveCommon` can zero a code page; the stock snapshot read can fail on XOM pages. Stock may be usable for in-place toggles that are safe at runtime (for example No Motion Blur) but this was **not tested**. Treat the patched build as required until someone verifies otherwise, and fix the README/install wording.

## 8. Ideas and next steps

| Idea | First step |
|---|---|
| Finish the cap/off fixes in the generator: `off` = `on` is done; splitting entries <= 1024 bytes is not | extend `build_cheats.py` (split `on` and `off` consistently into consecutive entries), re-run `verify_against_dump.py`, test cold start + Toolbox toggle with klog open |
| Persistent toggles (the Toolbox state is lost on relaunch; `enabled` in the file is the only persistent state) | have the util daemon write the toggled `enabled` flags back to the JSON after a successful toggle (`CheatService` owns the file path) |
| Cheat-file hot reload / reapply without relaunching | read `CheatService` hot-reload state upstream (`docs/util_arch/cheats_cpp.md`); note frame-rate patches still need exec time |
| A pad-chord trigger that runs inside onionHEN instead of in a cave | onionHEN already implements shortcut chords for its menus (`[shortcuts]` in `config.ini`; where the handler lives was not investigated): extend it to write a data flag through the cheat backend |
| Keep the patch complete | regenerate `onionhen-bloodborne.patch` including new files and add a CI-style check (`git apply --check` on a clean checkout of `b23ffe6`) |
| Upstream the generic parts (enabled flag, non-destructive cave mapping) | clean separation of the bloodborne-specific overlay/probe changes |
| Verify other firmware | the backend selection is by firmware major (`< 0x840` mdbg, else kdirect): test on another firmware with a read-only probe first (`tools/dev/core/ps5dbg.py`, `code_patch.py <addr> ?8`) |
