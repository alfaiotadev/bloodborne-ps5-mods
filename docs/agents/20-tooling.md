# 20 - Tooling: talking to the console

> Tested only on firmware 12.40 with a PS5 Pro. Everything here was done with ps5debug-NG on that setup. Do not assume other firmware, other ps5debug builds or other consoles behave the same.

Safety first (details in [../../AGENTS.md](../../AGENTS.md)): tell the user **before** anything that is visible on the console (game kill, ShellUI restart, teleport, camera lock, toast), never print tokens, back up the console's cheat file before replacing it, never toggle enemy/AI cheats while testing other mods, and keep a backup of the save before experiments that can crash the game.

The shipped scripts and their full reference table are in [`../../tools/dev/README.md`](../../tools/dev/README.md); this file explains the protocol underneath, the workflows, and how the pieces interact (including the traps).

## 1. Setup on the bridge host

Any Linux/macOS machine that can reach the console over the network.

```bash
export PS5_HOST=<console-ip>                 # required by everything that talks to the console, no default
python3 -m venv .venv && . .venv/bin/activate
pip install capstone                         # disassembly, tools/mods/verify_against_dump.py, tools/dev/analysis/*
pip install numpy pillow imagecodecs         # only for screenshot analysis (JPEG XR decode)
python3 tools/dev/core/ps5dbg.py             # connectivity check: prints the process list (needs ps5debug on the console)
```

Environment variables read by `tools/dev` (from `tools/dev/core/ps5env.py`):

| Variable | Meaning | Default |
|---|---|---|
| `PS5_HOST` | console address | required |
| `PS5_DEBUG_PORT` | ps5debug port | 744 |
| `PS5_FTP_PORT` | FTP port | 2121 |
| `PS5_ELFLDR_PORT` | ELF loader port (toast payload) | 9021 |
| `PS5_WORKDIR` | scratch dir for logs, snapshots (`*.pkl`), `scenes.json` | `./work` |
| `PS5_NOTIFY_ELF` | path of a built `notify.elf` (enables on-screen toasts; otherwise the text is just printed) | unset |
| `SCENES` | scenes file | `$PS5_WORKDIR/scenes.json` |
| `PS5_EBOOT_DUMP`, `PS5_EBOOT_BASE` | flat eboot memory image and the virtual address of its first byte (`0x400000`), for `analysis/dump_xref.py`, `bb_ann.py`, `bb_ctx.py`, `dump_ctx.py` | unset / `0x400000` |

* `tools/mods/*` needs **only the Python 3 standard library** (generators) plus `capstone` for the verification script.
* Scripts under `tools/dev/<folder>/` put `core/` and `mods-live/` on `sys.path` relative to their own location, so they can be started from any working directory (`python3 tools/dev/camera/head_cam.py status`).
* Required console state: the jailbreak chain is up, **ps5debug-NG listens on port 744** (it is a payload sent to elfldr on port 9021), onionHEN is running, Bloodborne is running (`eboot.bin`). After a console rest mode the chain may need to be re-run.
* ps5debug has no authentication: only on a trusted network.

## 2. ps5debug protocol (port 744)

Little-endian. Request = 12-byte header `<III magic=0xFFAABBCC, opcode, body_length>` followed by the body. Response begins with a `u32 status`: **`0x80000000` = success** (`ps5dbg.py` also names `0xF0000001` = generic error; `0xF0000003` = unknown/bad command, seen when a wrong opcode was sent).

| Opcode | Name | Body | Response after status |
|---|---|---|---|
| `0xBDAA0001` | process list | none | `u32 n`, then `n` x 36 bytes: 32-byte NUL-padded name + `i32 pid` |
| `0xBDAA0002` | read | `<IQI` pid, address, length | `length` raw bytes (on failure only a non-success status) |
| `0xBDAA0003` | write | `<IQI` pid, address, length | status ack; **then the client sends `length` data bytes**; then a second `u32` status |
| `0xBDAA0004` | memory map | `<I` pid | `u32 n`, then `n` x 58 bytes: 32-byte name, `<QQQ` start, end, offset, `<H` protection (value 2 = writable; the lab scans test `prot & 2`) |
| `0xBDAA0007` | `proc_elf` | `<II` pid, length | `length` bytes, then a status; present in `ps5dbg.py`, semantics not documented, unused by other scripts |
| `0xBDBB0001` | debugger attach | `<I` pid | see section 3 |
| `0xBDBB0002` | debugger detach | none | |
| `0xBDBB0010` | stop/go | `<I` 0 | `0` = go |

Process commands are `0xBDAA00xx`, debugger commands `0xBDBB00xx`. The ps4debug-style protocol has more opcodes; only the ones above are exercised by the lab scripts, do not rely on others without testing.

Minimal client (this is `tools/dev/core/ps5dbg.py` in essence):

```python
import os, socket, struct
MAGIC, OK = 0xFFAABBCC, 0x80000000
class Dbg:
    def __init__(self, host=os.environ["PS5_HOST"], port=744):
        self.s = socket.create_connection((host, port), timeout=15); self.s.settimeout(120)
    def recvn(self, n):
        b = b""
        while len(b) < n:
            c = self.s.recv(n - len(b));  b += c
            if not c: raise IOError("closed")
        return b
    def cmd(self, op, body=b""):
        self.s.sendall(struct.pack("<III", MAGIC, op, len(body)) + body); return struct.unpack("<I", self.recvn(4))[0]
    def read(self, pid, addr, n):
        return self.recvn(n) if self.cmd(0xBDAA0002, struct.pack("<IQI", pid, addr, n)) == OK else None
    def write(self, pid, addr, data):
        assert self.cmd(0xBDAA0003, struct.pack("<IQI", pid, addr, len(data))) == OK
        self.s.sendall(data); assert struct.unpack("<I", self.recvn(4))[0] == OK
        assert self.read(pid, addr, len(data)) == data              # always read back
```

(The shipped class is named the same and offers `proc_list`, `proc_maps`, `proc_read`, `proc_elf`, `cmd`; the examples below use the shipped names `proc_read` / `cmd`.)

Finding the game: process list, name `eboot.bin`, take the **last** entry (`[p for p in d.proc_list() if p[0]=="eboot.bin"][-1][1]`). The pid changes at every launch.

Rules that cost time to learn:

* Reads of unmapped memory return a failure status (`None` in the helpers): always handle it. Heap objects move between launches and on respawn.
* Code is XOM but readable and writable through ps5debug (DMAP). Writes go to physical pages and ignore protections.
* A code patch longer than one byte must be written with **one** write call (`fmt:"x"` in `ab_loop.py`). Three separate one-byte writes of a 3-byte patch once created a transient invalid instruction (`31 95 C0`) and crashed the game.
* Never rewrite a **live** cave: unhook first (restore the hook's original bytes), then change the cave, then hook again. When removing a mod, restore **hooks/call sites first**, caves afterwards (clearing a cave before its call site crashed the game).
* Multi-megabyte reads are fine in 8 MB chunks (about 82 MB/s measured).
* A **kernel crash dialog** left open can make the console shut itself down; ask the user to dismiss it.

### Pointer-chain and vtable helpers (the idiom used everywhere)

```python
q = lambda a: struct.unpack("<Q", d.proc_read(pid, a, 8))[0]
pl  = q(q(0x593E878) + 0x60)                 # player ChrIns
X   = q(q(pl + 0x3B0) + 0x68)                # physics body
pos = struct.unpack("<3f", d.proc_read(pid, X + 0x1E0, 12))
mgr = q(q(0x593E860) + 0x2830); cam = q(mgr + 0x60)
```

Find all heap instances of a vtable (as in `probes/find_vtable_instances.py` / `ab_loop.py`): iterate `proc_maps`, skip regions that are not writable (`prot & 2 == 0`), tiny (< 4 KB) or huge (> 1 GiB, the GPU arena), read in 8 MB chunks and search for `struct.pack("<Q", vtable)` at 8-byte alignment. Validate by reading the object's other fields.

## 3. The debugger and catching crashes

`tools/dev/probes/crash_catch.py` waits for `eboot.bin`, waits 18 s (onionHEN applies cheats at exec first), attaches the debugger and logs every stop; on SIGSEGV/SIGILL/SIGABRT/SIGFPE/SIGBUS it prints registers, 48 bytes of code before `rip` and 0x80 bytes of stack, then **leaves the game stopped** (read everything you need from memory before exiting; the process dies when the watcher exits). While it runs it listens on TCP 755 on all interfaces.

Protocol facts:

1. The **console connects back** to the client on **TCP 755**, so the client must listen first (binding 755 needs root on the bridge host).
2. Send `0xBDBB0001` with the pid on port 744; accept the connection on 755; send stop/go `0xBDBB0010` with body `0` (go).
3. Stops arrive as **864-byte** packets: `u32 lwpid`, `u32 wait status` (signal = `(status>>8)&0xFF` when the low byte is `0x7F`), thread name (40 bytes) at offset 8, registers from **offset 48** in the order r15, r14, r13, r12, r11, r10, r9, r8, rdi, rsi, rbp, rbx, rdx, rcx, rax (15 qwords), `trapno u32` at +120, `err u32` at +128, **`rip` at +136**, then cs, rflags, rsp, ss.
4. Non-fatal stops (SIGSTOP/SIGTRAP...) are continued with `0xBDBB0010`.

What it has found so far: the head-camera slot scan dereferencing the flag value `0x1_0000_0003` (crash at cave address `0x54A1792`, `vmovss xmm4,[rax+0xC]` with `rax = 0x100000CC3`); a jump into a freed object in the game's own `CSChrThread4` after an AI cheat was toggled (return address `0x191E97E`; not our code).

Quick triage without a debugger: stream the kernel log (`nc $PS5_HOST 3232 > klog.txt`) and look for `fatal signal` and the `# rip:` line that follows; a `rip` inside `0x54A0000..0x54A4000` is a cave bug, anywhere else it is either a bad hook or the game's own crash.

## 4. Cheat files, FTP and the console log

```bash
# back up the console's current file first (always), then upload
curl -gsS ftp://$PS5_HOST:2121/data/OnionHEN/cheats/CUSA03173_01.09.json -o console_backup.json
curl -gsS -T cheats/CUSA03173_01.09.json ftp://$PS5_HOST:2121/data/OnionHEN/cheats/CUSA03173_01.09.json
```

* `-g` disables curl globbing (brackets in names), URL-encode odd characters. LIST is the authoritative existence/size check.
* ftpsrv quirks: **`DELE` is refused** (`550 Read-only filesystem`: files cannot be deleted, only overwritten or emptied), `RNFR` sometimes lies (retry), `STOR` and `APPE` work (resume with `curl --append`).
* The cheat file name must equal `<title id>_<version>.json`. onionHEN reads it when the game session is created (game start); a changed file takes effect at the next **game launch**.
* Kernel log: `nc $PS5_HOST 3232 | tee klog.txt`. Useful lines: `Big App started` (game launch), `[lifecycle] cheat session primed for CUSA03173`, `[Cheat] auto-applied '<mod name>'`, `[service] auto-apply failed ...`, `[service] auto-apply complete, resumed pid=`, `fatal signal`, `# rip:`.
* Ready-made profiles: `python3 tools/mods/build_cheats.py --all-profiles` writes `cheats/CUSA03173_01.09.json` plus `cheats/profiles/*_quality.json` and `*_fps.json`; copy the one you want to the console under the name `CUSA03173_01.09.json`.

## 5. Starting, restarting and closing the game

There is **no launch/kill automation** in the sources: the human starts and closes Bloodborne from the PS5 home screen (and dismisses the crash dialog). Consequences for agents:

* Ask the user to launch/close the game; say what you need ("please start Bloodborne now and tell me when you are at the main menu / in the Hunter's Dream").
* A new launch = new pid, new heap addresses (re-run any `vt:`/`vtall:` lookups), cheats are re-applied from the JSON.
* To produce an **unpatched dump** the cheat file must not auto-apply: move it away (or set every `"enabled": false`) *before* launching, dump, then restore it.
* The lab once drove "one config per launch" by watching the klog for `Big App started`, waiting for `CRASH` (fatal signal) or `BOOT` (sample valid, fps > 1) and uploading the next config (`res_queue.py`, not shipped): a good pattern for crash-bisecting a list of configs.

### Updating onionHEN without a console reboot (VISIBLE: warn the user)

1. Upload the new ELFs by FTP: `OnionHEN.elf` -> `/data/ps5_autoloader/onionHEN.elf`, `bootstrapper.elf` -> `/data/OnionHEN/onionhen.elf` (verify `sha1`; keep the old files under other names).
2. **Close the game.** Send to port 9048 the frame `struct.pack("<II", 0x4F4E494F, 1)` (`cmd_shutdown_onion_stack`): kills the util daemon and the private elfldr, **restarts SceShellUI (screen black for about 5 s)**, the daemon exits; kstuff stays.
3. About 15 s later send `OnionHEN.elf` to port 9021 (`nc $PS5_HOST 9021 < OnionHEN.elf`): the bootstrapper restarts daemon and util and injects the fresh ShellUI payload. Re-sending only the launcher (without step 2) updates the daemon but does **not** re-inject ShellUI ("Toolbox already active").
4. The screenshot hook is disarmed after a ShellUI restart: press the console's screenshot button once.

## 6. Dumping the game and verifying a cheat file

No dumper is shipped. A dump is a few lines:

```python
import os, sys
sys.path.insert(0, "tools/dev/core"); from ps5dbg import Dbg
d = Dbg(); pid = [p for p in d.proc_list() if p[0] == "eboot.bin"][-1][1]
with open("eboot_dump.bin", "wb") as f:
    a = 0x400000
    while a < 0x5AD4000:
        n = min(8 << 20, 0x5AD4000 - a); f.write(d.proc_read(pid, a, n)); a += n     # dump index = address - 0x400000
```

* The dump is **game code**: never commit it, never upload it. `.gitignore` it.
* Dump an **unpatched** run (no auto-apply, section 5), early (before anything patched memory).
* `python3 tools/mods/verify_against_dump.py <cheats.json> eboot_dump.bin` compares every `off` value with the dump and checks that every hook ends on an instruction boundary (capstone). `python3 tools/mods/fill_off_from_dump.py tools/mods/data/base_mods.json eboot_dump.bin` fills the `off` bytes of the base mods from the dump. (The docstrings of these two scripts point to `docs/agents/02-tooling.md`, which is a redirect stub to this file.)
* Static helpers: `PS5_EBOOT_DUMP=eboot_dump.bin python3 tools/dev/analysis/bb_ann.py 183ac60 183ad00` prints annotated linear disassembly (rip-relative targets resolved to strings); `bb_ctx.py <insn_addr_hex>...` shows instructions around an address and resyncs the decoder (x86 has no instruction boundaries: it tries several start offsets); `dump_ctx.py` annotates around addresses and marks the render-resolution globals; `dump_xref.py` is the library with string/xref/function-start helpers (numpy + capstone).
* Only **code** bytes of a dump are comparable with `off` values; data bytes are live runtime state.

## 7. Screenshots (patched onionHEN ShellUI payload)

The patched ShellUI payload hooks `CaptureScreen_old/new`, **caches the arguments of one real screenshot press**, and replays the capture when asked.

* **Arm:** the human presses the console's screenshot button **once** after ShellUI has (re)started. State file `/system_tmp/onionhen/screenshot_state` (`valid=1 presses=N ...`) shows it is armed. Standby/ShellUI restart disarms it.
* **Trigger:** upload any file named `/system_tmp/onionhen/screenshot_request` by FTP; the UI thread checks every ~6 frames, consumes it, calls the original capture, and writes `screenshot_ack` = `<epoch_ms> <status>` (**0** ok, **1** not armed, **2** original function missing). `tools/dev/core/shot.py` wraps this: `shot.py state`, `shot.py [n] [interval_s]`, library `shot.trigger()` returns `(ok, ack_epoch_ms, status)`.
* **Fetch:** screenshots are JXR files under `/user/av_contents/photo/NPXS40087/<title>/<hash>/<ts>.jxr` with a `.meta` carrying `absoluteTime` (epoch ms; about `ack - 1.0 s`). `core/collect_shots.py` matches photos to ab_loop states by `absoluteTime` (tolerance 0.7 s).
* **Decode:** `imagecodecs.jpegxr_decode`. The capture is 3840x2160 of a native 1080p render; analysis reduces 2x2 to 1080p-equivalent luma. Keep the JXR + `.meta` as the master (about 0.5 MB each); lossless WebP/PNG are 2-7 MB; lossy WebP only for viewing.
* Toast messages are **not** captured in screenshots, so a short `shot_delay` (1-2 s) is enough for changes that apply within a frame (camera/FOV lerp about 1 s).

Toasts: `ps5env.toast()` uploads text to `/data/toast.txt` by FTP and sends the toast payload (`PS5_NOTIFY_ELF`, built from `tools/dev/notify/` with the PS5 payload SDK: `make -C tools/dev/notify`) to port 9021. Used for human cues; without `PS5_NOTIFY_ELF` the text is only printed.

## 8. The A/B loop (`tools/dev/mods-live/ab_loop.py`)

Alternates named states in the live game, takes a screenshot per state, **always restores every touched address** in a `finally` block. Example specs: `tools/dev/specs/*.json`. Spec (JSON):

| Key | Meaning |
|---|---|
| `hold` | seconds per state |
| `sequence` | list of state names, e.g. `["A","B","A","B"]` (repeat states give the noise floor) |
| `fixed` | writes held for the whole run (e.g. SFX-OFF `{"addr":"vt:0x57b9080+0x5c6","fmt":"B","val":1}`) |
| `states` | `{name: [write, ...]}` |
| `shot_delay` | seconds after the state switch to trigger a screenshot (needs the armed hook; the loop pre-flights it and refuses to start if not armed) |
| `scenes`, `scene_wait`, `warmup`, `scenes_file` | run the whole sequence once per recorded scene (camera pose lock + game warp); `warmup` passes visit every scene first without shots; scenes file also from `$SCENES` or `$PS5_WORKDIR/scenes.json` |
| `toast` | `false` skips on-screen cues |
| `restore_first` | addresses restored first (hook call sites before their caves) |

A write is `{"addr", "fmt", "val", "check"?, "noverify"?}`. `fmt`: `B` u8, `H` u16, `I` u32, `f` float32, **`x` hex bytes written in ONE atomic call (use for code)**. `val` may be `"orig"` (the value read before the run). `addr` may be a hex string, **`vt:<vtable>+<off>`** (the single heap instance of that vtable; survives restarts) or **`vtall:<vtable>+<off>`** (one write per live instance, e.g. the 4 AA pass instances). `check: [addr, qword]` must match before anything is written (object moved?). `noverify` skips the read-back for values the game consumes within a frame (dirty flags, the scene-warp CALL flag).

Example (as in the shipped `spec_aa_modes_scenes`-style specs): compare the game's DLAA with threshold 0.3 in a scene with fog off:

```json
{"hold": 4, "shot_delay": 2, "toast": false, "warmup": 1, "scene_wait": 5, "scenes": ["my_spot"],
 "fixed": [{"addr": "vt:0x57b9080+0x5c6", "fmt": "B", "val": 1}],
 "sequence": ["game DLAA", "thr 0.3", "game DLAA"],
 "states": {"game DLAA": [{"addr": "vtall:0x56e7980+0x8", "fmt": "B", "val": 0}],
            "thr 0.3": [{"addr": "vtall:0x56e7980+0x8", "fmt": "B", "val": 1}, {"addr": "vtall:0x56e7980+0x9", "fmt": "B", "val": 1},
                        {"addr": "vtall:0x56e7980+0xc", "fmt": "I", "val": 3}, {"addr": "vtall:0x56e7980+0x28", "fmt": "f", "val": 0.3},
                        {"addr": "vtall:0x56e7980+0x2c", "fmt": "f", "val": 2.44}, {"addr": "vtall:0x56e7980+0x30", "fmt": "f", "val": 0.25}]}}}
```

Log lines (file `$PS5_WORKDIR/ab_loop.log`): `HH:MM:SS host | console_epoch_ms=<ms> | state i/N = <scene> :: <state>`, `shot: ok=True status=0 ack_epoch_ms=<ms>`, `persisted after hold: YES|NO -> ...` (NO means the game rewrote your value or the heap object moved: **discard that state**), `RESTORED all`.

After the loop: `python3 tools/dev/core/collect_shots.py <log> <outdir> [--n 40]` then `python3 tools/dev/analysis/analyze_ab.py <outdir> [--ref "<state>"] [--crop x0,y0,x1,y1] [--png] [--collage]`. Metrics: normalised sharpness `mean|Laplacian| / (blur sigma 6 + 8)` on 1080p-equivalent luma (whole frame and lower 40 %), `mean|d|`, phase-correlation shift (0,0 = same framing), and the **noise floor** from repeated states. Comparison pages: `analysis/make_slider.py` (slider, strips, blink, diff), `analysis/make_strips.py` (one image cut into per-state strips).

Traps:

* **`ab_loop.py` with `scenes` installs the lab pose-lock cave and, at the end, removes it** (`Scenes.remove()`). Do not use scene runs while the release head-camera mod is active: they share hooks `0x183F77B`, `0x1C090E0`, `0x1836C54`, the cave addresses `0x54A0780`/`0x54A1100` and the data block `0x54A0E00` with a different layout ([10](10-memory-map.md) section 1). The same applies to `scene.py`, `scenelib.py`, `head_cam.py`, `cam_lock.py` and the camera logs.
* Four shipped specs (`spec_aa_falloff_scenes`, `spec_taa_scenes`, `spec_taa_weight_scenes`, `spec_aniso_scenes`) contain heap addresses from one session (their `note` field says so): re-resolve them before use. The scene names in the specs are not shipped; record your own.

## 9. Scenes (repeatable position + camera)

`tools/dev/core/scene.py` (library `scenelib.py`): a scene is `{"map": u32, "player_pos": [x,y,z], "player_yaw": rad, "cam": <64 hex bytes = 4 pose rows>, "note": ...}` stored in `scenes.json` (`tools/dev/scenes.example.json` shows the schema).

| Command | Action |
|---|---|
| `record <name> [note...]` | store the current player position, yaw and camera pose |
| `goto <name> [--wait 5.0] [--keep-yaw]` | lock the camera to the stored pose (pose-lock cave), game-warp the player (same map only), wait; camera stays locked |
| `shot <name> [--wait 5.0] [--keep]` | goto + remote screenshot + release the camera |
| `sweep <scene...> [--passes N] [--warmup W] [--wait 5.0] [--log f.jsonl]` | warm-up passes (no shots) then N measured passes, a shot per scene |
| `settle <name> [t1 t2 ...]` | warp, then a shot at each given second (texture streaming settle: about 4 s) |
| `nowarp`, `release`, `list`, `install`, `remove` | utilities (`remove` unhooks and clears the lab caves) |

Measured: position error 0.000 m over 27-100 m warps, yaw restored exactly, image phase-correlation shift (0,0) px, mean luma difference between repeat visits 1-5 (noise). **Plain warps do not unload textures** (an elevator/area change does), so do one warm-up pass before measuring; compare only shots from the same visit/run; the warp only works inside the current map; enemy AI is on, so a death mid-run ruins the run (heap objects get reallocated, `persisted after hold: NO`, texture streaming breaks until a reload). A call-flag verification race (the cave clears `CALL` within a frame) is why `scenelib` writes it with `verify=False`.

## 10. Overlay probes and the FPS sample

`/data/OnionHEN/debug_probes.txt` (hot-reloaded, ~5 s) defines values the daemon reads from the game every 0.5 s and shows in the overlay **DBG** group; the daemon also publishes `game_mem_mb` (sum of the game's VM map). `tools/dev/core/onion_sample.py [seconds] [interval]` decodes `/system_tmp/onionhen/fps_sample` over FTP (fps, pid, valid, game memory, DBG text, age). Format and layout: [10](10-memory-map.md) section 10. Use this to measure fps (the only performance metric the maintainers recorded; there are no GPU/CPU load numbers).

## 11. Script map (`tools/dev/`)

Authoritative per-script reference with usage and mode (WRITES / read-only / offline): [`../../tools/dev/README.md`](../../tools/dev/README.md). Orientation:

| Folder | What is in it | Notes |
|---|---|---|
| `core/` | `ps5dbg.py` client, `ps5env.py` env/toast helpers, `scene.py` + `scenelib.py`, `shot.py`, `collect_shots.py`, `onion_sample.py` | scenes install the **lab** pose-lock cave (collides with release) |
| `mods-live/` | `ab_loop.py`, `apply_live.py`, `code_patch.py`, `flag.py`, `flag_toggle.py`, `fov_live.py`, `player_warp.py`, `time_freeze.py`, `make_cam_pose_cave.py` | all WRITE to the running game. `apply_live.py <cheat.json> "<mod name prefix>"` applies one mod live (flags off first, entries in order, flags last) and never resets the cave's cached `HOLD`/`ARROFF`/`COOL` fields (they are not part of any cheat entry, so a re-apply does not force a rescan); `fov_live.py <scale>` rewrites the FOV constant at `0x54A0500`; `player_warp.py` is a raw data-write warp valid only for about 1 m |
| `camera/` | `head_cam.py`, `cam_lock.py`, `cam_pose.py`, `face_cam.py`, camera diagnostics/finders, `hc_state.py` (verify live hooks/data against the cheat JSON), `dump_cam_params.py`, `read_cam.py` | `head_cam.py` and `cam_lock.py` are the **lab** versions (bone 78 chain); do not combine with the release mod |
| `graphics/` | `aa_probe.py`, `yebis_probe.py`, `read_dof.py`, `read_lod.py`, `dump_lod_rows.py`, `gfx_inspect.py`, `scan_rt.py`, `aa_loop.py`, `aniso_loop.py`, `sampler_loop.py` | mostly read-only; the `*_loop.py` write and restore |
| `probes/` | structure finders and state dumps (bone arrays, holders, cadence, lock-on, stick, params), `crash_catch.py` | read-only except `crash_catch.py` (debugger) |
| `analysis/` | `analyze_ab.py`, `make_strips.py`, `make_slider.py`, `bb_ann.py`, `bb_ctx.py`, `dump_ctx.py`, `dump_xref.py` | offline; need numpy/Pillow/imagecodecs/capstone and your own dump |
| `specs/` | example A/B specs | see section 8 traps |
| `notify/` | toast payload source (no binary) | |

Lab scripts described in these docs but **not shipped** (the description is still a record of the method): `make_res_cheat.py` and `res_queue.py` (resolution experiments, one config per launch), `hook_dump.py` and the `tools/hook` diagnostics (CreateTexture2D/swapchain/computeSurfaceInfo wrappers, log ring at `0x5A40010`), `make_fps_camera_mod.py` and `fps_cam_live.py` (the earlier "hood view" FPS camera: distance 0.05 m, height 1.55, forward 0.2), `make_camera_mod.py` (superseded by `tools/mods/make_fov_mod.py`), `make_heat_data.py`, `cnt_parse.py` and `fix_60fps_pkg.py` (a failed attempt to repair a 60 FPS repack pkg by transplanting `origin-deltainfo.dat`; PlayGoCore rejected the repack with `0x80F00612`), several scan scripts (`scan_arena.py`, `scan_dbg.py`, `scan_c0000.py`, `scan_asm.py`, `wide_scan.py`, `find_arrays2/3.py`, `head_world.py`).
