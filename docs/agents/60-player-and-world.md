# 60 - Player and world: objects, position, warp, input, hazards

> Tested only on firmware 12.40 with a PS5 Pro, Bloodborne `CUSA03173` v01.09. Object layouts below were observed in Hunter's Dream and Yharnam (cold start, death/respawn, teleports); other areas may differ. Narrative and tables: [../research/06-player-world-and-camera-structures.md](../research/06-player-world-and-camera-structures.md), [../research/04-scene-automation-and-measurement.md](../research/04-scene-automation-and-measurement.md). Addresses: [10-memory-map.md](10-memory-map.md).

## 1. The object graph

```
G_WorldChrMan 0x593E878 --[g]--> WorldChrMan
   +0x60 --> player ChrIns "pl" (handle 10000)                      vtable read from [pl]
        +0x48 --> model container     (vt 0x579CF10)
              +0x18 pose object       (vt 0x57A0820)  -> bone-array slots (holder 0x18, before respawn)
              +0x20 holder            (vt 0x57A0F10)
              +0x5F0 object           (vt 0x57A1680)
              +0x5F8 holder           (vt 0x57A1500)  -> bone-array slots (after respawn)
        +0x58 --> module container    (vt 0x5770610)  -> model->world rows +0x320/0x330/0x340, translation +0x350
        +0x3B0 --> physics slot       (vt 0x5735D70)  +0x68 --> physics body X (vt 0x57356F0)
        +0x3F8  map id (u32)
        +0x4D0 --> hit boxes: [+0xE8] +0xDD0, 8 elements, stride 0xA0
        +0xA68 --> legacy model-space pose (empty in fresh saves)
```

Always check the vtable (`[obj]` equals the constant) before trusting a pointer; always range-check (high dword `2..3`, low dword >= `0x10000`).

## 2. Position, angles and what to write where

`X = [[pl+0x3B0]+0x68]`:

| Field | Meaning | Notes |
|---|---|---|
| `X+0x1E0` | position (x, y, z, 1), **Y up**, feet | read and write here; example (-111.02, -56.44, -20.01) |
| `X+0x1C0`, `X+0x1F0` | copies (previous / next) | `SetPosition` writes `0x1E0` and `0x1F0` |
| `X+0x1D0` | angles (pitchRad, yawRad, 0, 0); yaw = `X+0x1D4` (example -1.9228) | writing yaw persists in memory but the character does not turn until `0x1CBCF30(pl,1)` runs |
| `X+0x210` (u16), `X+0x32A` (u8) | flags set by `SetPosition` (`0x0101`, `1`); physics consumes and clears them (idle 0) | |
| `pl+0xC0`, `[pl+0x400]+0x30`, `[pl+0x60]+0x1B0` | further position copies | **do not write**; they are derived |
| `[pl+0x58]+0x350` | model origin (translation row) | zero/NaN after a respawn |

The game's own `SetPosition(chr, &pos)` is `0x1CC16A0`: `X+0x1E0 = X+0x1F0 = pos; word X+0x210 = 0x0101; byte X+0x32A = 1`; angle wrap `0x1CC1770`. A raw data write (`tools/dev/mods-live/player_warp.py`: `read`, `nudge dx dy dz [hold]`, `to x y z [yaw]`, `yaw dRad [hold]`) works for about **1 m** (flags consumed in < 50 ms, position stays); a **27 m** raw write is reverted by the game (it restores all copies). For long moves use the game's warp.

## 3. The game's own warp (via the call service)

`0x194B110(ctx = [0x593B148], &mapId, &pos, &rot)`, called by the load path `0x1948740`: reads the debug keys `SprjEzSelectBot.PlayerWarp.igPosX/Y/Z`, `degX/degY` (degrees -> radians through a global factor), `cDegX/cDegY` from the key/value store `0x593D710` (get `0x24EC0F0`, set `0x24EC3B0`; the save function `0x194EA30` formats `%.2f` and also sets `EnableBot = true`, `MoveMapStep.IsDebugExit = true`). It works **only if the map id equals the current map** (`[pl+0x3F8]`, compared with `[[0x593B120]+0xA7C]`). It returns the map id, sets the character yaw and resets the camera behind the character (pitch 0), which does not matter when the camera is pose-locked.

Arguments live in the lab scratch area `MAPID 0x54A0C00`, `POS 0x54A0C10` (x, y, z, 1), `ROT 0x54A0C20` (pitchRad, yawRad, 0, 0). The function must run on the **game thread**: the lab call service (`make_cam_pose_cave.py`: `FN`, `ARG0..3`, `RET`, `CALL`, executed by the follow-camera epilogue cave once per frame) does that. Measured: scenes A -> B -> A over 27 m and later up to about 100 m: position error **0.000 m**, yaw restored exactly, images phase-correlation shift (0,0). The `CALL` flag must be written without read-back (the cave clears it within a frame; reading it back raced and failed 2 of 8 warps). Tools: `tools/dev/core/scene.py`, `scenelib.py` ([20](20-tooling.md) section 9). These use the **lab** caves and collide with the release head camera.

## 4. Model, pose and drawing

* **Bone arrays (world space)**: 170 x 3x4 floats, stride 0x30, head 68 (details: [40](40-camera-system.md) and [10](10-memory-map.md) section 4). 3-4 copies, about one frame apart; **30 Hz in Yharnam** (all copies; origin and camera stay 60 Hz). Other maps were not measured systematically: re-measure with `probes/cadence_probe.py` before assuming 60 Hz.
* **Model->world rows** `[pl+0x58]+0x320/0x330/0x340` (R0, R1, R2, row-vector convention) and translation `+0x350`: head world = `R3 + t.x*R0 + t.y*R1 + t.z*R2` for model-space poses. Player model forward = `-R2`.
* **Legacy model-space pose** (`[pl+0xA68]->[+0x50]`): 108 `hkQsTransform` (stride 0x30: translation vec4, quaternion `x,y,z,w` at `+0x10`, scale vec4), head 78, neck 77; head-local axes in world: forward = +z, up = +x, right = -y. Empty in fresh saves.
* **Hit boxes**: `[[pl+0x4D0]+0xE8]+0xDD0`, 8 elements of stride 0xA0 (AABB-like); the head element's centre matched the head bone world position (an independent check of the bone chain).
* **Hiding the player (all failed):** the player's `SetDispMask` vtable slot (`[pl]` slot `+0x458`) is an empty `ret`; writing the 128-bit mesh mask at `[[pl+0x48]+0x18]+0x170` and the debug flag `Player Hide` (`0x593E88E`) changed nothing. Draw entities: manager `[0x593B168]` (strings `SprjModelDrawEntity` `0x4D34FAF`, `SprjAsmModelDrawEntity` `0x4D35003`); `SetDrawEnable` -> `0x17CA580` -> `0x19A6CA0` (id -> entity binary search); entity flags `+0x1FC` bit 14 = drawn (entity 0x2E0 bytes, blocks of stride 0x1F8 at `[M+0x28]`, count `block+0xC8`, base `block+0xD0`); `[[pl+0x48]+0x18]` reads like a draw entity. Whether clearing bit 14 hides the model was not tested (`read_entity.py`, `scan_entities.py`, `dump_entity.py` are the starting points).
* **FACE2** rotates the model rows for display and makes coat/hood cloth vanish ([40](40-camera-system.md) section 3.3): evidence that cloth-bearing objects follow those rows.

## 5. Enemies and lock-on

* The camera manager holds the lock-on state: `mgr+0x110 + n*0x80` (n = 0..5): `+0x110` target ChrIns pointer, `+0x120` lock point (world), `+0x130..+0x15C` target model matrix, `+0x180` local lock point (y about 1.48 m). Also `pl+0xF8 = 1`, `pl+0x110 = 2`, `cam+0x154 = 1.0` while locked.
* Finding ChrIns-like objects: BFS the object graph from WorldChrMan and accept objects whose position resolves via `+0x3B0 -> +0x68 -> +0x1E0` (`probes/lock_target3.py`, `lock_target_probe.py`). A global list of enemies was not located.
* Enemy AI/movement is on during measurements. A hit or death mid-run: heap objects are re-allocated (all `vt:`/`vtall:` addresses go stale: `persisted after hold: NO`) and texture streaming breaks until the area reloads. Choose safe spots, restore health, discard the run.

## 6. Time, frame rate and the fixed time step

* The 60 FPS mod rewrites the time-step constant at `0x243487E` (`mov dword [r12+0x18], imm32`: 1/30 `0x3D088889` -> 1/60 `0x3C888889`) together with the frame-limiter jumps and other constants (128 entries, derived from Lance McDonald's patch, [../../CREDITS.md](../../CREDITS.md)). It must be applied at **exec time**; mid-run toggling crashes on gameplay entry.
* The timestep object (`+0x18` dt = `0x3C888889`) is found by scanning heap objects for that dword (`probes/find_timestep_obj.py`; one run: object `0x20764A340`); writing 1e-6 there for 30 s **froze nothing** (an initialisation setting, not the per-frame dt). Static constants `0x59406E4`/`0x5940A54` are 1/60 literals.
* The overlay FPS and `onion_sample.py` are the only performance numbers the maintainers collected (60 fps held on the PS5 Pro in the tested scenes). No frame-time distribution, GPU or CPU load numbers exist, and **nothing is known for a base PS5**.

## 7. Input

* Right-stick rotation deltas come from `WorldChrMan+0x70/+0x80` and reach the follow camera at `cam+0x110/+0x120` (set in the manager update `0x18368B0`).
* **Left-stick values were not found** cleanly (`probes/stick_scan.py`, `stick_fields.py`: candidates were derived values).
* **Pad buttons:** the release generator reads the **DualSense report ring** of `libScePad` (12 reports x 0xE0 bytes, buttons dword first; ring at module base + `0x28BDC`, base derived from the game import slot `0x57E5B30`, function offset `0xA30`). The touchpad click is bit `0x100000`; the head-camera mod uses a double click to toggle `MODE`. In the ScePad API the L3/R3 button bits are `0x2` and `0x4` (general SDK knowledge, **not verified in this game**); R3 is the lock-on button in Bloodborne, so L3+R3 would collide with gameplay and the touchpad is the cleaner choice. onionHEN's built-in shortcuts only open menus (`cheats_menu`, toolbox keys) and have no free binding.
* A different pad source (hooking `scePadReadState`, reading the game's input structure) was not explored.

## 8. Hazards and test hygiene

| Hazard | Effect | Rule |
|---|---|---|
| Toggling enemy/AI cheats (for example "enemy movement") at runtime | crash within seconds in the game's `CSChrThread4` (`call [rax+0x18]` at `0x191E97B`, return `0x191E97E`; freed object) - seen more than once, independent of our mods | apply such cheats before the game starts; never include them in live tests |
| Crash during an autosave | a damaged save can result | back up the save before experiments that can crash; play offline |
| Crash dialog left open | the console can shut itself down | the user dismisses it |
| Death during a test run | objects re-allocated, streaming broken | discard the run; reload the area |
| Plain warps | textures are not unloaded; area changes (elevator/lamp travel) do | warm-up pass; compare only within one visit |
| Cutscenes / loading | pointers null or half-built | validate every pointer in caves |
| Heap addresses | change every launch and after death | resolve by vtable at use time |
| Online play | modified memory may violate terms of service | play offline |

## 9. Test locations used (names as in the notes)

Hunter's Dream (cottage, steps/pavement; mist moving: use SFX-OFF), Yharnam near the first lamp (ladder top, long view towards the sickroom doors; ladder up/down and the jump from the ladder are good head-camera tests), the bridge (burning rolling stone: dangerous for runs), corridor under the bridge (brick wall). Map ids observed: `0x18010000` (`m24_01`). Positions of the lab's scenes are not shipped; record your own with `scene.py record`.

## 10. Ideas not yet tried

| Idea | First step |
|---|---|
| Player/enemy scale multipliers (fun mod) | read the draw entity (`read_entity.py`), look for a transform scale in the entity (`0x2E0` bytes) or ChrIns model scale; try a live write and observe |
| Hide the player's model in FPS properly | test clearing entity flag bit 14 (`+0x1FC`) on the player's draw entity via `flag_toggle.py` (it restores); note FACE2 already hides cloth |
| Freeze/disable enemy AI **safely** for measurements | apply a start-up cheat before launch (never at runtime); or place the player where no enemy reaches; find a global enemy list from WorldChrMan with `lock_target3.py` |
| Invulnerability for test runs | find the HP field of the player ChrIns by differencing (hit/heal), freeze it live; verify it does not alter other behaviour |
| Position logging / speed readout | poll `X+0x1E0` at 60 Hz with `cadence2.py`-style loops |
| Persistent per-map scene library | extend `scene.py`; keep scenes outside the repo (they identify save-specific positions) |
| Find the left-stick/pad state | hook or read the pad report ring (already used for the touchpad) and map axes; compare with `stick_scan.py` results |
| Understand the post-death texture streaming break | snapshot the streaming manager before/after a death; `scan_rt.py <W> <H>` shows which descriptors are populated |
