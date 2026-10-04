# 04 - Scene automation and measurement

How the project got repeatable screenshots out of a game that never stands still: a remote screenshot
trigger, a player warp, a camera pose-lock, the A/B loop that ties them together, the texture-streaming
and environment gotchas, and the comparison tools. The numbers produced with this pipeline are in
[03](03-anti-aliasing-and-image-quality.md).

> Platform: firmware 12.40, PS5 Pro. The tools were run from a lab host that talks to the console
> over the network ([01](01-platform-and-tooling.md)). Confidence: everything below was exercised on
> the console unless marked *inferred*.

## 1. The problem

Image-quality effects of 1-5 % have to be separated from: moving fog and particles, foliage and
cloth animation, the player's idle animation, eye adaptation (brightness drift), camera position and
texture streaming state. Without control, noise is +-4-10 % and every early anisotropy and DOF "result"
was an artefact. The fix has four parts, each described below:

1. a way to take a screenshot at an exact, scripted moment,
2. a way to put the player and the camera at exactly the same pose every time,
3. a loop that alternates states and always restores memory,
4. an environment with the main drift sources removed, plus statistical hygiene (ABAB, warm-up).

## 2. Screenshot automation

### Design

The screenshot comes from the console's own screenshot function, so the image is exactly what a
button press would produce (4K JPEG XR, see [01](01-platform-and-tooling.md#7-the-screenshot-hook-in-one-paragraph)).
The function is called from the **ShellUI** process (a managed, Mono-based runtime). The onionHEN
ShellUI payload was extended ([07](07-onionhen-integration.md#9-screenshot-hook)):

1. The existing `CaptureScreen` hook (old and new signature) **caches the arguments** of a real button
   press: instance, user id, device id, capture type, format string, capture-info object. The managed
   objects are pinned with GC handles so they stay valid.
2. A per-frame hook on the UI thread (`OnRender_Hook`) runs every sixth frame and looks for the file
   `/system_tmp/onionhen/screenshot_request`. If present it is consumed, and the *original*
   `CaptureScreen` is called with the cached arguments (a flag keeps the replay from re-caching).
3. The result is written to `/system_tmp/onionhen/screenshot_ack` as `<epoch_ms> <status>` and the
   armed state to `screenshot_state` (`valid=1 presses=N user=.. device=.. type=.. args=4|5`).

| Status | Meaning |
|--------|---------|
| 0 | `CaptureScreen` was called |
| 1 | Not armed: no real screenshot has been pressed since ShellUI started |
| 2 | The original function pointer is missing |

**Arming:** press the screenshot button once on the console after ShellUI has loaded. The state resets
whenever ShellUI restarts or the console reboots. The lab tools check this first ("pre-flight shot") and
refuse to start a run that would produce no images.

The trigger is a file on the console's FTP-visible filesystem, so any script on the network can use it
(`tools/dev/shot.py`: `state`, `N [interval]`, or `shot.trigger()` returning `(ok, ack_epoch_ms, status)`).

### Timing and matching

- The photo's `.meta` file has `absoluteTime` (epoch milliseconds, the console's clock). It equals
  about **`ack_epoch_ms - 1.0 s`**; matching uses a +-0.7 s tolerance. That is how images are assigned
  to experiment states even for short hold times; a fallback uses the time window of the active state.
- **Toast notifications are not captured** in screenshots, so the delay between a state change and
  the shot can be short (1-2 s: enough for the change to appear; camera and FOV changes ease in over
  about 1 s). In practice `shot_delay` was 2 s.
- Verified runs: manual arming and a remote trigger both stored images; a four-state FOV A/B produced four
  images, all status 0, each landing in the right state window (+6.4..6.6 s after the switch with
  `shot_delay` 6-7); vertical FOV measured from the images (x1.3 -> 56.1 degrees, x1.6 -> 68.8,
  control 43.0) matched the hand-taken images.

### Collecting the images

`tools/dev/collect_shots.py <ab_loop log> <outdir> [--n 40]` parses the A/B log (state lines
`console_epoch_ms=<ms> | state i/N = <scene> :: <state>`, shot lines `ack_epoch_ms=<ms>`,
`RESTORED all`), lists the newest N photos under `photo/NPXS40087/<title>/<hash>/`, matches each
`.meta` `absoluteTime` to a shot acknowledgement and downloads
`NN_<scene>__<state>_<k>.{jxr,meta}` plus `manifest.json` (scene, state, state index, matched-by
`ack` or `window`, offset into the state). Tested 4 of 4 correct.

### Image format notes

Original JXR is about 0.5 MB, already smaller than any lossless conversion (4K PNG 7.0 MB, 1080p
Lanczos PNG 2.4 MB, lossless WebP 4K 5.7 MB / 1080p 1.8 MB, WebP q92 4K 0.79 MB / 1080p 0.34 MB). Keep
JXR plus `.meta` as the archive; use lossless images for measurement; lossy WebP only for viewing.

## 3. Player position and warp

The structures behind this are listed in [06](06-player-world-and-camera-structures.md); here is how
they are used.

**Position.** The player ChrIns is `pl = [[0x593E878]+0x60]`. The physics body is
`X = [[pl+0x3B0]+0x68]`:

| Field | Offset | Notes |
|-------|--------|-------|
| position | `X+0x1E0` | `(x, y, z, w=1)`, **Y is up**; copies at `X+0x1F0` (current/next) and `X+0x1C0` (previous) |
| angles | `X+0x1D0` | `(pitchRad, yawRad, 0, 0)`; yaw at `X+0x1D4` (measured -1.9228 rad in one test) |
| move flags | `word X+0x210 = 0x0101`, `byte X+0x32A = 1` | set by the game's `SetPosition`; the physics step consumes and clears them (0 at rest) |

Other copies of the position exist in sub-modules (`[pl+0x400]+0x30`, `[pl+0x60]+0x1B0`, ...); **write
to `X`, not to those.**

**Raw nudges.** A 32-byte write covering `X+0x1E0` and `X+0x1F0`, followed by the two flags, moved the
player 1 m and back (flags are consumed in under 50 ms and the position holds). Limits: a 27 m
raw move does not stick (the game restores every position copy), and writing the yaw (`X+0x1D4`) stays
in memory but the character does not turn, because the angle is only applied by the function at
`0x1CBCF30(pl, 1)`.

**Game warp (used for everything real).** The editor's "PlayerWarp" tool inside the game
(`0x194B110(ctx = [0x593B148], &mapId, &pos, &rot)`, called from the load path at `0x1948740`)
reads its parameters from a key/value store (`SprjEzSelectBot.PlayerWarp.igPosX/Y/Z`, `degX/degY`,
`cDegX/cDegY`; store at `0x593D710`, get `0x24EC0F0`, set `0x24EC3B0`). Called directly with
`mapId = [pl+0x3F8]` (for example `0x18010000`), `pos = (x, y, z, 1)` and `rot = (pitchRad,
yawRad, 0, 0)`, it moves the physics, sets the character's yaw and resets the follow camera behind
the player (pitch 0). It **only works inside the current map** (the map id's `m<num>` part must equal
the current map, `[[0x593B120]+0xA7C]`). A game-side saver (`0x194EA30`) also sets `EnableBot = true`
and `MoveMapStep.IsDebugExit = true`; those were not needed.

Calling a game function from outside requires running on a game thread: the **call service** below.

## 4. Camera pose-lock and call service

### Why a hook is needed

The follow camera (`cam = [[[0x593E860]+0x2830]+0x60]`) keeps its pose rows at
`cam+0x10 / +0x20 / +0x30 / +0x40` (right / up / forward / position). **They cannot be written from
outside**: the overwrite is undone in under 12 ms. The update function `0x183AC60` integrates
rotation deltas into several matrices and computes the orientation as a **look-at from the camera
position to the pivot**; several code paths write the rows (`0x183B399`, `0x183EBB2`, `0x183EC5E`,
`0x183EFC0`), and `cam+0x140/0x144` (pitch/yaw) and `cam+0x2E0` are derived copies. No raw angle state
or quaternion could be found (diff scans over the object found nothing usable). The solution is to
force the final result with a hook at the function's single exit.

### The hook (lab design)

| Item | Value |
|------|-------|
| Hook | `0x183F77B`: `add rsp, 0x3D8` (7 bytes) -> `jmp cave` + 2 NOPs; return `0x183F782` (the only epilogue of the follow-camera update) |
| Cave | `0x54A0780` (143 bytes in the original pose-lock-only build) |
| `FLAG` | `0x54A0700` (u8) |
| `CALL` | `0x54A0702` (u8) |
| `CNT` | `0x54A0704` (u32 run counter; about 67 per second measured, roughly the camera update rate - the difference from 60 was not investigated) |
| `ROW0..ROW3` | `0x54A0710`, `0x54A0720`, `0x54A0730`, `0x54A0740` (16 bytes each: right, up, forward, position) |
| `FN`, `ARG0..ARG3`, `RET` | `0x54A0750`, `0x54A0758..0x54A0770` (rdi, rsi, rdx, rcx), `0x54A0778` |
| Warp scratch | `MAPID 0x54A0C00`, `POS 0x54A0C10` (x,y,z,1), `ROT 0x54A0C20` (pitchRad, yawRad, 0, 0) (an earlier note gave `0x54A0900/10/20`; the script constants are authoritative) |

Cave logic, in order:

1. `CNT++`.
2. If `FLAG != 0`: copy `ROW0..3` into `[r13+0x10 .. 0x40]` (`r13` = the follow camera). The camera
   manager copies the pose out of this object immediately after the call, so the rows are final.
3. If `CALL != 0`: clear it and call `FN(ARG0..ARG3)` on the game thread (SysV order; `rsp` is aligned
   at this point; `r13` and other callee-saved registers survive), store `rax` in `RET`.
4. Run the displaced `add rsp, 0x3D8` and jump back.

Client side: write `FN` and the arguments, set `CALL = 1`, poll until it reads 0, read `RET`. **Do not
read the flag back with verification**: the cave clears it within a frame, and the race between the
verify read and the cave aborted 2 of 8 warps in an early run.

**Install/remove discipline:** unhook first, write the cave, hook last. Never rewrite a cave that
is executing. The hook is harmless when `FLAG = 0` and `CALL = 0` and disappears when the game
restarts; `scene.py remove` takes it out by hand.

> The released head-camera mod uses the same hook address and the same cave address for a different
> purpose (FACE2) and a different data-block meaning ([02](02-code-caves-and-hooks.md#5-layout-of-the-release-build)).
> Do not run the lab scene tools while the released head-camera mod is enabled.

### Orbit lock

`cam_lock.py lock --yaw <deg> --pitch <deg>` rotates the whole camera frame (rows and position) rigidly
about the player's position, so the character stays at the same spot on screen (verified offline and
live); `--spin` rotates in place, in which case the character drifts to the edge. The lock is immediate
(no easing) and releasing it returns instantly to the game's own camera, which is exactly what
automation needs.

## 5. Scenes

A **scene** = map id + player position + player yaw + the absolute final camera pose
(`cam` rows as 64 bytes of hex). Stored in `scenes.json`:

```json
"<name>": { "map": 402718720, "player_pos": [x, y, z], "player_yaw": -2.3089,
            "cam": "<128 hex digits: right,up,forward,position rows>", "note": "...", "recorded": "..." }
```

`tools/dev/scene.py` (thin CLI over `scenelib.Scenes`):

| Command | Effect |
|---------|--------|
| `record <name> [note]` | Store the current player position, yaw and camera pose |
| `goto <name> [--wait 5.0] [--keep-yaw]` | Lock the camera to the stored pose, game-warp the player (same map only), wait; camera stays locked |
| `shot <name> [--wait 5.0] [--keep]` | `goto`, remote screenshot, release the camera |
| `sweep <scenes..> [--passes N] [--warmup W] [--wait 5.0] [--log f.jsonl]` | W warm-up passes (no shots), then N measured passes; one JSON log line per shot (`pass, scene, err_m, ack_epoch_ms`) |
| `settle <name> [t1 t2 ..]` | Warp, then a shot at each given second (texture-streaming measurement) |
| `nowarp`, `release`, `list`, `install`, `remove` | Harmless self-test; camera lock off; list; hook management |

`Scenes.go` order: install the hook, set the camera lock (absolute pose first), then warp the player and
yaw, then wait; it returns the position error in metres.

**Reproducibility, measured:** bridge A -> B -> A (27 m): position error 0.000 m, yaw restored exactly,
phase-correlation shift `(0, 0)` px, mean luma difference 4.6 between the two A shots (clouds, fog,
plants, idle animation) against 24-25 between A and B. Four real scenes x 2 rounds with moves of up
to about 100 m: position error 0.000 m and shift `(0, 0)` everywhere.

### The test scenes

All are in one Yharnam map (`0x18010000`, i.e. `m24_01`), because warps work only within a map.
(The identifiers in `scenes.json` are Finnish; a rough translation is given.)

| Identifier | What | Purpose |
|------------|------|---------|
| `silta_paa_mukulakivi` | End of the long bridge, cobblestone at a shallow angle | anisotropy, FOV, AA |
| `sillan_alla_tiiliseina` | Under the bridge, brick wall at a steep angle, far | anisotropy, LOD; **dropped from some runs: an enemy killed the player** |
| `sickroom_aidat_aa` | Sickroom, long fences, even lighting | AA |
| `nuotio_tikkaat_horisontti` | Bonfire and ladders, long view to the horizon | LOD, distance; **textures did not stream in after a restart** |
| `bridge_a`, `bridge_b` | Bridge, two points 27 m apart | function tests of the warp |

## 6. The A/B loop

`tools/dev/ab_loop.py spec.json` holds fixed writes for the whole run, alternates **states**, logs
every switch (with the console clock, `console_epoch_ms`) and **always restores every touched
address** in a `finally` block. A representative spec:

```json
{
  "hold": 4, "shot_delay": 2, "toast": false, "warmup": 1, "scene_wait": 5,
  "scenes": ["sickroom_aidat_aa", "silta_paa_mukulakivi"],
  "sequence": ["game DLAA", "thr 0.3", "game DLAA", "thr 0.3"],
  "fixed": [ {"addr": "vt:0x57b9080+0x5c6", "fmt": "B", "val": 1} ],
  "states": {
    "game DLAA": [ {"addr": "vtall:0x56e7980+0x8", "fmt": "B", "val": 0} ],
    "thr 0.3":   [ {"addr": "vtall:0x56e7980+0x8",  "fmt": "B", "val": 1},
                   {"addr": "vtall:0x56e7980+0x9",  "fmt": "B", "val": 1},
                   {"addr": "vtall:0x56e7980+0xc",  "fmt": "I", "val": 3},
                   {"addr": "vtall:0x56e7980+0x28", "fmt": "f", "val": 0.3},
                   {"addr": "vtall:0x56e7980+0x2c", "fmt": "f", "val": 2.44},
                   {"addr": "vtall:0x56e7980+0x30", "fmt": "f", "val": 0.25} ] }
}
```

| Key | Meaning |
|-----|---------|
| `hold` | Seconds each state is held |
| `sequence` | State order (ABAB etc.) |
| `fixed` | Writes held for the whole run (here: the fog layer off) |
| `states` | Map of state name to writes |
| `shot_delay` | Take a remote screenshot this many seconds after each switch |
| `scenes` / `scenes_file` / `$SCENES` | Run the whole sequence once per scene (camera lock + warp) |
| `scene_wait` | Seconds to wait after each warp (default 5) for textures |
| `warmup` | Passes over all scenes **without shots** before measuring |
| `toast` | `false`: skip on-screen notifications (they are not captured anyway) |
| `restore_first` | Addresses restored first at the end (call sites before caves) |
| write `fmt` | `B`, `H`, `I`, `f`, or `x` (hex bytes in **one atomic write**, for code patches) |
| write `addr` | Absolute, `vt:<vtable>+<off>` (exactly one live instance), or `vtall:<vtable>+<off>` (one write per instance) |
| write `val` | Number, or `"orig"` (the value read before the run) |
| write `check` | `[addr, qword]` that must match before anything is written (object moved? game restarted?) |
| write `noverify` | Skip the read-back (values the game consumes within a frame) |

After each hold the loop reports `persisted after hold: YES/NO`: whether the game overwrote the value
(`NO` means the write had no lasting effect or went to a stale address, which also happens after a death).
At the end it releases the camera lock, removes the pose-lock hook and restores every address. The
restore order reverses the write order, except for `restore_first` addresses. (The first version
restored a cave before its call site and crashed the game; [02](02-code-caves-and-hooks.md#9-other-crash-stories-platform-level).)

## 7. Texture streaming and other gotchas

### Streaming state changes sharpness

| Finding | Evidence |
|---------|----------|
| A **warp never unloads textures**; an elevator or area transition does | Sharpness between rounds varied -8..+15 %; spots visited a moment ago were sharper because not every texture is freed between warps |
| Settling takes about 3-4 s | `scene.py settle`: shots at t = 1..30 s after the warp; for t >= 4 s sharpness fluctuates +-4-8 % with no direction; the 4 s shot is already as close to the 30 s shot as any other. Default wait therefore **5 s** |
| A **warm-up pass** fixes it | One pass over all four scenes without shots, then two measured rounds: sharpness differences -2.8 / +5.2 / +4.3 / +0.2 % against -8 / +14.6 / +0.6 / -0.6 % without; shift `(0, 0)`, mean luma difference 1-4.6 = the noise of a static scene |
| Streaming of one area does not start on a warp alone | After a restart the bonfire scene's textures stayed low-resolution (sharpness 0.065 vs 0.206 earlier, noise 2.35) even with the warm-up; the area has to be walked into or checked separately |

**Rule:** compare only shots from the same visit/run; do a warm-up pass first; never compare
screenshots from different game sessions.

### Death and enemies

- Enemy movement and AI are on. In one run an enemy killed the player during the measurement. After a
  death **texture streaming is broken** (the same effect explains the bonfire scene problem) and the
  scene objects' heap addresses change (`persisted after hold: NO`; the writes went to the old
  addresses). The texture problem probably only disappears after a load (rest) or a restart.
  **A death during a run invalidates the run.**
- Choose safe scene locations. Enemies were frozen with an AI-disable cheat for the bonfire LOD and DOF
  tests (not shipped). **Toggling AI cheats at runtime can crash the game** in its own `CSChrThread4`
  thread; this is unrelated to the camera mods ([07](07-onionhen-integration.md#11-runtime-toggling-and-its-limits)).

### Stabilising the environment: the FFX/SFX layer

- A fixed time step was tried first and **failed**: a timestep object (found at a heap address in one
  run; field `+0x18` = `0x3C888889`, 1/60 s) turned out to be an init setting, not the per-frame
  delta. Writing 1e-6 for 30 s froze nothing. About 16,000 copies of the 1/60 constant exist in memory
  (code constants and entity structures); the static copies at `0x59406E4` and `0x5940A54` are constants
  and do not change. The "Inner Simulation Time" / "Time Rate" debug menus belong to the sea-wave effect,
  not to fog or foliage.
- **What worked:** the effect system's debug switch **`SFX-OFF`**. The FFX scene controller (vtable
  `0x57B9080`) has a byte `[obj+0x5C6]`; setting it to 1 removes ground-level fog, shimmering
  particles and flames. (The "Update-MultThreadEnable" byte is `+0x5C0`.) Readers of the flag are at
  `0x26FF427` (function `0x26FF340`), `0x2701A8D` (`0x2701A50`, a vtable slot), `0x270207C`, `0x270292C`;
  initialisation at `0x26FD9EB`. A static patch would be one byte, `0x26FD9F2` from 0 to 1 (a
  cheat fragment exists in the lab; it was never deployed, so untested).
- It leaves the **white distance-fog wall** (a separate layer: `FogA/FogB`, `FOG MANAGER` at
  `0x4D9FE34`, `FogInterpRatio` `0x4DCC3C0`, the `Fog Param` debug menu `0x4DD185E`, `DepthFogDensity`
  `0x4CACF08`) and **light sources** (a fire's glow stays, only the flames go). Brightness changes
  (mean 76.1 with the flag, 85.0 without), so compare states only against the same fog setting.
- Stability measured with the flag on (7 shots over 103 s, same view): brightness sd **0.22 %**
  (previously a drift of about 7 %), sharpness sd **0.2 %** (regions 0.2-0.6 %), drift 0.00 % per
  10 s (previously +-6..10 %), pixel difference between shots (foliage/animation) mean 3.1-3.7 without
  affecting the metric. With the flag **off** (normal state) sharpness read -23 % (static wall -33 %)
  and brightness +8 %: the fog and effects were eating the comparisons. **Foliage freezing was found
  unnecessary.**
- Use: `fixed` write `vt:0x57B9080+0x5C6 = 1` in the A/B spec; the address lives only as long as the
  game process, so it is re-found by vtable.

## 8. Comparison tools

Analysis scripts need numpy, Pillow and imagecodecs (JPEG XR decode).

### `tools/dev/analyze_ab.py <dir> [--png] [--collage] [--ref "<state>"] [--crop x0,y0,x1,y1]`

Works on a `collect_shots` output directory. For every scene and state: normalised sharpness (whole
frame and lower 40 %), the noise floor from repeated shots of the same state (ABAB), pairwise
differences between states (sharpness change, ground change, mean luma difference, phase-correlation
shift). `--ref` prints a compact table of every state against a reference state (mean of its shots;
a state that occurs twice also yields the noise floor). `--crop` writes a contact sheet of the same
box (1080p-equivalent pixels) for every state, 4x nearest-neighbour zoom, three per row, for visual AA
judgement. `--png` and `--collage` write decoded images.

### `tools/dev/make_strips.py <dir> <scene> "<state 1>" "<state 2>" ... [--bands] [--pick first|last] [--no-label] [--out base]`

One image in which the frame is cut into N vertical strips (or horizontal bands with `--bands`), each
strip taken from a different state. Because the camera is pose-locked the strips join seamlessly and
every strip spans the whole depth range, from near ground to the horizon. Output: full 4K and 1080p
PNG with labels and white separators.

### `tools/dev/make_slider.py --out <dir> --set "name=<collect dir>" ... [--scenes a b ..] [--html-only]`

Builds an interactive comparison page from one or more series x scenes x states: a slider (A|B),
vertical and horizontal strips (A-D), blink, and a difference mode (needs the page served over HTTP
for canvas pixel access; a `serve.sh` helper is generated), zoom and pan with visible pixels,
sharpness numbers and the B-versus-A difference, and a URL hash that stores the view
(`#set=1&scene=0&mode=vstrips&a=0&b=1&c=2&d=3`). Images are lossless WebP at 1080p-equivalent
(2x2 box reduce, the same as the analysis); `--html-only` regenerates the page from existing data.

### Visual judgement

The blink comparison (A, B alternating at the same pixel position) was the decisive tool for AA. The
maintainer's preference in blink tests chose DLAA threshold 0.3 and disliked FXAA/FXAA3; crops from
`analyze_ab.py --crop` and strips from `make_strips.py` carried the written record.

## 9. A recipe

1. Reboot or restart the game; load into the area; press the screenshot button once (arming).
2. Record or load the scenes (`scene.py record`, `scenes.json`).
3. Write a spec: fog layer off as a `fixed` write; states A/B in ABAB order; `scenes`, `warmup: 1`,
   `scene_wait: 5`, `shot_delay: 2`, `toast: false`.
4. Include a **positive control** state with a known large effect and a **repeated** state for the noise
   floor.
5. Run `ab_loop.py`; check the log for `persisted after hold: YES` on every state.
6. `collect_shots.py` the images; `analyze_ab.py --ref` for numbers; strips/slider for the eyes.
7. Throw the run away if anyone died, if a restart happened, or if `shift` is not `(0, 0)`.
