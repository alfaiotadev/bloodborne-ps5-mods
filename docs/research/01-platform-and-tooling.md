# 01 - Platform and tooling

How the research was set up, how game memory was read and written, and why the cheat file uses
absolute addresses. Everything here is needed to reproduce the later documents.

> **Test platform (repeated from the README on purpose).** All measurements and experiments were done
> on **PS5 firmware 12.40 on a PS5 Pro**, with Bloodborne Game of the Year Edition (`CUSA03173`,
> version 01.09) running in backward-compatibility mode, 4K output of a native 1080p render.
> **Behaviour and performance on a base PS5 are unknown**, and so is everything on other firmware
> versions, game versions and regions.

## 1. Setup overview

Two machines on one isolated network segment:

| Role | What runs there |
|------|-----------------|
| Console | Jailbroken PS5 (firmware 12.40) with the payload chain below. The game process is `eboot.bin`. |
| Lab host | Any Linux or macOS machine with Python 3. Runs the research scripts (`tools/dev/*.py`), talks to the console over TCP, and (optionally) analyses screenshots. |

Console addresses are written `<console-ip>` throughout; the lab tools hard-code one address near the
top of the ps5debug client and must be edited for your network.

### Payload chain

How the console is jailbroken is out of scope (see [`CREDITS.md`](../../CREDITS.md) for the projects
involved). What the research needs running on the console:

| Component | Port | Purpose |
|-----------|------|---------|
| kstuff-lite | - | Kernel patches (fSELF/package support) that the rest of the chain depends on. |
| elfldr (ps5-payload-dev) | 9021/tcp | One connection = one ELF, executed on receipt. Used to (re)load payloads, including onionHEN. |
| ftpsrv | 2121/tcp | FTP server with the console filesystem exposed (writable under `/data`). Used for cheat files (`/data/OnionHEN/cheats/`), screenshots (`/user/av_contents/photo/`) and onionHEN's control files (`/system_tmp/onionhen/`). The version used cannot delete files (`DELE` returns 550); overwriting works. File names with spaces or brackets are easier to handle after renaming. |
| ps5debug-NG | 744/tcp | The debugger payload: process list, memory maps, memory read/write, debugger attach. All live-memory research goes through it (section 4). |
| onionHEN (patched, see [07](07-onionhen-integration.md)) | 9048/tcp (IPC) | Cheat engine, ShellUI toolbox and overlay. Applies the cheat JSON at game start. |

Practical notes that cost time:

- A **game crash dialog must be dismissed** on the console. Leaving it open made the console shut
  itself down (observed twice).
- Restarting ShellUI (needed to load a new ShellUI payload, see [07](07-onionhen-integration.md#8-updating-the-payload-without-a-reboot))
  blanks the display for about five seconds and must not be done with a game running.
- A crashing payload sent to elfldr can take down unrelated system processes; check the payload
  state afterwards.

## 2. Game process and memory model

| Fact | Value | Confidence |
|------|-------|------------|
| Process name | `eboot.bin` (when several exist, take the newest pid) | confirmed |
| Image base | `0x400000`; the main image spans `0x400000`-`0x5AD4000` (91,045,888 bytes) | confirmed (full image read from the live process) |
| Code pages | Execute-only (XOM): a normal read of code fails | confirmed |
| Game heap | Objects live at `0x2_0000_0000`-`0x3_FFFF_FFFF` (nothing outside this window was ever seen); the caves use it, plus a low dword >= `0x10000`, as their "plausible pointer" test (see [02](02-code-caves-and-hooks.md#7-pointer-validation)) | confirmed (window used in shipped code) |
| Large GPU arena | One mapping of about 3325 MB, the largest in the process; skipped when scanning for objects | confirmed |
| Cave region | `0x54A0000`-`0x54A4000` (16 KiB), inside the image; all zero bytes in a dump of the unpatched process (the zero run extends from roughly `0x547F994` to `0x54DBFD0`) | confirmed |

**Static globals** (fixed addresses inside the image, e.g. `0x593E878` WorldChrMan) keep their
address across runs and across game restarts. **Heap objects** move on every start; they are found
by following pointer chains from a static global or by scanning for a vtable (section 5).

### Virtual address versus file offset

The 60 FPS patch this project started from is published as a patcher that edits a decrypted
`eboot.bin` on disk. Its file offsets map to the process like this:

```
virtual address = file offset + 0x3FC000        (confirmed; e.g. file 0x512C9F8 -> 0x55289F8)
```

onionHEN, on the other hand, resolves a cheat entry as `base + offset` where `base` is the virtual
address of the module's first section (`0x400000` for `eboot.bin`). Feeding it the already-absolute
addresses therefore shifts every write **4 MB too high**. See the next section.

## 3. Why cheat-JSON offsets are absolute virtual addresses

This was the root cause of the first long-running failure ("all writes succeed, the game crashes").

- onionHEN's JSON parser accepts an optional `"absolute": true` per memory entry; without it the
  engine writes to `sections[0].vaddr + offset`.
- The first converted cheat file contained virtual addresses (file offset + `0x3FC000`) but was
  applied without `absolute`. All 134 writes landed `0x400000` bytes too high. The bytes there were
  valid code, so the write and the engine's read-back verification both succeeded, and the game
  crashed when that code ran.
- A wrong hypothesis (the GOTY executable differing from the original release at one orphaned byte
  around `0x283487E`) was a side effect of looking at the shifted address; at the correct address
  `0x243487E` the original instruction is `mov dword [r12+0x18], 0x3D088889` (a 1/30 s time step)
  and the patch cleanly replaces it with the 1/60 s constant.
- **Fix:** `"absolute": true` on every entry. The release generators emit it everywhere, and every
  address in these documents is already a virtual address, so `offset` in the cheat file equals the
  address you see in the debugger. The wrong rule "memory = `0x400000` + cheat offset" appeared in
  early notes and is explicitly retracted. Confirmed: the game then runs at 60 FPS from the first
  menu on.

## 4. The ps5debug protocol

All live research uses ps5debug-NG on port 744 (a descendant of the ps4debug protocol). The wire
format below is what the lab client (`tools/dev/ps5dbg.py`) implements; every item was exercised on
the console unless marked otherwise.

### Framing

Little-endian. Request:

```
u32 magic   = 0xFFAABBCC
u32 command
u32 body_length
body...
```

Every command answers with a `u32` status first. `0x80000000` is success; `0xF0000001` is a generic
error; `0xF0000003` was returned by the image-dump command (see below). Payload data, if any, follows
the status.

### Process commands (`0xBDAA00xx`)

| Command | Body | Reply | Notes |
|---------|------|-------|-------|
| `0xBDAA0001` process list | none | status, `u32 n`, then `n` entries of 36 bytes: `char name[32]`, `i32 pid` | The game is the entry named `eboot.bin`. |
| `0xBDAA0002` memory read | `u32 pid, u64 address, u32 length` | status, then `length` raw bytes | Reads through the kernel direct map, so it also works on execute-only code pages. About 82 MB/s measured. An unreadable range returns a non-success status. |
| `0xBDAA0003` memory write | `u32 pid, u64 address, u32 length` | status; then the client sends `length` bytes; then a second status | **One command = one atomic write.** Always read back and compare afterwards. |
| `0xBDAA0004` memory maps | `u32 pid` | status, `u32 n`, then `n` entries of 58 bytes: `char name[32]`, `u64 start`, `u64 end`, `u64 offset`, `u16 prot` | `prot & 2` is the write bit; used to find scannable heap regions. |
| `0xBDAA0007` | `u32 pid, u32 length` | status (+ data) | Named "PROC_ELF" in the lab client. Returned `0xF0000003` when used to dump the image, so dumps are done with plain reads of `0x400000`-`0x5AD4000`. |

Other process commands exist in the ps4debug lineage (call, protect, scan, info, alloc/free); they were
**not used** and their availability in ps5debug-NG is not verified here.

### Debugger commands (`0xBDBB00xx`) and port 755

| Command | Body | Notes |
|---------|------|-------|
| `0xBDBB0001` attach | `u32 pid` | Note the prefix: attach is `0xBDBB...`, not `0xBDAA...`. After the command the **console connects back to the client's TCP port 755**, so the client must already be listening. Binding port 755 needs root on Linux. |
| `0xBDBB0002` detach | none | |
| `0xBDBB0010` stop/go | `u32 0` | Resumes the stopped process. For a non-fatal stop the lab client simply sends "go" again (signal pass-through). |

A thread-list command returned `0xF0000001` in an early session and is not needed for crash catching.

**Stop packet** (console to client on port 755): **864 bytes** each time a thread stops.

| Offset | Size | Field |
|--------|------|-------|
| 0 | u32 | lwp (thread id) |
| 4 | u32 | wait status (`(status & 0xFF) == 0x7F` means stopped; signal = `(status >> 8) & 0xFF`) |
| 8 | 40 bytes | thread name (NUL-terminated) |
| 48 | 15 x u64 | registers in the order r15, r14, r13, r12, r11, r10, r9, r8, rdi, rsi, rbp, rbx, rdx, rcx, rax |
| 48+120 | u32 | trap number |
| 48+128 | u32 | error code |
| 48+136 | 5 x u64 | rip, cs, rflags, rsp, ss |

Procedure that produced every crash root cause in this project (`tools/dev/crash_catch.py`):

1. Listen on port 755.
2. Wait until `eboot.bin` appears; wait about 18 seconds so the game is past early start-up.
3. Send `0xBDBB0001` with the pid; accept the connection (a few seconds timeout); read the initial
   packet; send "go".
4. For every further stop packet: log the signal, rip and thread name. On a fatal signal (SIGILL 4,
   SIGABRT 6, SIGFPE 8, SIGBUS 10, SIGSEGV 11): print all registers, read 48 bytes of code at
   `rip - 16` and 0x80 bytes of stack through the normal read command, and **leave the process
   stopped** so nothing is lost. Otherwise continue.

The decisive example is the slot-scan crash in [02](02-code-caves-and-hooks.md#8-the-sigsegv-root-cause-story).

### Minimal client (framing only)

```python
import socket, struct
MAGIC = 0xFFAABBCC
s = socket.create_connection(("<console-ip>", 744))
def cmd(op, body=b""):
    s.sendall(struct.pack("<III", MAGIC, op, len(body)) + body)
    return struct.unpack("<I", recv(4))[0]            # recv(n): loop until n bytes
def read(pid, addr, n):
    assert cmd(0xBDAA0002, struct.pack("<IQI", pid, addr, n)) == 0x80000000
    return recv(n)
def write(pid, addr, data):
    assert cmd(0xBDAA0003, struct.pack("<IQI", pid, addr, len(data))) == 0x80000000
    s.sendall(data)
    assert struct.unpack("<I", recv(4))[0] == 0x80000000
    assert read(pid, addr, len(data)) == data         # always verify
```

## 5. Reading and writing game memory safely

Rules learned the hard way:

- **Code patches must be one write.** A three-byte patch (`0F 95 C0` to `31 C0 90`) written as three
  separate one-byte writes passes through an invalid intermediate instruction; the game crashed on
  the first live test. The A/B tool therefore has a "hex bytes, one atomic write" format.
- **Restore in reverse dependency order.** Restoring a code cave to zeros *before* restoring the call
  site that jumps into it crashed the game. Restore hooks and call sites first, caves and data last.
- **Never rewrite a cave that may be executing.** Unhook, wait a few frames, rewrite, re-hook.
- **Do not read back flags the game consumes within a frame.** A "call request" flag cleared by a
  cave within one frame raced with the verification read and aborted 2 of 8 warps; such writes use
  no read-back.
- **Values the game rewrites every frame do not stick.** Scene parameters (for example the depth of
  field block) are overwritten within milliseconds; only a code patch persists. Param-table rows
  (camera distance, FOV, LOD) are persistent data and do stick.
- **Heap object addresses die with the game process, and also on death/respawn** for some objects.
  Tools re-find them by vtable scan on every run and "check" the vtable pointer before writing.

### Finding objects

- **Pointer chains from static globals**, e.g. the player is `[[0x593E878]+0x60]`.
- **Vtable scan** (`tools/dev/find_vtable_instances.py`, `ab_loop.py`): read every writable mapping of
  4 KiB to 1 GiB (skip the largest mapping, the GPU arena) in 8 MiB chunks, search for the 8-byte
  vtable pointer at 8-byte alignment. Gives all live instances of a class; some classes have several
  instances of which one is active (see the AA pass in [03](03-anti-aliasing-and-image-quality.md)).
- **Differential scans**: snapshot an object graph in two states (locked on / free, moving / idle),
  report fields that changed (lock-on target, camera angles). Breadth-first walks over pointer graphs
  from WorldChrMan found the lock-on entries.
- **Float-triple search**: look for a position-like triple within a known distance of another known
  position (found the physics body position from the camera position).
- **Static analysis**: a live dump of the image disassembled with Capstone; the game ships many
  debug-menu registration functions whose strings name fields (`AntiAliasType`, `MaxAnisotropy`,
  `CamDist`, ...), which give field order and meaning at essentially no cost.

## 6. How cheats get applied at game start

Details in [07](07-onionhen-integration.md); the short version:

1. The onionHEN daemon sees the `BigAppStarted` event at **exec time** (the game process has just
   been created and has not run its initialisation).
2. It asks the onionHEN utility process for the runtime cheat list, which creates a cheat session for
   the title.
3. Session creation **auto-applies every mod marked `"enabled": true`**: the game is stopped with
   SIGSTOP, each mod is written (write plus read-back verification, entries in file order), and the
   game is resumed with SIGCONT. A 128-write mod takes about 23 ms.
4. The game therefore starts with all patches already in place, which the frame-rate patches
   require. Applying them mid-run leaves already-initialised state at the old rate and crashed on
   gameplay entry.

Consequence for the camera mods: their caves and hooks are live **while saves and maps load**, so
every pointer they touch has to survive half-constructed objects ([02](02-code-caves-and-hooks.md)).

## 7. The screenshot hook, in one paragraph

The console's own screenshot function writes a 3840x2160 JPEG XR (`.jxr`) plus a `.meta` file to
`/user/av_contents/photo/NPXS40087/<title>/<hash>/`. The patched ShellUI payload caches the arguments
of one real screenshot button press and replays the managed `CaptureScreen` call whenever a file
`/system_tmp/onionhen/screenshot_request` appears, then writes `screenshot_ack` (`<epoch_ms> <status>`).
That lets a script take a screenshot at an exact moment. The image's `.meta` contains
`absoluteTime`, which is about `ack - 1.0 s` and is used to match images to experiment states. See
[04](04-scene-automation-and-measurement.md#2-screenshot-automation) for the full design and the numbers.
The 4K image is the system's upscale of the native 1080p render (spectral energy above the 1080p
Nyquist limit is identical to a native-1080p capture), so metrics are computed on a 2x2-reduced
1080p-equivalent.

## 8. Tool inventory (lab)

| Tool | Purpose |
|------|---------|
| `tools/dev/ps5dbg.py` | The protocol client above. |
| `tools/dev/crash_catch.py` | Debugger attach and crash capture (section 4). |
| `tools/dev/apply_live.py` | Write one mod of a cheat JSON into the running game: flags off, caves and data, hooks, flags on. |
| `tools/dev/ab_loop.py` | Generic live A/B loop: hold fixed writes, alternate states, optional scenes and screenshots, **always restores every touched address** in a `finally` block. State writes support formats `B/H/I/f` and `x` (hex bytes, one atomic write), addresses `vt:<vtable>+<off>` (one instance) and `vtall:<vtable>+<off>` (all instances), a `check` guard (an object address plus the qword expected there) and a `noverify` option. |
| `tools/dev/shot.py`, `collect_shots.py` | Remote screenshot trigger and image collection. |
| `tools/dev/scene.py`, `scenelib.py` | Repeatable scenes (player warp plus camera pose-lock), see [04](04-scene-automation-and-measurement.md). |
| `tools/dev/analyze_ab.py`, `make_strips.py`, `make_slider.py` | Image analysis and comparison. |
| `tools/mods/verify_against_dump.py` | Developer check: every cheat entry's `off` bytes against a dump of the unpatched process, and that every hook overwrites whole instructions (needs Capstone and a dump you make yourself). |
| `tools/mods/fill_off_from_dump.py` | Fill every entry's `off` with the original bytes from such a dump. |

The release cheat file is built by `tools/mods/build_cheats.py` from the per-mod generators; see
[02](02-code-caves-and-hooks.md) for the layout it enforces.
