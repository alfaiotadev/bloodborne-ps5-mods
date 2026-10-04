# 02 - Code caves and hooks

The patching technique behind every non-trivial mod in this repository, the layout of the release
build, and the pitfalls that crashed the game while it was developed.

## 1. Why code patches

Almost nothing the mods need to change can be changed by writing data:

- Game objects (the AA pass, sampler table, camera) live on the heap and move on every start.
- Scene parameters (depth of field, AA enable, camera FOV rows) are re-derived from the scene every
  frame, so a data write survives a few milliseconds at best. A **code** patch at the consumer or at
  the writer persists.
- The 60 FPS patch is itself a set of code patches (frame-rate cap, time step, vsync handling).

So the mods are small code patches plus, for anything that needs real logic, **code caves**: our own
machine code written into unused memory and reached by a jump from the game's code.

## 2. The cave region

| Property | Value |
|----------|-------|
| Range | `0x54A0000`-`0x54A4000` (16 KiB, four pages) |
| Where | Inside the `eboot.bin` image, in a run of zero bytes (about `0x547F994`-`0x54DBFD0` in an unpatched dump); unused padding |
| Protection | The cave pages are made readable/writable/executable by the onionHEN write path (`kernel_mprotect` RWX in place; see [07](07-onionhen-integration.md#4-non-destructive-code-cave-mapping)) or are already so; the live ps5debug writes bypass protection through the direct map |
| Used by the release | Sparsely between `0x54A0400` and `0x54A1B7F` (table in section 5); everything above `0x54A1B80` is free |

Confidence: the region is confirmed usable (all caves in this document run there); the claim that it is
padding is from a dump of the unpatched process.

## 3. Anatomy of a hook

A **hook** diverts execution from the game's code into a cave. The cave runs our logic, re-executes
the instructions the hook displaced, and jumps back.

| Hook kind | Bytes written | Used for |
|-----------|---------------|----------|
| `jmp rel32` over whole instructions | `E9 <rel32>` (5 bytes) plus `90` NOPs up to the end of the last displaced instruction | Head camera (epilogue, manager, cast), DLAA threshold |
| Call-site retarget | new `E8 <rel32>` over an existing 5-byte `call` | Anisotropy (the stub tail-jumps to the original callee) |
| RIP-relative operand redirect | rewrite only the 4-byte displacement of an instruction that loads a constant | Wide FOV (points the load at a constant in the cave region; no cave code) |
| In-place opcode swap | same-length replacement, no cave | No depth of field (`0F 95 C0` -> `31 C0 90`), no motion blur (`74 16` -> `EB 16`) |

Rules the generators follow (checked by `tools/mods/verify_against_dump.py` against a dump of the
unpatched game, using Capstone):

1. **Overwrite whole instructions only.** A 5-byte `jmp` over a 7-byte instruction needs two NOPs, or
   the tail bytes decode as garbage. If the displaced instruction is longer than five bytes, the
   whole instruction is covered (`jmp` + NOPs) and re-executed in the cave.
2. **Only displace instructions without RIP-relative operands**, or re-encode them: copying a
   RIP-relative instruction into the cave changes its target. The shipped hooks displace
   `add rsp, 0x3D8`, `push rbp; mov rbp,rsp; push r15`, `vmovaps [rbx+0x40], xmm3` and
   `vmovss xmm0, [rsi+0x18]`, none of which has one.
3. **Know the register state at the hook point.** The caves save and restore the general registers
   they use (`rax, rcx, rdx, rsi`, and `r8, r9` in the manager cave). The manager and epilogue caves
   additionally clobber `xmm4`-`xmm7` and EFLAGS and **rely on them being dead at the hook site**;
   this is justified only by the fact that the game keeps working, not by a liveness analysis
   (inferred).
4. **Stack alignment:** a cave that calls into the game must keep `rsp` 16-byte aligned (the lab
   call-service cave at the follow-camera epilogue is entered with an aligned stack).
5. **A cave never trusts game state.** Anything it reads is validated (section 7). If any check
   fails, the cave does nothing and falls through to the original instructions, so the game runs
   its unmodified behaviour.

### The helper assembler

`tools/mods/caves.py` is a tiny x86-64 assembler so that no external toolchain is needed:

- `Asm(base)` collects raw bytes, supports RIP-relative operands (`A.rip(opcode, target)` computes
  `target - address_of_next_instruction`), `jcc`/`jmp`/`call` to labels with rel32 fix-ups, and
  `jmp_abs`.
- `vss`, `vld`, `vst` encode the few VEX scalar-single instructions needed.
- `hook5(at, cave)` returns `E9 rel32`; `hook(at, cave, total)` pads with NOPs to `total` bytes.

Everything produces plain bytes, which go into the cheat JSON as hex strings. Worked example, the DLAA
threshold hook (`tools/mods/make_dlaa_mod.py`):

```
0x125970F  c5 fa 10 46 18        vmovss xmm0, [rsi+0x18]      original: copy the scene's DLAA threshold
        ->  e9 ec 7b 24 04        jmp 0x54A1300                 hook (5 bytes, whole instruction)
0x54A1300  c5 fa 10 05 38 00 00 00  vmovss xmm0, [rip+0x38]    load the constant at 0x54A1340 instead
0x54A1308  e9 07 84 db fb        jmp 0x1259714                 back to the next instruction
0x54A1340  9a 99 99 3e           0.3f
```

## 4. Apply order, and restoring on "off"

onionHEN applies the entries of a mod **in file order**, with the game suspended. The generators
therefore always emit:

1. **Data** (constants, the head-camera configuration block),
2. **Caves** (code),
3. **Hooks last** (the entries that make the game jump into the caves),
4. For flag-gated mods, the **enable flag as the very last entry**.

A hook written before its cave would send the game into zeros. Removal runs the other way: hooks
and call sites first, caves and data last. The lab tools restore touched addresses in reverse order
of writing, with "call sites" restorable first.

**Restoring original bytes.** Every hook entry carries an `off` value equal to the original bytes
(taken from a dump of the unpatched process with `tools/mods/fill_off_from_dump.py` and re-checked by
`verify_against_dump.py`). Data and cave entries have an empty `off`: once the hooks are restored
they are dead storage.

> **Caveat (inferred from the onionHEN source, not tested on hardware).** onionHEN's toggle code
> rejects toggling a mod **off** as an "invalid patch" if any of its entries has an empty `off`. The
> release mods with cave or data entries (everything except 60 FPS, motion blur, chromatic
> aberration, intro logos, DOF, the DLC unlock and the one-byte FACE2 / aim flag mods) would therefore not be disable-able from the
> toolbox at runtime; the practical way to turn them off is to edit `"enabled"` in the cheat file and
> restart the game. See [07](07-onionhen-integration.md#11-runtime-toggling-and-its-limits).

## 5. Layout of the release build

All addresses are absolute virtual addresses. The "owner" is the mod (in
`cheats/CUSA03173_01.09.json`) that writes the entry.

### Hooks and patched game code

| Address | Size | Owner | Original bytes | Written | Return / target |
|---------|------|-------|----------------|---------|-----------------|
| `0x183AF5A` | 4 | Wide FOV | `FA AE 4E 03` (disp to `0x4D25E58`, pi/180) | `A2 55 C6 03` (disp to `0x54A0500`) | operand of `vmulss xmm1,xmm1,[rip+d]` at `0x183AF56` |
| `0x125970F` | 5 | DLAA threshold | `C5 FA 10 46 18` | `jmp 0x54A1300` | back to `0x1259714` |
| `0x25D803D` | 5 | Anisotropy | `E8 AE B7 9D FE` (`call 0xFB37F0`) | `call 0x54A0400` | stub tail-jumps to `0xFB37F0` |
| `0x25D7A8B` | 3 | No DOF | `0F 95 C0` | `31 C0 90` | in place |
| `0x1836C54` | 5 | Head camera | `C5 F8 29 5B 40` | `jmp 0x54A1600` | back to `0x1836C59` |
| `0x183F77B` | 7 | Head camera | `48 81 C4 D8 03 00 00` | `jmp 0x54A0780` + 2 NOPs | back to `0x183F782` |
| `0x1C090E0` | 6 | Head camera | `55 48 89 E5 41 57` | `jmp 0x54A1100` + 1 NOP | back to `0x1C090E6` |
| `0x26A057B` | 2 | No motion blur | `74 16` | `EB 16` | in place |
| `0x269FAA8` | 12 | No chromatic aberration | `8B 85 90 F5 FF FF 89 83 AC 00 00 00` | `C7 83 AC 00 00 00 00 00 00 00 90 90` | in place |

The 60 FPS mod (128 writes, 270 bytes in total), the intro-logo strings (`0x4D99138`, `0x4D99154`,
`0x4D9916E`, 4 bytes each) and the DLC unlock (`0x23B67B3`, 8 bytes) are plain in-place patches; see
[07](07-onionhen-integration.md#7-the-shipped-mods) and [`../../CREDITS.md`](../../CREDITS.md).

### Caves and data

| Range | Size | Owner | Content |
|-------|------|-------|---------|
| `0x54A0400`-`0x54A0485` | 134 | Anisotropy | Stub: writes `MaxAnisotropy = 16` into nine sampler fields, tail-jumps to the original callee |
| `0x54A0500`-`0x54A0503` | 4 | Wide FOV | `float` = pi/180 x scale |
| `0x54A0780`-`0x54A0905` | 390 | Head camera | Epilogue cave (FACE2: rotate the displayed body towards the camera) |
| `0x54A0E04`-`0x54A0E3F` | 60 | Head camera | Configuration block (bone offset, R/U/F offsets, plausibility limits, smoothing, holder) |
| `0x54A0E40`-`0x54A0E6F` | 48 | (runtime) | `LASTH`, `LASTO`, `OFFS`: latched head, latched origin, smoothed offset (written by the cave, not in the JSON) |
| `0x54A0E70` / `71` | 1 + 1 | Head camera | `NOCOLL` (collision cast off), `MODE` (camera override on); `MODE` is the last core entry |
| `0x54A0E72` | 1 | Lock-on aim mod | `AIM` flag |
| `0x54A0E73` | 1 | FACE2 mod | `FACE2` flag |
| `0x54A0E90`-`0x54A0E9F` | 16 | Head camera | `FALLV` fallback head offset `(0, 1.53, 0, 0)` |
| `0x54A0EA0`-`0x54A0EFF` | 96 | Head camera | Aim constants and SIMD masks |
| `0x54A0F18`-`0x54A0F1F` | 8 | Head camera | `TR`, `TU` (aim offset, initially 0) |
| `0x54A0F20`-`0x54A0F2F` | 16 | (runtime) | `FPREV`: the game's forward row of the previous frame |
| `0x54A0F30`-`0x54A0F3B` | 12 | Head camera | `DECAY`, `MOTCOS`, `TINY` |
| `0x54A1100`-`0x54A111A` | 27 | Head camera | Cast cave: returns "no hit" when `NOCOLL` is set |
| `0x54A1300`-`0x54A130C` | 13 | DLAA threshold | Cave (see the example above) |
| `0x54A1340`-`0x54A1343` | 4 | DLAA threshold | `float` threshold constant |
| `0x54A1600`-`0x54A1B7F` | 1408 | Head camera | Manager cave (head position, smoothing, aim, validation) |

The full data-block table with field meanings is in [05](05-fps-head-camera.md#7-data-block). The
generator `tools/mods/build_cheats.py` fails the build if any two mods write overlapping memory.
This is not cosmetic: according to the onionHEN source, the engine refuses to enable a mod whose
memory ranges overlap an already enabled mod (it reports a conflict). It is the reason the flag bytes `AIM` and `FACE2` are separate one-byte entries in
separate mods that do not overlap the core mod's entries.

> **Do not mix with the lab scene tooling.** The lab pose-lock cave ([04](04-scene-automation-and-measurement.md#4-camera-pose-lock-and-call-service))
> as documented there uses the same epilogue hook (`0x183F77B`), the same cave address
> (`0x54A0780`) and an older meaning of the same data block (`0x54A0E00...`). Running it while the
> released head-camera mod is active would overwrite the released epilogue cave and misinterpret
> its data. Use one or the other.

## 6. Hooking patterns in detail

### Per-frame call-site hook (anisotropy)

The game's post-effect apply function calls `0xFB37F0` (a `SetAntialiasEnable` wrapper) once per
frame at `0x25D803D`. Retargeting that `call` to a stub gives a once-per-frame execution point
without displacing any other instruction:

```
stub:  movabs r10, 0x59406C8        ; SprjGraphics pointer global
       mov r10, [r10] ; test ; jz done
       mov r10, [r10+0x250] ; test ; jz done          ; sampler descriptor owner
       mov dword [r10 + 0x360 + i*0x38 + 4], 16       ; i = 8..15 and 17 (nine stores)
done:  jmp 0xFB37F0                                    ; tail call; rdi/esi untouched
```

Only `rax`/`r10` change, so no save/restore is needed. (The mod works technically but has no
measurable visual effect; see [03](03-anti-aliasing-and-image-quality.md#anisotropic-filtering).)

### Constant redirect (FOV)

`vmulss xmm1, xmm1, [rip+disp]` at `0x183AF56` multiplies the camera row's FOV (degrees) by pi/180.
Pointing the displacement at a cave constant `pi/180 x scale` scales the FOV for every row. Write the
constant **first**, then the displacement; restore in the opposite order.

### Function-entry hook (collision cast)

The camera's six collision casts all call `0x1C090E0` (filter `0x25`); these six call sites are its
only callers. The hook replaces the 6-byte prologue with `jmp cave`; the cave returns `xor eax, eax;
ret` ("no hit") while a flag is set and otherwise runs the displaced prologue and jumps to `0x1C090E6`.

### Mid-function store hook (camera manager)

At `0x1836C54` the manager stores the camera position row (`vmovaps [rbx+0x40], xmm3`). A 5-byte hook
there lets the cave replace `xmm3` before the store, with the right/up/forward rows still in
`xmm0`-`xmm2`. This is the right place because it is **downstream of the game's own camera logic**:
nothing the game computes from its camera state is affected ([05](05-fps-head-camera.md)).

## 7. Pointer validation

Because the hooks are live from process start, the caves also run while saves and maps load, when
objects are half built, zero-filled or freed. The released caves validate with these primitives:

**Heap-pointer test** (`chk` in the generator):

```
mov rsi, reg ; shr rsi, 32 ; sub rsi, 2 ; cmp rsi, 5 ; ja fail
```

accepts exactly `0x2_0000_0000`-`0x3_FFFF_FFFF` with a low dword of at least `0x10000`. A value such as `0x1_0000_0003` (a flag, not a
pointer) is rejected.

**Vtable test:** `cmp qword [reg], <vtable> ; jne fail`. The objects in the walk are identified by
vtable before anything is read from them: `[pl+0x48]` = `0x579CF10`, the pose object
`[[pl+0x48]+0x18]` = `0x57A0820`, `[pl+0x58]` = `0x5770610`, `[pl+0x3B0]` = `0x5735D70` and the
physics body = `0x57356F0`.

**Alignment:** the bone arrays are 16-byte aligned; `test al, 0xF ; jnz fail`.

**Plausibility** (candidate head position against the model origin):

| Check | Limit | Purpose |
|-------|-------|---------|
| Height above origin | between `YMIN = -0.5` and `YMAX = 2.4` m | A real head, including roll |
| Horizontal distance from origin | squared < `R2 = 2.25` (1.5 m) | Belongs to this player |
| Distance to the game's own camera | squared < `LIMIT = 100` (10 m) | Rejects zeroed, garbage, NaN poses and cutscene cameras |
| FACE2 rotation sanity | `cos^2 + sin^2 >= MINN = 0.5` | Rejects degenerate camera/model rows |

Every comparison is written so that **NaN fails** (`vucomiss` plus a parity jump).

**Back-off:** after a failed slot scan the cave does not scan again for 120 frames (`COOL`) and
uses the fallback head offset in the meantime; scanning is the expensive operation.

## 8. The SIGSEGV root-cause story

**Symptom.** After the head camera moved from a live-written experiment to a cheat-JSON package
(hooks live from game start), the game crashed during save or map loading, and occasionally during
play. Earlier "crashes at load" had been seen too.

**Catching it.** The debugger attach ([01](01-platform-and-tooling.md#debugger-commands-0xbdbb00xx-and-port-755))
caught a `SIGSEGV` inside the manager cave:

```
rip = 0x54A1792    vmovss xmm4, [rax+0xC]
rax = 0x100000CC3
```

`0xCC3` is `0xCC0` (the head-bone offset `68 x 0x30`) plus 3, so the "array pointer" the cave was
using was `0x1_0000_0003`: not a pointer at all but a field value (a flag-like integer) in the model's
holder object.

**Cause.** The cave found the animated bone arrays by scanning the holder object slot by slot for a
value that looked like a heap pointer. The test was `0x1_0000_0000 < value < 0x8_0000_0000`, which
`0x1_0000_0003` passes. Reading `[value + 0xCC0 + 0xC]` then faulted.

**Fix.** The strict pointer window (upper 32 bits 2..3, low dword >= 0x10000 - a second crash, `rax = 0x500000CC0` at cave offset `0x54A1C17`, came from the packed integer pair `0x5_0000_0000` that passed the first window 2..7), 16-byte alignment, the plausibility checks
above, and the 120-frame back-off after a failed scan. The earlier load-time crashes were the same
class: **unchecked pointers into objects that are not yet (or no longer) valid**.

Related symptom without a crash: after the fix, the camera briefly dropped to the third-person view
at the end of a roll. The head was then only 0.10-0.25 m above the model origin, which the old
lower bound (`YMIN = 0.25`) rejected as "not a head"; widening the window to `-0.5` and adding the
height floor `HMIN` ([05](05-fps-head-camera.md#height-floor)) cured it.

## 9. Other crash stories (platform level)

| What went wrong | Cause | Fix |
|-----------------|-------|-----|
| Game crashed immediately or mid-run in the first 60 FPS tests | onionHEN's original `mapCodeCave` replaced the target page with an anonymous mapping, zeroing the surrounding game code | Make it non-destructive: only `kernel_mprotect` RWX in place ([07](07-onionhen-integration.md#4-non-destructive-code-cave-mapping)). This was the cause of both "crash mid-run" and "crash at start" symptoms seen earlier |
| All writes verified but the game crashed | Writes landed `0x400000` bytes too high | `"absolute": true` ([01](01-platform-and-tooling.md#3-why-cheat-json-offsets-are-absolute-virtual-addresses)) |
| Partially patched frame loop crashed | The game was running while the patch was being written | The engine freezes the game (SIGSTOP) for the whole auto-apply |
| Live DOF test killed the game | Three-byte patch written as three one-byte writes; intermediate state invalid | One atomic write per code patch |
| Crash at the end of every A/B run | Cave zeroed before the call site that jumps into it was restored | Restore call sites and hooks first |
| 2 of 8 scene warps crashed | Read-back of a request flag raced with the cave clearing it | No verify read on that flag |
| Crash on gameplay entry after runtime toggle of frame-rate patches | Game state already initialised at the old rate | Apply at exec time, do not toggle mid-run |
| Crash in the game's own thread `CSChrThread4` after toggling an enemy-AI cheat at runtime | Not camera related; runtime toggling of AI cheats is unsafe | Do not toggle such cheats during play |
| Camera cave did nothing / threw the view to third person after death | Respawned model had zero/NaN model matrix and moved bone arrays; plausibility test compared against zero | Origin from the physics body; holder search ([05](05-fps-head-camera.md#4-bone-arrays-and-the-holder-search)) |

## 10. Checklist for writing a new hook

1. Find the instruction boundary (disassemble a dump of the **unpatched** process; `verify_against_dump.py`).
2. Put constants and state in the data area, code in a cave, hook last.
3. Validate every pointer (window, alignment, vtable, plausibility); make NaN fail every comparison.
4. Preserve every register and flag you cannot prove dead; keep the stack aligned.
5. Put a runtime kill-switch byte in the data area and make it the last entry of the mod.
6. Give every hook entry the original bytes as `off`.
7. Run `build_cheats.py` (overlap check) and test a **cold start** with the mod enabled in the cheat
   file, then a load, a death and a respawn.
