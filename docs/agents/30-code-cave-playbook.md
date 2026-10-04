# 30 - Code cave playbook: writing a new mod

> Tested only on firmware 12.40 with a PS5 Pro, game `CUSA03173` v01.09. A mod that works here may behave differently on a base PS5 or other firmware: say so in your report instead of extrapolating.

This is the step-by-step recipe for adding or changing a mod with `tools/mods/caves.py`, followed by the verification pipeline and a catalogue of the mistakes that really crashed the game or wasted days. Read the catalogue (section 9) before writing any cave that runs every frame.

## 1. Choose the kind of patch

| Need | Patch type | Example in the repo |
|---|---|---|
| Flip a branch / constant / a few bytes | **inline patch**, one `on`/`off` pair | No Motion Blur (`74 16` -> `EB 16`), No DOF (`0F 95 C0` -> `31 C0 90`) |
| Change a constant a RIP-relative instruction reads | **operand redirect**: new constant in a cave, rewrite only the `disp32` | Wide FOV (`0x183AF5A` -> `0x54A0500`) |
| Replace a value the code loads | **hook that replaces the load**, cave loads something else and jumps back | DLAA threshold (`0x125970F`) |
| Run extra code every frame / read-modify-write live structures | **hook + cave**: `jmp rel32` over whole instructions, cave re-executes the displaced bytes and jumps back | head camera (3 hooks) |
| Intercept every call of one callee | **call-site redirect**: stub tail-jumps to the callee | Anisotropic 16x (`0x25D803D`) |
| Persistent PARAM table edit | **data write** (rows are persistent) | LOD_BANK / LOCK_CAM_PARAM_ST rows (not shipped) |

Prefer the smallest patch that works. Never write live-state fields that the game recomputes every frame (scene params, camera fields): patch the consumer instead ([10](10-memory-map.md)).

## 2. The `caves.py` API (all of it)

```python
from caves import Asm, rip, vss, vld, vst, hook5, hook
```

* `rip(at, insn_len, target)` -> 4-byte little-endian `rel32 = target - (at + insn_len)`: the displacement of a RIP-relative operand or a jump. `at` is the address of the instruction's first byte, `insn_len` its **total** length, so `at + insn_len` is the address of the **next** instruction.
* `Asm(base)`: builds code at virtual address `base`.
  * `raw(bytes)` append bytes.
  * `rip(opcode, target, imm=b"")` append `opcode` + `disp32` (to `target`) + `imm`. **`opcode` must include everything before the disp32** (prefixes, REX/VEX, opcode, ModRM with mod=00 rm=101). The displacement is computed with `len(opcode) + 4 + len(imm)`, so give the immediate in `imm`. Example: `cmp byte [rip+X],0` = `A.rip(b"\x80\x3d", X, b"\x00")`; `vmovups xmm5,[rip+X]` = `A.rip(b"\xc5\xf8\x10\x2d", X)`.
  * `jcc(cc, label)` near conditional jump (6 bytes); `cc` in `e, ne, ae, be, a, p, b` (opcodes `0F 84/85/83/86/87/8A/82`).
  * `jmp(label)` / `call(label)` near `E9` / `E8` to a label bound later; `bind(label)`; all label jumps are rel32 so cave size is never an issue.
  * `jmp_abs(target)` `E9` to an absolute address (used for the jump back to the game).
  * `done()` resolves labels and returns the bytes.
* `vss(op, d, s1, s2)` 2-byte-VEX scalar-single `xmm_d = xmm_s1 op xmm_s2` for `op` `0x58` add, `0x59` mul, `0x5C` sub; **only xmm0..xmm7**.
* `vld(x, base, disp)` / `vst(x, base, disp)` `vmovss xmm_x,[base+disp32]` / store; `base` is a register number 0..7 and must **not** be 4 (rsp, needs a SIB byte; `rdx` = 2, `rax` = 0).
* `hook5(at, cave)` = `E9 rel32` (exactly 5 bytes); `hook(at, cave, total)` = `jmp` + NOP padding to `total` bytes (use it so that **whole displaced instructions** are replaced).

Everything else is written as raw bytes with a comment on the instruction (see `make_head_camera_mod.py`). Disassemble the result with capstone (section 6) to check every byte.

### Worked example: the displacement math

DLAA cave: `vmovss xmm0,[rip+CONST]` at `CAVE=0x54A1300` is 8 bytes (`C5 FA 10 05` + disp32), so `disp = CONST - (CAVE + 8) = 0x54A1340 - 0x54A1308 = 0x38` -> `c5fa100538000000`; then `jmp BACK` at `CAVE+8` is 5 bytes: `rel32 = 0x1259714 - (CAVE + 8 + 5)`. FOV: the original instruction `vmulss xmm1,xmm1,[rip+disp32]` at `0x183AF56` is 8 bytes, next instruction `0x183AF5E`, original target `0x4D25E58`: `disp = 0x4D25E58 - 0x183AF5E = 0x034EAEFA` = bytes `FA AE 4E 03`. The generator **asserts** this against the bytes in the dump (`assert ORIG_DISP.hex() == "faae4e03"`): do the same for every displacement you derive.

## 3. Recipe

1. **Define the goal and the evidence plan.** What must change, and how will you measure it (fps via overlay, image metrics via the A/B pipeline, a value read back)? Write the success criterion down first.
2. **Find the consumer.** Locate the code that reads the value you want to change (static: debug-menu registration -> struct offset -> xref; live: change the value and watch what rewrites it, or use the debugger). If the value is rewritten every frame by the game, the consumer is the target.
3. **Pick the hook site** (section 4). Copy the displaced bytes (`ORIG`) from an **unpatched dump**, never from a patched run.
4. **Pick cave and data addresses** (section 5). The release map is in [10](10-memory-map.md); `build_cheats.py` refuses overlaps.
5. **Write the generator** `tools/mods/make_<name>_mod.py` (template below): constants at the top, `build()` returning the mod dict, `if __name__ == "__main__"` printing JSON. Entry order: **data -> caves -> hooks -> flag bytes last**; hooks carry `off` = original bytes; flags carry `on 01 / off 00`; caves and data blocks may leave `off` empty: `build_cheats.py` then sets `off = on` (onionHEN refuses to switch a mod off if any entry's `off` is empty; with `off = on` the caves are rewritten with the same bytes in file order and the hooks, which come last, restore the original instructions; never use zeros as `off` for a cave).
6. **Register it in `build_cheats.py`** (import, add to `mods`, decide the default; experimental mods default to `enabled: false`; a companion that needs another mod says so in its name, like "(needs head camera)").
7. **Build and check overlaps:** `python3 tools/mods/build_cheats.py --out /tmp/test.json`.
8. **Verify against the dump:** `python3 tools/mods/verify_against_dump.py /tmp/test.json <unpatched_dump.bin>` (you must provide the dump: [20](20-tooling.md) section 6).
9. **Disassemble your cave** and read it twice (section 6).
10. **Apply live** (section 7) in a safe place (Hunter's Dream), with the user warned and a save backup.
11. **Cold-start test** from the JSON (the real delivery path): the hooks are live while the game boots, loads saves and maps.
12. **Stress test** (section 8): load, roll, walk, ladder, death and respawn, teleport between maps, cutscene, toggle off/on, 10 minutes of play.
13. **Measure** your criterion with the A/B pipeline or a numeric read-back, including a **noise floor**.
14. **Document:** add the mod to `docs/features.md`, extend [10](10-memory-map.md) and `registry.json` (re-derive caves/hooks/data fields from the generator), add negative results to [80](80-experiments-log.md).

### Template

```python
#!/usr/bin/env python3
"""My mod: <what, where, why>.  Hook <addr> (<original instruction>) -> cave <addr>.  Order: data, cave, hook last."""
import json, struct, sys
from caves import Asm, rip, hook5

DATA, CAVE = 0x54A1C00, 0x54A1C10                 # must be free (zeros in the unpatched dump) and not overlap other mods
HOOK, BACK = 0x1259000, 0x1259005                 # example only
ORIG = bytes.fromhex("c5fa104618")                # displaced instruction(s), whole instructions only, from the dump

def build_cave():
    A = Asm(CAVE)
    A.rip(b"\x80\x3d", DATA, b"\x00"); A.jcc("e", "orig")      # cmp byte [rip+DATA],0 ; je orig   (runtime switch)
    # ... save registers, validate pointers, do the work, restore registers ...
    A.bind("orig"); A.raw(ORIG); A.jmp_abs(BACK)                # displaced instruction(s), then back
    return A.done()

def build():
    return {"name": "My mod (experimental)", "type": "checkbox", "enabled": False, "memory": [
        {"offset": "%08X" % DATA, "on": "01", "off": "00", "absolute": True},
        {"offset": "%08X" % CAVE, "on": build_cave().hex(), "off": "", "absolute": True},      # build_cheats.py fills empty off with on
        {"offset": "%08X" % HOOK, "on": hook5(HOOK, CAVE).hex(), "off": ORIG.hex(), "absolute": True}]}

if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
```

(Inline patches and operand redirects need no `Asm`: see `make_dof_mod.py` and `make_fov_mod.py`.)

## 4. Choosing the hook site

* **Whole instructions only.** `jmp rel32` is 5 bytes; if the instruction at the site is shorter, the following instruction(s) must also be displaced entirely; pad with NOPs to the boundary (`hook(at, cave, total)`). `verify_against_dump.py` checks the boundary with capstone. Existing: 5 B one instruction (`vmovaps [rbx+0x40],xmm3`), 6 B three instructions (`push rbp; mov rbp,rsp; push r15`), 7 B one instruction + 2 NOP (`add rsp,0x3D8`).
* **Displaced bytes must be position independent.** They are re-emitted verbatim in the cave: no RIP-relative operands, no relative jumps/calls among them (else you must re-encode them for the new address).
* **Know the registers and flags.** At the hook, which registers hold inputs, which are dead? Everything you use must be saved (`push`/`pop`) unless the code after the hook provably overwrites it. Read the code after the hook with capstone. Flags: your cave clobbers them (`cmp`, `vucomiss`); that is fine only if the displaced and following instructions do not read flags set before the hook (check with capstone for your site; the shipped hooks have run stably, the check itself was not recorded).
* **Know the thread.** A hook runs on whichever thread calls the function. The camera functions run on the game thread once per frame; a function called from several threads needs synchronisation of anything shared with your data block. The debugger stop packet names the thread (`CSChrThread4` ...).
* **Prefer one hook per feature at an epilogue or a store** where register meaning is stable: the follow-camera epilogue (`r13 = this`), the manager's pose store (`rbx = mgr`, `xmm0..xmm3` = right/up/forward/position), a per-frame call site.
* **Stack alignment:** at the follow-camera epilogue `rsp` is 16-byte aligned, so a `call` to a game function from the cave is legal there (the lab call service does this); check alignment before calling anything that uses SSE spills. The lab FACE code kept values in callee-saved registers across the call and relied on the epilogue's own pops.
* **Where not to hook:** inside the follow camera's update body (several paths write the pose rows; writes are overwritten within a frame); anything that the game rewrites from data every frame ([10](10-memory-map.md)).

## 5. Choosing cave and data space

* Region **`0x54A0000..0x54A4000`**; it must read as zeros in an unpatched dump (`python3 -c` over the dump, or `verify` script) and must not overlap another mod's range (checked by `build_cheats.py`) **nor the lab allocations** if you also use the lab tools ([10](10-memory-map.md) section 1).
* **Keep every `memory` entry <= 1024 bytes.** onionHEN skips longer entries silently but still writes the hooks, so the hook jumps into an empty cave and crashes the game; live ps5debug writes have no such cap, so a cave that works in a live test can still crash at game start. `build_cheats.py` splits caves/data into 1000-byte chunks automatically and asserts the cap; always finish a new cave with a cold-start test (restart the game, load a save).
* Align 16-byte vectors to 16 bytes (data used with `vmovaps` must be aligned; the generators keep all vector constants aligned).
* Allocate data in **one data block** with named offsets, give runtime variables a documented zero start, and keep constants live-tunable (the maintainers tuned `OFF_U`, `HMIN`, `ALPHA` by writing floats with ps5debug while playing).
* Leave gaps: the next feature will want space next to the data block.

## 6. Verify bytes before they touch the console

```python
# run from tools/mods (or put it on sys.path); pip install capstone
import re
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
import make_head_camera_mod as m                      # your generator
code, base = m.build_mgr(), m.CAVE_MGR
md = Cs(CS_ARCH_X86, CS_MODE_64)
for i in md.disasm(code, base):
    note = ""
    r = re.search(r"rip ([+-]) (0x[0-9a-f]+)", i.op_str)          # capstone prints [rip + 0x38]
    if r:                                                          # resolve the absolute target = next insn + disp
        note = "   ; -> 0x%X" % (i.address + i.size + (1 if r.group(1) == "+" else -1) * int(r.group(2), 16))
    print("%x: %-8s %s%s" % (i.address, i.mnemonic, i.op_str, note))
```

Check, line by line:

1. The disassembly decodes cleanly to the end with no `(bad)` and every instruction is the one you meant (VEX/RIP encodings are hand-assembled).
2. Every RIP-relative target lands in **your data block or a known global**, with the right field (print and compare against the constants).
3. Every `jmp/jcc/call` lands on a label inside the cave or on a documented `BACK`; the last instruction is the jump back; **every exit path pops exactly what was pushed** (count pushes and pops per path).
4. Displaced bytes equal the dump bytes at the hook; `BACK` = hook address + displaced length.
5. Every pointer you dereference was validated before the dereference (section 9, items 7-9).
6. NaN behaviour: `vucomiss` sets PF=ZF=CF=1 on unordered; every compare must send NaN to the safe path (`jp` first, or a condition that NaN satisfies, as the existing caves do).
7. `python3 tools/mods/verify_against_dump.py` prints `all match` and every hook `OK`.
8. `build_cheats.py` prints `no overlaps`.

## 7. Apply order, live apply and rollback

* **Apply:** data, caves, hooks last, flags last of all (`build_cheats.py` also fills `off = on` for caves/data). A hook goes live as soon as its 5-7 bytes land, so everything it jumps to must already be in place. **Switch off / remove:** flags first, then hooks (restore the original bytes), then (optionally) caves and data. Never clear a cave while its hook is live. Never rewrite a live cave: unhook, change, hook.
* **Write each code patch with a single write call** (several bytes torn across calls = transient invalid instruction).
* **Live apply** without relaunching: `python3 tools/dev/mods-live/apply_live.py /tmp/test.json "<mod name prefix>"` (writes flags 0 first, entries in order with read-back verification, flags on last), or `tools/dev/mods-live/code_patch.py` for single patches. Live apply happens while the game is running normally; it does **not** reproduce the cold-start conditions, so it is never sufficient on its own.
* **Cold start** is the real path: upload the JSON, ask the user to launch the game ([20](20-tooling.md) sections 4-5); check the klog for `auto-applied '<name>'`.
* **Rollback:** restore the previous cheat file (you backed it up), have the user relaunch. For a hung/crashed game the user closes it and dismisses the dialog.

## 8. Tests every cave that runs per frame must pass

Boot with the mod enabled in the JSON, then: main menu -> load save -> map load -> walk -> run -> **roll** -> ladder -> **die and respawn** -> **teleport between maps** (Hunter's Dream <-> Yharnam) -> lock on / lock off -> cutscene if any -> toggle the mod off and on from the menu -> 10 minutes of normal play. Also compare the timing: fps must stay at 60. Anything that uses live object layouts must be re-checked after a respawn (layouts change) and in both a 60 Hz and a 30 Hz pose map.

Do **not** toggle enemy/AI cheats at runtime during these tests: toggling "enemy movement" crashed the game inside its own `CSChrThread4` within seconds, repeatedly, independent of our mods.

## 9. Catalogue of mistakes that happened

Each row is something that really went wrong during development (sources in [80](80-experiments-log.md)); the fix is what is in the repository now.

| # | Mistake | Symptom | Cause | Fix / rule |
|---|---|---|---|---|
| 1 | Cheat offsets treated as `0x400000 + offset` | 134 valid-looking writes landed 4 MB too high; write and verify succeeded but the game crashed | onionHEN adds `sections[0].vaddr` unless `"absolute": true` | every entry `"absolute": true`; offsets are absolute VAs |
| 2 | onionHEN's code-cave mapping replaced the page with an anonymous mapping | the code page became zeros; "mid-run crash" and "crash at start-up" | `mapCodeCave` did `mmap(MAP_ANONYMOUS)` over the page | patched: only `kernel_mprotect(RWX)`, contents preserved (see [70](70-onionhen-cheat-engine.md)) |
| 3 | Timing patch toggled mid-run | crash on gameplay entry | frame loop already initialised at 30 fps | exec-time auto-apply with the process suspended |
| 4 | Multi-byte code patch written as several single-byte writes | transient `31 95 C0` (invalid) crashed the game during a live A/B | torn write | one atomic write per patch (`fmt:"x"`) |
| 5 | Cave cleared **before** its call site was restored | crash at the end of an A/B run | call into zeroed memory | restore hooks/call sites first (`restore_first`), caves after |
| 6 | Rewriting a cave that is live | random crashes while installing | game thread executing half-written code | unhook, rewrite, hook (scenelib does this) |
| 7 | Pointers dereferenced without validation | crash during load, save load, map change | at hook time, objects are null/freed/half-built; the old pose chain `[pl+0xA68]->[+0x50]` is empty/self-pointing in fresh saves | range check (`2 <= hi32 <= 7`), alignment, **vtable check** before every dereference; if any check fails the cave does nothing |
| 8 | "Is it a heap pointer?" test too loose (`hi32` 1..7) | SIGSEGV at cave `0x54A1792` (`vmovss xmm4,[rax+0xC]`, `rax = 0x100000CC3`) | the scan dereferenced the **flag value `0x1_0000_0003`** | `hi32 in 2..7` + 16-byte alignment + 120-frame back-off after a failed scan; found with the debugger (`crash_catch.py`) |
| 9 | The same test, window `2..7`, still too loose | SIGSEGV at cave `0x54A1C17` (`vmovss xmm4,[rax+0xC]`, `rax = 0x500000CC0`) after a respawn: the scan dereferenced the packed integer pair `0x5_0000_0000` | window `2..3` and low dword >= `0x10000` (both pointer checks); tested by dying repeatedly from a cold start |
| 9 | Fixed slot offset for the bone array | camera in third person, or garbage head | the array pointer slots differ per session/model build; after a respawn the arrays move to another holder | self-healing scan over holders `0x18/0x20/0x5F8`, slots `0..0x5F8` (step 8), remember the working pair (`HOLD`, `ARROFF`) |
| 10 | Used the model matrix translation `[pl+0x58]+0x350` as origin | after a respawn plausibility compared against zero, rejected everything: camera dropped to third person | the row is zero/NaN after a respawn | read the origin from the physics body `X+0x1E0` |
| 11 | Plausibility window `YMIN = 0.25` | camera flicked to third person at the end of a roll | during a roll the head is only 0.1 m above the origin | `YMIN = -0.5`; plus a height floor `HMIN` (1.25 m) so the view never dips into the body |
| 12 | Override of the follow camera's **own** position row | camera "tornado": 13 pitch flips per second, about 9400 deg/s | the pad code derives angles from the manager pose; head 0.1 m from the pivot makes the look-at unstable | override only the manager's **output copy** (`0x1836C54`), leave the follow camera's state alone |
| 13 | Collision pull-in against walls | the camera distance flickered 1.2 <-> 3.7 m per frame; orientation spun | the six collision casts of the follow camera | hook `0x1C090E0`, return "no hit" when NOCOLL |
| 14 | Forcing the player's facing every frame (write yaw + `0x1CBCF30`) | "tank controls": movement only forward | the game state was changed, not just the display | FACE2: rotate the **displayed** model->world rows only (hides coat/hood cloth, see [40](40-camera-system.md)) |
| 15 | Writing the follow camera rows/angles from outside | overwritten in < 12 ms | orientation is a look-at recomputed every frame via 5 code paths | hook the epilogue / manager store; never write from outside |
| 16 | Writing fields the game recomputes (`cam+0x180/0x184`, scene params) | value gone within a frame; `persisted after hold: NO` | per-frame computation / per-frame copy of scene data | patch the consumer or a persistent PARAM row |
| 17 | Raised FOV in the PARAM row above 48 deg | FOV stayed at 48 | code clamp 38..48 at `0x183AF2B..4E` | redirect the pi/180 constant instead (Wide FOV) |
| 18 | Aniso hook on a per-frame call | no visible effect in 3 scenes | the sampler objects are created at init; the table is read only then | a hook before sampler creation or an init patch would be needed (open) |
| 19 | Resolution patch timing | HUD broken, edges unchanged | patch landed after graphics creation; init order race | write all copies (globals + UI scale + copies) so the order does not matter |
| 20 | Verifying a flag the cave consumes within a frame | 2 of 8 warps failed | read-back raced the cave clearing `CALL` | `verify=False` for such flags |
| 21 | Raw position write for a 27 m move | the game restored all copies | only about 1 m is tolerated | the game's own warp `0x194B110` via the call service |
| 22 | Judged "AA off vs forced AA" without knowing the baseline | wrong conclusion | the baseline was already DLAA; the test layered FXAA2 on top | read the live state first (`aa_probe.py`) |
| 23 | A/B runs with fog and enemies on | brightness drift 7 %, sharpness noise of the same size as the effect, texture streaming broken after a death | moving fog layer; enemy kills the player | SFX-OFF during measurements, safe spots, discard runs with a death |
| 24 | Documented `mem = 0x400000 + cheat_offset` | wasted time | wrong note | correct rule: `mem = cheat_offset` (with `absolute`) |

### Classes of bugs to design against (listed by the maintainer; no logs recorded in the notes)

* **Wrong RIP displacement:** forgetting the immediate in the instruction length (`Asm.rip` takes `imm` for this reason), computing from the cave start instead of the next instruction, or copying displaced bytes that contain a RIP-relative operand. Guard: disassemble and resolve every target; assert recomputed original displacements against the dump.
* **Clobbered registers:** using xmm4..xmm7 or rsi/rdx as scratch where the continuing code still needs them; `chk()` in the head-camera cave clobbers `rsi` and the flags by design. Guard: read the continuation, save what you use, keep a single list of scratch registers per cave, and remember that although all xmm registers are caller-saved in the SysV ABI, a hook in the middle of a function is not a call boundary: the surrounding code may still hold live values in them.
* **Hook on the wrong thread / wrong function:** hooking a function that is also called from non-game threads, or from a loading thread when the structures you read do not exist yet. Guard: check the calling thread with the debugger, validate everything (rule 7).
* **Stack imbalance:** a path that pops less than it pushed returns into garbage. Guard: count per exit path.

## 10. Debugging aids

* **Counters/markers:** the lab cave increments `CNT` (`inc dword [rip+CNT]`) every run: reading it proves the cave executes and shows the frame rate of the hooked path (about 67/s for the camera epilogue).
* **Stage the cave:** first a cave that only re-executes the displaced bytes and jumps back (proves hook and BACK), then add behaviour behind a data flag, then enable the flag live.
* **Read the state back:** `mods-live/code_patch.py <addr> ?<len>` on the data block, `camera/hc_state.py` and `probes/respawn_state.py` style dumps (they compare live hooks, data and object chains with the expected values).
* **Crashes:** `crash_catch.py`; a `rip` inside the cave region is a cave bug (disassemble around `rip`), elsewhere check the hook/registers.
* An emulator (e.g. Unicorn) could run caves offline against synthetic memory; the maintainers have not tried it.

* **Never read the code of a system library (`libScePad.sprx`, `libkernel.sprx`, ...) from a cave.** Those mappings are execute-only (XOM): a `cmp dword [rax],imm` on a function address of libScePad faulted (SIGSEGV, error code 0x5 = read protection violation) and killed the game at the first run, although ps5debug could read the same bytes. Verify a library layout with the game's own data only (import-slot distances, page offsets) and read the library's *data* segments, which are readable. Found with the debugger: `python3 tools/dev/probes/crash_catch.py`.
