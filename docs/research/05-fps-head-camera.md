# 05 - The FPS head camera

A first-person view for Bloodborne: the camera is bolted to the player's head bone, the game's own
camera logic (pad rotation, lock-on, cutscene handling) is left intact, and the whole thing is
applied as three small cheat-JSON mods from game start. This document gives the final design, then
the history: what was tried, every crash and its cause, and what failed.

> Platform: firmware 12.40, PS5 Pro, Bloodborne GOTY `CUSA03173` v01.09. "Confirmed" means exercised
> on the console and judged by the maintainer on the live picture (height, hood visibility, head bobbing,
> rolls, stick behaviour, loads, death/respawn, teleports). Release generator:
> `tools/mods/make_head_camera_mod.py`. Structure reference: [06](06-player-world-and-camera-structures.md).
> Hook technique: [02](02-code-caves-and-hooks.md).

## 1. What ships

| Mod (name in the cheat file) | Default | What it does |
|------------------------------|---------|--------------|
| **FPS head camera (experimental)** | off | Manager cave (camera position := head), collision-cast cave, FACE2 epilogue cave (inactive until its flag is set), all data. Turns itself on with its last entry (`MODE = 1`). |
| **FPS head camera: body faces the view (needs head camera)** | off | One byte: `FACE2 = 1`. Rotates the *displayed* body towards the camera direction. Side effect: coat and hood cloth parts disappear (section 8). |
| **FPS head camera: aim at the lock-on target (needs head camera)** | off | One byte: `AIM = 1`. While locked on, the view is aimed from the head at the target (section 9). |

Settings in the cheat file: offsets right / up / forward from the head bone `R/U/F = 0 / 0.30 / 0.32` (up was 0.17 up to v1.1.0 and was raised after play-testing: the view felt too low and small; forward was 0.22 until the final tests: with the body-facing option the model's face jumped in front of the camera when walking forward/backward; 0.32 fixed it)
m, height floor `HMIN = 1.25` m above the model origin, smoothing `ALPHA = 0.5`.

Not in the release: the pose-lock / call-service hook, the squeeze-hold, the old state-writing "FACE"
mode (all lab tooling, [04](04-scene-automation-and-measurement.md)).

## 2. Final design in one picture

```
 game frame
   |
   +-- camera manager update (0x18368B0)
         |   call follow-camera update (0x183AC60)   <- the game's own camera logic: pad rotation,
         |         |                                     chase, look-at, lock-on  (NOT touched)
         |         '-- epilogue 0x183F77B ----------- hook E: FACE2 (display only, optional)
         |         '-- 6 collision casts -> 0x1C090E0  hook C: return "no hit"
         |
         |   copy follow-camera pose into manager pose
         |   vmovaps [rbx+0x40], xmm3       <- 0x1836C54  hook M: our cave replaces the POSITION row
         '-- (manager pose is what the renderer uses)
```

Hook M is the heart. At that instruction the manager has just copied the follow camera's pose rows
into its own: `xmm0` = right, `xmm1` = up, `xmm2` = forward, `xmm3` = position (w = 1). The cave
replaces only `xmm3` (and, in aim mode, rewrites the rows) **in the manager's output copy**. The
follow-camera object keeps its own state, so everything the game derives from it (pad-driven angles,
lock-on, collision) behaves exactly as before. The viewing direction is the game's.

New position:

```
camera = origin(now) + S + R*right + U*up + F*forward          (right/up/forward = the game's rows)
S      = smoothed animated head offset from the model origin, floored at origin.y + HMIN
```

## 3. Head bone source

### Final: world-space bone arrays (confirmed)

| Item | Value |
|------|-------|
| Player | `pl = [[0x593E878]+0x60]` (WorldChrMan, handle 10000) |
| Model container | `mod = [pl+0x48]`, vtable `0x579CF10` |
| Pose object | `[mod+0x18]`, vtable `0x57A0820` (and other holders, section 4) |
| Arrays | The animated bone matrices **in world space**: 170 bones, each a 3x4 row-major float matrix, **stride `0x30`**, translation in column 3 (floats 3, 7, 11 of the matrix) |
| Head | **bone 68** (offset `68 * 0x30 = 0xCC0`); bone 67 is the neck |
| Copies | 3-4 copies of the array exist (successive pipeline stages, about one frame apart; measured with the lag probe). Any one is fine because the cave latches and smooths |
| Multiply | None needed; the matrices are already in world space |

Head position = `(m[3], m[7], m[11])` of the matrix at `array + 0xCC0`.

### Early version (superseded)

The first proof of concept used the model-space pose: an `hkQsTransform` array (stride `0x30`:
translation vec4, quaternion `(x,y,z,w)` at `+0x10`, scale), **108 bones**, reached by
`ChrIns -> [+0xA68] -> [+0x50]`, **bone 78 = head** (neck 77), and moved to world space with the
model-to-world rows `[pl+0x58]+0x320 / 0x330 / 0x340` (R0, R1, R2; row-vector convention) and the
translation row `+0x350`:
`head_world = R3 + t.x*R0 + t.y*R1 + t.z*R2`. That matched the centre of the head hit box (AABB at
`ChrIns+0x4D0 -> [+0xE8] +0xDD0`, stride `0xA0`). Head-local axes in world space: forward = +z, up =
+x, right = -y. The head orientation follows the *body*, not the right stick (the camera turned
355 degrees while the head yaw stayed), which is why the orientation is taken from the game's camera
and the head only supplies the position.

**Why it was replaced:** on a fresh save `[pl+0xA68] -> [+0x50]` was a self-pointer / empty; the
world-space arrays are the stable source. (Two different skeletons are involved: 108 model-space
bones with head 78, versus 170 world-space bones with head 68.)

## 4. Bone arrays and the holder search

The offsets of the array pointers inside the model structures **vary between sessions and after
respawn**. The cave therefore finds them itself.

Observed (confirmed): the array pointers sit in a sub-structure of four pointers (relative offsets
`+0`, `+8`, `+0xE0`, `+0x170`) embedded in a *holder* object:

| Situation | Holder | Slot offsets seen |
|-----------|--------|-------------------|
| Before death (cold start) | `[mod+0x18]` (vtable `0x57A0820`) | `+0x430/+0x570/+0x578`; `+0x320/+0x328/+0x400/+0x490`; `+0x450` |
| After respawn | `[mod+0x5F8]` (vtable `0x57A1500`) | `+0xC0/+0xC8/+0x1A0/+0x230` |
| Also seen | `[mod+0x20]` (vtable `0x57A0F10`, slot `+0x110`), `[mod+0x5F0]` (vtable `0x57A1680`) | - |

Search algorithm in the manager cave:

1. **Fast path:** use the remembered holder `HOLD` and slot `ARROFF`; if the candidate passes the
   plausibility test, done.
2. If that fails and the back-off counter `COOL` is non-zero: decrement it and use the fallback.
3. **Scan:** for each holder offset in `0x18, 0x20, 0x5F8` (inside `mod`), for each slot offset
   `0, 8, ..., 0x5F8`: test the candidate. The first plausible one is stored in `HOLD` / `ARROFF`.
4. Nothing found: set `COOL = 120` frames and use the fallback.

Candidate test (routine `P`): the holder pointer and the slot value must be heap pointers; the array
must be 16-byte aligned; the bone-68 translation must be between `YMIN = -0.5` and `YMAX = 2.4` m above
the model origin and within `R2 = 2.25` m^2 (1.5 m) horizontally ([02](02-code-caves-and-hooks.md#7-pointer-validation)).
Earlier lab notes describe a scan of `+0x300..+0x600` in one holder; the release code scans all slots
`0..0x5F8` of three holders.

## 5. The origin, the latch and the smoothing

### Origin from the physics body (confirmed)

The model-to-world translation `[pl+0x58]+0x350` is **zeros/NaN after a respawn**, so it cannot be
the origin. The cave uses the physics body instead: `X = [[pl+0x3B0]+0x68]`, validated by the vtables
`0x5735D70` (`[pl+0x3B0]`) and `0x57356F0` (`X`); the position `X+0x1E0` (x, y, z, 1) is the character's
feet and equals `ChrIns+0xC0`. The first version compared the head with the (zero) model matrix, so
the plausibility test rejected everything and the camera fell back to third person.

### 30 Hz pose, 60 Hz everything else (confirmed)

In Yharnam the pose arrays are re-evaluated at **30 Hz** (every copy; change interval 33 ms) while
the origin and the camera run at 60 Hz. Using the head directly made the bobbing step at 30 Hz. The
cave:

1. **Latches** `(head, origin)` into `LASTH`/`LASTO` whenever the array value changes (x,y,z all
   compared). Movement stays 60 Hz because the camera uses `origin(now)`.
2. Computes `T = LASTH - LASTO`, the animated head offset at the time the animation last updated.
3. **Smooths:** `S += ALPHA * (T - S)` each frame (`ALPHA = 0.5`), snapping when
   `|T - S|^2 >= SNAP2 = 1.0` (first frame, slot change). With a 60 Hz pose this equals the head
   position of the current frame.

The maintainer judged movement smooth and the bobbing soft again.

### Height floor

`HMIN = 1.25` m (generator; one lab note says 1.40): the camera's y is never below
`origin.y + HMIN`. Without it rolls and crouches dropped the view into the body ("the model jumps at
your eyes"). Walking head height is about 1.53 m, so the floor does not act while walking. Confirmed
"much better".

### Fallback

If no array is found (back-off active), `camera = origin + FALLV` with `FALLV = (0, 1.53, 0, 0)`: FPS
stays on without animation bobbing; confirmed in respawn tests.

### Validation against the game's camera

If the new position is farther than `sqrt(LIMIT)` = 10 m from the game's own camera position (zeroed,
NaN, or garbage poses; cutscene cameras), the cave keeps the game's camera.

## 6. Collision cast hook

The follow camera does six collision casts per update, all calling `0x1C090E0` (filter `0x25`; these six
call sites are the function's only callers). The game's camera pulled itself in against walls
and the cast result **flickered between about 1.2 m and 3.7 m every frame**; combined with the camera
being only 0.1 m from its pivot, that made the orientation spin. The cast cave returns `xor eax,eax; ret`
("no hit") while `NOCOLL = 1`, then the game's camera never pulls in. The game also re-sets a
"collision bit" at `0x5527A94` every frame from a parameter, so that bit is not a switch. This is
the only change to the game's own camera behaviour (confirmed).

## 7. Data block

All fields in `D = 0x54A0E00`. "JSON" = written by the cheat file; "run" = written by the caves.

| Offset | Address | Name | Type | Default | Meaning |
|--------|---------|------|------|---------|---------|
| +0x04 | `0x54A0E04` | `BONEOFF` | i32 | `0xCC0` (68 x 0x30) | Head bone offset in the array |
| +0x08 | `0x54A0E08` | `OFF_R` | f32 | 0.0 | Camera offset along the game's right row (m) |
| +0x0C | `0x54A0E0C` | `OFF_U` | f32 | 0.30 | ... up row |
| +0x10 | `0x54A0E10` | `OFF_F` | f32 | 0.32 | ... forward row |
| +0x14 | `0x54A0E14` | `ARROFF` | i32 | `0x320` initial; run: last working slot | Slot offset inside the holder |
| +0x18 | `0x54A0E18` | `LIMIT` | f32 | 100.0 | Squared max head-to-game-camera distance |
| +0x1C | `0x54A0E1C` | `MINN` | f32 | 0.5 | FACE2: minimum `cos^2 + sin^2` |
| +0x20 | `0x54A0E20` | `YMIN` | f32 | -0.5 | Lowest plausible head above origin (m) |
| +0x24 | `0x54A0E24` | `YMAX` | f32 | 2.4 | Highest plausible head above origin (m) |
| +0x28 | `0x54A0E28` | `R2` | f32 | 2.25 | Max squared horizontal distance head-origin |
| +0x2C | `0x54A0E2C` | `COOL` | u32 | 0; run: counts down from 120 | Scan back-off |
| +0x30 | `0x54A0E30` | `HMIN` | f32 | 1.25 | Height floor above origin (m) |
| +0x34 | `0x54A0E34` | `SNAP2` | f32 | 1.0 | Smoothing snap threshold (squared m) |
| +0x38 | `0x54A0E38` | `ALPHA` | f32 | 0.5 | Smoothing factor per frame |
| +0x3C | `0x54A0E3C` | `HOLD` | u32 | `0x18` | Holder offset inside the model container (`0x18`, `0x20`, `0x5F8`) |
| +0x40 | `0x54A0E40` | `LASTH` | 4 x f32 | 0 (run) | Latched head |
| +0x50 | `0x54A0E50` | `LASTO` | 4 x f32 | 0 (run) | Latched origin |
| +0x60 | `0x54A0E60` | `OFFS` | 4 x f32 | 0 (run) | Smoothed offset `S` |
| +0x70 | `0x54A0E70` | `NOCOLL` | u8 | 1 | Collision cast cave active |
| +0x71 | `0x54A0E71` | `MODE` | u8 | 1 (last entry) | Camera override on |
| +0x72 | `0x54A0E72` | `AIM` | u8 | 1 in its own mod | Lock-on aim on |
| +0x73 | `0x54A0E73` | `FACE2` | u8 | 1 in its own mod | Display-only body facing on |
| +0x90 | `0x54A0E90` | `FALLV` | 4 x f32 | `(0, 1.53, 0, 0)` | Fallback head offset |
| +0xA0 | `0x54A0EA0` | `AIMMIN2` | f32 | 0.09 | Aim: min squared distance to target (0.3 m) |
| +0xA4 | `0x54A0EA4` | `AIMMAX2` | f32 | 3600.0 | Aim: max squared distance (60 m) |
| +0xA8 | `0x54A0EA8` | `AIMCOS` | f32 | 0.3 | Aim: min cosine between the target direction and the game's forward |
| +0xAC | `0x54A0EAC` | `AIMWMIN` | f32 | 0.05 | Defined, not referenced by the shipped cave |
| +0xB0 | `0x54A0EB0` | `ONE` | f32 | 1.0 | Constant |
| +0xB4 | `0x54A0EB4` | `EPS` | f32 | 1e-6 | Looking straight up/down guard |
| +0xB8 | `0x54A0EB8` | `BETA` | f32 | 0.3 | Aim easing per frame |
| +0xBC | `0x54A0EBC` | `GAMMA` | f32 | 0.35 | Defined, not referenced by the shipped cave |
| +0xC0..+0xFF | `0x54A0EC0`.. | masks | 4 x 16 B | - | xyz mask `(~0,~0,~0,0)`, `(~0,0,~0,0)`, sign `(0,0,-0,0)`, sign-all |
| +0x118 | `0x54A0F18` | `TR` | f32 | 0 | Aim offset along the game's right row |
| +0x11C | `0x54A0F1C` | `TU` | f32 | 0 | Aim offset along the game's up row |
| +0x120 | `0x54A0F20` | `FPREV` | 4 x f32 | 0 (run) | Previous frame's game forward row |
| +0x130 | `0x54A0F30` | `DECAY` | f32 | 0.97 | Aim offset decay per frame while turning |
| +0x134 | `0x54A0F34` | `MOTCOS` | f32 | 0.99998 | "Camera is turning" threshold (cosine per frame) |
| +0x138 | `0x54A0F38` | `TINY` | f32 | 1e-6 | `TR^2 + TU^2` below this: no offset |

Code: manager cave `0x54A1600` (1408 bytes), cast cave `0x54A1100` (27), epilogue cave `0x54A0780` (390).
Hooks: `0x1836C54` (5), `0x1C090E0` (6), `0x183F77B` (7). Layout and bytes: [02](02-code-caves-and-hooks.md#5-layout-of-the-release-build).

### Tuning

The generator takes `--r`, `--u`, `--f` (camera offset in metres along the game's right/up/forward
rows), `--bone` (default 68) and `--arr` (initial slot offset, default `0x320`); the other values
are arguments of `build()`. Only `OFF_U`, `OFF_F`, `HMIN` and `ALPHA` at their shipped values were
judged on the console; the other effects in the table follow from the code.

| Value | Effect of raising it | Notes |
|-------|----------------------|-------|
| `OFF_U` (0.30) | Camera higher above the head-bone position | Default 0.30 since v1.2.0 (0.17 before; the view felt too low). With 0.17 / 0.22 the weapons are visible in the hands and the hood is out of the picture; 0.30 together with FOV x1.8 keeps the weapons well visible (maintainer's choice) |
| `OFF_F` (0.32) | Camera further forward | The forward shift that keeps the hood and the face out of the picture (0.22 let the face poke in front of the camera when walking). **Without head gear** (tested with the head slot empty instead of the Black Hood) the camera can sit further back: 0.08 was clean, 0.05 stayed clean even in hard movement and visceral attacks, 0.02 let the hair flicker into view. Hood items are not covered by the FACE2 cloth side effect, so with a hood keep 0.32 |
| `HMIN` (1.25) | Camera never lower than origin + `HMIN` | Must stay below the standing head height (about 1.53 m) or the floor acts while walking |
| `ALPHA` (0.5) | Faster smoothing (less lag, more visible 30 Hz stepping) | 1.0 = no smoothing |
| `SNAP2` (1.0) | Larger offset jumps are smoothed instead of snapped | Hard-reset threshold for the first frame and for slot changes |
| `LIMIT` (100) | Accept a head further from the game's camera | Lower values reject more garbage (inferred: also more legitimate fast moves) |
| `YMIN` / `YMAX` / `R2` | Plausibility window for the head bone | `YMIN` was 0.25 before rolls were considered |
| `AIMCOS`, `BETA`, `DECAY`, `MOTCOS` | Aim acceptance cone, easing, fade-out | See section 9 |

## 8. FACE2 - the body faces the camera (display only)

**Why:** with the camera in the head, the character's own body points where the game thinks it
faces, so strafing, backpedalling or turning shows the character's arms and torso in odd places.

**How:** at the follow-camera epilogue (`0x183F77B`) the cave rotates the model-to-world rows
`R2` (offsets `+0x340` x, `+0x348` z) and `R0` (`+0x320`, `+0x328`) of the module container `[pl+0x58]`
about the character root, so that the displayed model forward (`-R2`) points along the camera's
horizontal forward. With camera right row `(rx, rz)` and `R2 = (R2x, R2z)`:

```
cos = R2x*rz - R2z*rx        sin = R2z*rz + R2x*rx             (no trigonometry)
x' = x*cos + z*sin ;  z' = z*cos - x*sin                        (applied to R2, then R0)
```

Guarded by `cos^2 + sin^2 >= MINN (0.5)`. Only the display changes: the game's facing and movement state
is untouched, so moving sideways or backwards works normally (confirmed).

**Side effect (confirmed live):** while FACE2 is on, the **coat and hood cloth parts disappear**
(`FACE2 = 1`: coat gone; `FACE2 = 0`: coat back; changing equipment does not help). This explained the
earlier "hood flickers into view" observation. The maintainer considered the hiding possibly useful in
first person (no hood fluttering in front of the camera when walking backwards).
**FACE2 was not cold-start tested** (enabled at game start) when this was written, so it ships off
by default.

## 9. Lock-on aim (experimental)

### The problem

The game's lock-on camera looks at the **player's pivot** (`cam+0xA0..0xD0`), not at the enemy; the
player's head is exactly on the view ray, 3.7 m in front of the camera. The enemy appears above or to
the side of the screen centre depending on distance. When the camera moves to the head and keeps the
game's angle, the locked target ends up above the centre line (the closer, the higher).

### Finding the target (confirmed)

Differential scan of the camera manager (`mgr = [[0x593E860]+0x2830]`, the hook's `rbx`; manager
pose `+0x10/+0x20/+0x30/+0x40` = right/up/forward/position, R x U = F). Six identical entries at
`mgr + 0x110 + n*0x80` hold the locked target and are all zero when not locked:

| Field | Meaning |
|-------|---------|
| `mgr+0x110` | pointer to the target's ChrIns (0 = not locked) |
| `mgr+0x120` | **lock point in the world** (x, y, z, 1) |
| `mgr+0x130..+0x15C` | target model matrix (3x4) |
| `mgr+0x180` | lock point in the target's local space (y about 1.48 m) |

Other lock-on flags found: `pl+0xF8 = 1`, `pl+0x110 = 2`, `cam+0x154 = 1.0` (a lock factor that ramps
over about 1 s, so unusable as a trigger). The target is not visible as a pointer change in the
player's object graph (it is a handle), and the 4 KB follow-camera object has no lock flag.

### The aim

While `[rbx+0x110]` is a valid pointer (and `AIM = 1`):

1. `D = lockpoint - camera`; require `AIMMIN2 < |D|^2 < AIMMAX2` (0.3 m to 60 m).
2. `F' = D/|D|`; require `F'.F >= AIMCOS (0.3)` (the target is in front).
3. Express the aim as a **camera-space offset of the game's forward**:
   `TR = (F'.R)/(F'.F)`, `TU = (F'.U)/(F'.F)` against the game's own rows R, U, F; ease
   `TR += BETA*(target - TR)`, same for `TU`.
4. View forward = `normalize(F + TR*R + TU*U)`; rebuild the rows from the world up vector (no roll):
   `h = sqrt(Fx^2 + Fz^2)`, `right = (Fz, 0, -Fx)/h`, `up = (-Fy*Fx/h, h, -Fy*Fz/h)` (if `h^2 <= EPS`
   keep the game's view). Write the rows to `[rbx+0x10/0x20/0x30]` and reload `xmm0..xmm2`.

**After the release the offset stays** (the camera does not snap back to the game's direction). It
fades (`x DECAY = 0.97` per frame) only while the game's forward row moves faster than `MOTCOS`
per frame, i.e. while the player turns the camera, where the change is hidden by the motion.

### Iterations (judged by the maintainer on the console)

1. Hard on/off conditions (angle under 40 degrees) -> the aim jumped on late and flickered when close.
2. Using the game's own lock factor `cam+0x154` (rises over about 1 s) -> "pole, then a second
   later, face".
3. Returning to the game's direction on release -> the view "sinks and jerks".
4. Final: start immediately when a target is found, keep the offset after the release. Accepted as good
   enough; "someone else can make different profiles". It is a separate, experimental mod.

## 10. Failure and crash catalogue

| # | Symptom | Cause | Resolution | How found |
|---|---------|-------|------------|-----------|
| 1 | Camera inside/behind the character, hood cloth in view (distance 0.05-0.3 m) | The follow camera orbits the pivot; the hood is rendered | Offsets along the camera forward instead; later the head attach | live parameter edits |
| 2 | Distance 0: unstable; negative distance: camera passes through the pivot and **turns to look at the character from the front** (chest, chain, chin visible) | The orientation is a look-at from camera to pivot | Do not use the follow distance; override position downstream | `spec_fps_negdist` runs |
| 3 | Hiding the player did nothing | `Player Hide` (`0x593E88E`) and the model mesh mask (`[[pl+0x48]+0x18]+0x170`, 128 bits) do not affect rendering; the player's `SetDispMask` slot is an empty `ret` | Abandoned (the hood is out of the way by position, not by hiding) | byte-by-byte mask test |
| 4 | Camera "pulls back" when walking starts; seeing one's own face when turning | `ChrTransChaseRate` lag in the follow camera (0.1 per frame); the forward offset is in the character's local space | Chase fields were set to 1.0 / 0.5 in experiments (outcome not recorded); the head attach after the follow camera sidesteps the lag in the position | live parameter tests |
| 5 | Roll does not change the camera height | Pivot = root + fixed height | Head bone attach | observation |
| 6 | **Tornado**: the view spins randomly (13 pitch jumps per second, about 9400 degrees/s) with the head camera on | The first version overrode the position **inside the follow camera's own state** (epilogue mode; the original position restored at the function entry). The pad code derives the camera angles from the follow camera's pose; with the camera 0.1 m from its pivot, the look-at singularity throws the direction around. Collision and squeeze-hold were not the cause | **Manager mode**: override only the manager's output copy | logging the camera while the tornado was triggered |
| 7 | Camera pulled in against walls, orientation flicker | Collision cast result alternates 1.2 / 3.7 m per frame | Cast cave returns "no hit" | cast logging |
| 8 | Camera jumped when squeezed against a wall (lab version) | The game pulls the camera next to the pivot; look-at spins | A lab "squeeze hold" (show last good rows when closer than 1.5 m, release at 2.0 m); not needed after manager mode, not in the release | cam logs |
| 9 | Head chain empty on a fresh save | `[pl+0xA68]->[+0x50]` is a self-pointer there | World-space arrays via the model container | cold-start test |
| 10 | Array slot differs per session | Pose sub-structure embedded at varying offsets | Self-healing slot scan (`ARROFF`, section 4) | object layout probes |
| 11 | **SIGSEGV** at load | Slot scan dereferenced a flag value `0x1_0000_0003` that passed a loose heap test | Strict pointer window, alignment, back-off ([02](02-code-caves-and-hooks.md#8-the-sigsegv-root-cause-story)) | debugger attach and crash capture |
| 12 | Camera drops to third person at the end of a roll | Head only 0.10-0.25 m above origin; `YMIN` was 0.25 | `YMIN = -0.5`, `HMIN` floor | roll probe |
| 13 | Camera dips into the body in rolls ("model jumps at the eyes") | Head really is that low | `HMIN` | maintainer feedback |
| 14 | After death/respawn FPS is lost | Model matrix zero/NaN; holder moved from `[mod+0x18]` to `[mod+0x5F8]` | Origin from the physics body; three holders; `FALLV` fallback | respawn probes |
| 15 | Stepped bobbing in Yharnam | 30 Hz pose, 60 Hz camera | Latch and smooth | cadence probe (change interval 33 ms) |
| 16 | Tank controls with forced facing | "FACE": write the character's yaw to the camera yaw-pi and apply with `0x1CBCF30(pl,1)`; the game state turns, so movement is relative to a body that always faces the camera | Replaced by FACE2 (display only) | live |
| 17 | Coat/hood disappears | FACE2 rotates cloth-bearing matrices | Documented; FACE2 optional | live toggle |
| 18 | Camera pose rows cannot be overwritten externally | The update rewrites them in several paths and re-derives the orientation | Hook the single exit (pose-lock) or the manager copy | write tests (gone in <12 ms) |
| 19 | Left-stick values not found | Scans yielded only derived values | Not needed: the pad deltas flow `WorldChrMan+0x70/+0x80 -> cam+0x110/+0x120` (manager update `0x18368B0`) | `stick_scan` |
| 20 | No key combo for toggling FPS | Pad button bitmask not found | Toggle by enabling/disabling the cheat flags | - |

Left as is: at the start of **walking backwards** the character's silhouette briefly swings in front of
the camera (the game's turn animation twists the body); and the idle animation / roll orientation is
not damped (the head orientation is intentionally ignored; the view direction is the game's).

## 11. First attempt: "hood view" by parameters (history)

Before any hook on the manager, the camera was moved into the hood by editing the follow camera's
parameters (the `LOCK_CAM_PARAM_ST` rows, see [06](06-player-world-and-camera-structures.md#7-parameter-tables))
and by two 5-byte hooks that replaced the loads of `CamDist` (`0x183AE68`, `vmovss xmm1,[rsi]`) and
the pivot height (`0x183AEEF`, `vmovss xmm3,[rsi+0xC]`) with constants (distance 0.05 m, height 1.55
m) behind a flag byte; a forward shift `FWD` (the camera origin offset's z) of **+0.2 m** was the best
compromise (hood out of view). The hood sway from the idle animation, the lack of height change on
roll and the chase lag (rows 3-5 above) led directly to the head-bone idea.

## 12. Testing and tooling

- `tools/dev/apply_live.py <cheat.json> "<mod name prefix>"` writes one mod into the running game: the
  `MODE` and `FACE2` flags off first, then everything else in order, then the flags on last.
- `tools/dev/flag.py MODE=1 FACE2=0 NOCOLL=1` flips flags live; `hc_state.py`, `respawn_state.py`,
  `holders.py`, `obj_layout.py`, `arr_state.py`, `plaus.py`, `lag_probe.py`, `cadence_probe.py`,
  `roll_probe.py` are read-only probes (holder layout, array validity, pipeline lag, update cadence,
  rolling geometry).
- `tools/dev/crash_catch.py` ([01](01-platform-and-tooling.md#debugger-commands-0xbdbb00xx-and-port-755)).
- Cold-start test: enable the mods in the cheat file, start the game, load, walk, roll, die and
  respawn, teleport between areas (Hunter's Dream and Yharnam), lock on. Confirmed for the core
  mod; FACE2 cold start untested; lock-on aim confirmed by live use.
- Runtime toggling of an unrelated enemy-AI cheat crashed the game in its own thread `CSChrThread4`;
  that was not the camera.

## 13. Open ideas

- A pad-button toggle for FPS (the pad bitmask was not found).
- Damping the idle animation / roll in first person; ignoring the head orientation is deliberate.
- A scale multiplier for player and enemy models (found `SprjModelDrawEntity`, draw-entity table
  `[0x593B168]`, entity flags `+0x1FC` bit 14; not pursued).
- Damping the silhouette swing when walking backwards.
- Other aim profiles (the shipped one is one preference).

## Late additions (final release build)

- **Touchpad double-click toggle.** The game's touchpad click opens its personal-effects menu, so a double-click (two rising edges within 30 frames) was chosen as the switch. The DualSense report ring of libScePad (12 entries of 0xE0 bytes, buttons dword first; L3 0x2, R3 0x4, touchpad 0x100000) lives in the library's data segment; its base is derived from two game import slots (`0x57E5B30` -> libScePad+0xA30, `0x57E4E90` -> +0x13C0). The first version verified the module by comparing function bytes and crashed the game at load because system-library code is execute-only (XOM); found with the debugger (`rip` in the cave, error code 5). The ring was located by diffing the library's RW data while buttons were mashed; the stick bytes and timestamps in each entry identify it as a raw controller report.
- **Mode-dependent FOV.** The cave copies `FPSFOV` or `TPFOV` into the Wide-FOV constant every frame depending on MODE, so first person can use x1.8 (x1.5 up to v1.1.0) and third person stays at x1.3.
- **Delivery constraints found the hard way.** onionHEN limits each cheat entry to 1024 bytes (longer ones are skipped while the hooks are still written, which crashes the game at the first run of the cave - the generator now splits caves into 1000-byte chunks), refuses to switch a mod off when an entry has an empty `off` (the generator sets `off = on` for caves and data), and the cave's own cached state (holder, slot, back-off) must never be part of a written entry because a runtime toggle would reset it and force a full memory scan in the live game.
