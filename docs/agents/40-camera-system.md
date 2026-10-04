# 40 - Camera system: what is known, how to extend it

> Tested only on firmware 12.40 with a PS5 Pro, Bloodborne `CUSA03173` v01.09. Camera behaviour in cutscenes, boss arenas and special areas was not exhaustively tested; nothing here was measured on a base PS5. Narrative history: [../research/05-fps-head-camera.md](../research/05-fps-head-camera.md) and [../research/06-player-world-and-camera-structures.md](../research/06-player-world-and-camera-structures.md). Addresses: [10-memory-map.md](10-memory-map.md) and [registry.json](registry.json). Where lab notes and the generator `tools/mods/make_head_camera_mod.py` disagree, the generator wins.

## 1. The pipeline (one frame)

```
 pad -> WorldChrMan+0x70/+0x80 (stick deltas)
   camera manager update  0x18368B0   (mgr = [[0x593E860]+0x2830], 0x1150 bytes)
      call follow-camera update 0x183AC60   (cam = [mgr+0x60])
          integrates pad rotation deltas (cam+0x110/+0x120)
          chases the player: CamDist -> param row f0, pivot height -> row f3, FovY -> row f5*pi/180
          orientation = LOOK-AT from camera position to pivot (5 code paths write the rows)
          6 collision casts -> 0x1C090E0 pull the camera in against walls
          epilogue 0x183F77B   (add rsp,0x3D8; r13 = cam)
      copy follow-camera pose rows into the manager's own pose  ...  0x1836C54  vmovaps [rbx+0x40],xmm3
   renderer uses the MANAGER's pose rows (+0x10 right, +0x20 up, +0x30 forward, +0x40 position)
```

Facts that shape every camera mod (all `confirmed-live` unless noted):

* **The follow camera's pose rows cannot be written from outside**: overwritten within 12 ms. The orientation is recomputed as a look-at every frame in several code paths (`0x183B399`, `0x183B649`, `0x183EBB2`, `0x183EC5E`, `0x183EFC0`); `cam+0x140/+0x144` (pitch/yaw) and `cam+0x2E0` are derived copies, no angle state was found (differencing, quaternion search and persistence probes all failed).
* **Do not override the follow camera's own position row**: the pad code derives its angles from the manager pose; with the camera 0.1 m from the pivot the look-at becomes unstable and the view spins ("tornado": 13 pitch flips per second, about 9400 deg/s). Override only the **manager's output copy** at `0x1836C54`.
* Fields `cam+0x180/+0x184` are recomputed every frame; `cam+0x188` (CamDist) and `cam+0x50` (FovY) approach the parameter row with a blend: **direct writes do not persist**. `cam+0x17C..` are persistent inputs. (Probe: `tools/dev/camera/cam_persist.py`.)
* **Parameter rows persist** (`LOCK_CAM_PARAM_ST`, 72 rows x 32 B on the heap): doubling every row's distance `f0` worked and showed the whole staircase at once. FOV `f5` is clamped by code to 38..48 degrees.
* The collision pull-in flickered the camera distance between 1.2 and 3.7 m every frame; the camera collision bit `0x5527A94` is rewritten every frame from a parameter (not a switch), so the fix is the cast function `0x1C090E0`.
* The manager rows form a right-handed orthonormal frame (R x U = F, lengths 1); position row w = 1; rows are 16-byte aligned (`vmovaps`).

## 2. Wide FOV (shipped, stable)

`vmulss xmm1,xmm1,[rip+disp]` at `0x183AF56` multiplies the (clamped) row FOV by pi/180 (`0x4D25E58`). The mod points the `disp32` (`0x183AF5A`) at a cave constant `0x54A0500` = pi/180 x SCALE, so the **multiplier applies after the clamp** and every row scales. Constant first, displacement second; restoring writes the original displacement `FA AE 4E 03`.

| Scale | Vertical | Horizontal (16:9) | Note |
|---|---|---|---|
| 1.0 | 43.0 deg | about 70 deg | game default (measured 43.0 by image registration) |
| 1.2 | 51.6 | about 82 | |
| **1.3** | **55.9** (measured 55.7-56.1) | **about 87** | default of the release file |
| 1.5 | 64.5 | about 97 | the `fps` profile (tuned with the head camera) |
| 1.6 | 68.8 (measured) | about 100 | rejected by the maintainer as "psychedelic" |

Tune live: `python3 tools/dev/mods-live/fov_live.py 1.3` (writes the float at `0x54A0500`; the camera lerps to it in about 1 s). Build variants: `python3 tools/mods/build_cheats.py --fov-scale X`.

Not done: per-context FOV (aim camera, telescope), FOV compensating for the head camera's wider look, scaling the horizontal and vertical FOV independently.

## 3. The FPS head camera (shipped, experimental)

Three mods, one generator: **FPS head camera (experimental)** (core, `MODE`), **body faces the view** (`FACE2`), **aim at the lock-on target** (`AIM`). Verified from a cold start by the maintainer: load, FPS view, walking, running, rolls, ladder, death + respawn, teleports between Hunter's Dream and Yharnam, lock-on (with the limitations below). Not exhaustively tested: cutscenes, every boss arena, long sessions; the final FACE2 code was never cold-start tested.

### 3.1 Hooks and caves

| Hook | Cave | Purpose |
|---|---|---|
| `0x1836C54` (5 B) | manager cave `0x54A1600` | **core**: touchpad toggle, head position, smoothing, height floor, distance guard, AIM |
| `0x1C090E0` (6 B) | cast cave `0x54A1100` | camera collision off (`xor eax,eax; ret` when `NOCOLL`) |
| `0x183F77B` (7 B) | epilogue cave `0x54A0780` | FACE2 (inactive unless `FACE2 = 1` and `MODE = 1`) |

All state is in the data block `D = 0x54A0E00` ([10](10-memory-map.md) section 9) and is live-tunable.

### 3.2 What the manager cave does, in order

1. **Pad toggle** (runs even while the mode is off): if `PADTOG` is set and the libScePad function slot `[0x57E5B30]` looks valid (high dword 8, page offset `0xA30`, and the distance to the second import slot `[0x57E4E90]` is `0x990`, i.e. the same libScePad build; the library's *code* is execute-only and is never read - a version of this check that compared function bytes crashed the game), OR the 12 pad reports of the ring at `libScePad base + 0x28BDC` (stride 0xE0, buttons dword first; the ring lives in libScePad's readable data segment) so a press within about 50 ms is seen; touchpad = `0x100000`. A rising edge starts/ends a pair: a second click within 30 frames (about 0.5 s) does `xor byte [MODE],1`. The game's personal-effects menu opens/closes with the clicks (harmless). **Status: confirmed on hardware from a cold start.** Right after it the cave copies the active FOV multiplier (`FPSFOV` if MODE else `TPFOV`) into the Wide-FOV constant `0x54A0500`, so the first-person view can use a wider FOV than third person.
2. If `MODE == 0`: run the displaced `vmovaps [rbx+0x40],xmm3` and return.
3. **Pointer walk (every pointer validated):** `G_WorldChrMan` -> `[+0x60]` player -> `[+0x48]` (vtable `0x579CF10`) = model container -> `[pl+0x3B0]` (vtable `0x5735D70`) -> `[+0x68]` (vtable `0x57356F0`) = physics body `X`; origin = `X+0x1E0` (feet). Any failure -> do nothing, the game's camera runs.
4. **Head source:** the remembered holder `HOLD` (`0x18`, `0x20` or `0x5F8` inside the model container) and slot `ARROFF`; fast path via subroutines `H` (holder) and `P` (array plausibility: 16-byte aligned, head 0.25..2.4 m above the origin, now `YMIN = -0.5`, horizontal < 1.5 m). On failure: scan 3 holders x slots `0..0x5F8`, remember the working pair, else set a 120-frame back-off (`COOL`) and use `origin + FALLV` (1.53 m, no bobbing).
5. **30 Hz latch + smoothing:** the pose arrays update at 30 Hz in some maps (Yharnam; all copies, 33 ms) while origin and camera run at 60 Hz. Latch `(head, origin)` whenever the array value changes; `T = head@latch - origin@latch`; smooth `S += ALPHA*(T-S)` (ALPHA 0.5; a jump larger than sqrt(SNAP2) snaps); camera = `origin(now) + S`.
6. **Height floor:** `camera.y = max(camera.y, origin.y + HMIN)` (1.25 m) so rolls and stumbles do not drop the view into the body (walking head height varies about 0.22 m, so 1.40 clipped the bobbing).
7. **Offsets:** `+ R*right + U*up + F*forward` along the game's rows (xmm0..xmm2): defaults 0 / 0.17 / 0.32 m (eye position; weapons visible in the hands).
8. **Distance guard:** if the new position is >= sqrt(LIMIT) = 10 m from the game's camera (garbage/zero pose, cutscene cameras) keep the game's position.
9. **Death camera** (when `DEADF`, i.e. HP `[[pl+0x3b0]+0x20]+0xf8` <= 0): the height floor `HMIN` is not applied; the rows are rebuilt from the head matrix remembered in `HA`: forward `F = column 2`, up `U = column 0` (right = -column 1; measured against the game's rows while the hunter stands: dot products 1.00), each eased with `S += DALPHA*(T-S)` starting from the game's last forward/up (`FS`/`US`, refreshed every alive frame), then `F' = Fs/|Fs|`, `R' = (Us x F')/|.|`, `U' = F' x R'`. The offsets of step 7 use these rows, and after them the final camera y is raised to `origin.y + DFLOOR` (0.30 m) so the camera does not sink into the ground. The rows are written to `[rbx+0x10/0x20/0x30]` after the distance guard and AIM is skipped. The FACE2 epilogue is suspended while dead. Alive again (respawn): `DEADF = 0` and everything is normal. The game's own camera does not change at all when the player dies - that is what made the fixed first-person view look wrong.
10. **Killer camera** (flag `KILLCAM`): on the first dead frame (`DEADF`, edge via `DEADP`) the cave chooses `KILLER`: `[mgr+0x110]` (the locked-on target) if set, else the nearest living character within `sqrt(KRANGE2)` from `[WorldChrMan+0x1490]` (0x38-byte records, first qword = ChrIns, count at `+0x1488`, up to 256; a record is accepted when `[[c+0x3b0]+0x20]+0xf8 > 0` and `[[[c+0x3b0]+0x68]+0x1e0]` is a position). From `KCNT >= LOCKAT` the death-camera target view is "from the head towards the killer's chest (`+KHEIGHT`)": forward = normalised difference (**w lane masked to 0** - a row with a non-zero w broke the view matrix and gave a flat grey screen), up = `WORLDUP`; it replaces the head axes in the same easing (`DALPHA2`, via `ALPHAUSE`) and orthonormalisation. If the killer pointer fails validation the head axes are used.
11. **Time effect** (flag `SLOWON`, evaluated right after the HP read): while `DEADF` the target time scale is `PH1SCALE` for the first `PH1END` manager frames (`DCNT`, real time), `PH2SCALE` until `PH2END` frames, then 1.0; `TSCALE += SLOWG*(target-TSCALE)`. Defaults: normal speed for 300 frames (the death animation and the YOU DIED screen, which the game shows when the animation ends, run on game time), then 0.05 until frame 720. The separate hook at `0x1E196BB` (`vmovss xmm0,[r13+0x374]`, followed by `vmulss xmm1,xmm1,[rbx+8]`; `r13 = [[chr+0x3b0]+0x30]`) multiplies every character's speed factor by `TSCALE`. With the head camera off, or when the player object chain fails (loading), the cave resets `TSCALE` to 1.0. Stock community cheats ("Player's Speed x2", "Start Speed") use the same field; their player check compares against an address that holds zero here, so they have no effect.
12. **AIM** (if `AIM` and not dead): see 3.4.
13. Restore registers, run the displaced instruction, jump back to `0x1836C59`.

While alive the head only supplies the **position** (while dead it also supplies the orientation, step 9, or the direction to the killer, step 10). The view direction is the game's own (right stick): the head's orientation follows the body, not the stick (the camera turned 355 degrees while head yaw stayed), so using it would defeat camera control.

### 3.3 FACE2 (display-only body facing)

In the follow-camera epilogue, rotate the model->world rows R0 (`[pl+0x58]+0x320`) and R2 (`+0x340`) about the character root so the displayed model faces the camera's horizontal direction: with `rx, rz` = camera right row, `cos = R2x*rz - R2z*rx`, `sin = R2z*rz + R2x*rx` (no trigonometry), `x' = x*cos + z*sin`, `z' = z*cos - x*sin`; refuse if `cos^2 + sin^2 < MINN` (0.5). Game state (facing, movement) is untouched, so strafing/backpedalling work. **Side effect: coat and hood cloth parts disappear** while it is on (confirmed by toggling live; returns when off; equipment changes do not help). The maintainer considered the hiding even useful in FPS (no hood flapping in front when moving backwards). Cold-start testing of the final guarded version is pending. Forcing the player's real facing every frame (writing `X+0x1D4` + calling `0x1CBCF30(pl,1)`) gave "tank controls" and was dropped.

### 3.4 AIM (lock-on aim), design

The game's lock-on camera looks at the player's **pivot** (the player's head is exactly on the view line 3.7 m away), not at the enemy. With the camera moved to the head, the locked target sits above the centre line. The camera manager holds the lock-on state: `mgr+0x110` target ChrIns pointer (zero when not locked), `mgr+0x120` lock point (world x,y,z,1).

* While locked and `0.3 m <= |D| < 60 m` (`AIMMIN2/AIMMAX2`) with `D = lockpoint - camera`: `F' = D/|D|`; if `F'.F >= AIMCOS` (0.3) the target offsets in **camera space** are `TR = (F'.R)/(F'.F)`, `TU = (F'.U)/(F'.F)`; ease `TR += BETA*(target - TR)` (BETA 0.3), same for TU.
* Not locked: the offset **stays** (the game's view does not drag the camera back); it only decays (`x DECAY` 0.97 per frame) while the user turns the camera (the game's forward row moves faster than `MOTCOS` = 0.99998 per frame), where the change is hidden by the motion.
* View: `Fb = normalize(F + TR*R + TU*U)`; rows are rebuilt from the world up vector (no roll): `h = sqrt(Fx^2 + Fz^2)`, `V = Fb/h`, right = `(Vz, 0, -Vx, 0)`, up = `(-Fy*Fx/h, h, -Fy*Fz/h, 0)`, forward = `Fb` (w = 0); written to `mgr+0x10/0x20/0x30` and reloaded into xmm0..xmm2. If `h^2 <= EPS` (looking straight up/down) keep the game's view.
* History of the final design (maintainer feedback): hard on/off conditions (angle < 40 deg) gave a delayed jump and flicker at close range; the game's own lock factor `cam+0x154` ramps over about 1 s ("pole -> second -> face"); snapping back to the game's direction on release felt like "lowers and jerks". Current version starts immediately and keeps the offset. The maintainer decided to settle with it ("someone else can make other profiles").

### 3.5 Known limitations

* FACE2 hides cloth; the silhouette of the body spins in front of the camera for a moment when backpedalling starts (the game plays a turning animation; seen with FACE2 on).
* Close-range strafing while locked on can twitch the aim.
* On a death + respawn the layout changes (handled by the holder search) but the very first frames after a respawn may use the fallback head (no bobbing).
* Cutscenes: handled indirectly by the 10 m guard and the plausibility tests; unusual scripted cameras not exhaustively tested.
* Camera collision is off while the mod is on: the camera can end up inside walls in tight spaces (the head is inside the player's collision anyway).
* Mid-run toggling from the onionHEN menu: switching the camera mod off relies on the `off = on` entries added by `build_cheats.py` (onionHEN refuses to switch a mod off with an empty `off`); checked on hardware that toggling the cheats in the menu and the touchpad double-click work. The cache fields (`ARROFF`, `COOL`, `HOLD`) are deliberately not part of any entry, so toggling never resets them.

## 4. Tuning and live testing

All of these are live (the cave reads them every frame). Write floats with `struct.pack("<f", v).hex()`.

```bash
# read the whole data block (0x140 bytes)
python3 tools/dev/mods-live/code_patch.py 54A0E00 ?320
# raise the eye 5 cm: OFF_U (0x54A0E0C) 0.17 -> 0.22
python3 tools/dev/mods-live/code_patch.py 54A0E0C $(python3 -c "import struct;print(struct.pack('<f',0.22).hex())")
# switch the mode / FACE2 / collision flags
python3 tools/dev/mods-live/flag.py MODE=1 FACE2=0 NOCOLL=1
# compare live hooks/data/pointer chain with the cheat JSON
python3 tools/dev/camera/hc_state.py cheats/CUSA03173_01.09.json
```

To change a default permanently, change the argument of `build()` in `make_head_camera_mod.py` (`u`, `f`, `r`, `hmin`, `alpha`, ...) and regenerate. Do not run `head_cam.py`/`cam_lock.py`/`scene.py` (lab pose-lock) at the same time.

Checklist for any camera change: cold start; load a save; walk, run, **roll** (head 0.1 m above the origin), ladder up and down, **fall**, **die and respawn**, teleport Hunter's Dream <-> Yharnam, lock on/off at several distances, toggle the mod off/on (`flag.py MODE=0`/`1`), a cutscene if possible; check fps stays 60; a 10-minute session.

## 5. Lab-only camera tools (not for use together with the release mod)

* **Pose lock** (`mods-live/make_cam_pose_cave.py`, `camera/cam_lock.py`): hook at the epilogue `0x183F77B`; when `FLAG != 0` the cave copies `ROW0..3` over `[r13+0x10..0x40]`; the manager copies the pose right after. Instant (no easing), releases to the game's camera immediately: ideal for automation, used by the scene tooling ([20](20-tooling.md) section 9).
* **Call service:** the same cave runs `FN(ARG0..ARG3)` on the **game thread** when `CALL != 0` (rsp aligned at the epilogue), result in `RET`; this is how the game's own warp `0x194B110` is invoked.
* **Orbit lock** (`cam_lock.py lock --yaw d --pitch d`): rotate the whole frame rigidly around the player so the character stays at the same screen position.
* The first head camera lived here (epilogue mode with restore hook at the follow-camera entry `0x183AC60`, squeeze hold, bone-78 chain): superseded.

## 6. Ideas not yet tried (each with a first step)

| Idea | Why | First step |
|---|---|---|
| Lock-on aim profiles (different easing, aim at a body part, soft aim assist) | maintainer: "someone else can make other profiles" | change `BETA`, `AIMCOS`, the lock point (`mgr+0x120`, `mgr+0x180` local y 1.48 m) live with `code_patch.py`, record with a scene + `ab_loop` |
| Third-person distance multiplier | simple, safe QoL | hook the CamDist load at `0x183AE68` (`vmovss xmm1,[rsi]`; lab hood-view cave shows the 5-byte hook and the re-emitted next instruction) and multiply; or edit `LOCK_CAM_PARAM_ST` `f0` rows once per boot (rows are persistent but heap-resident) |
| Idle-animation / roll damping in FPS | head sway when standing | find the animation time-scale (`hkb` playback speed, timeFactor) for the player; first read-only probe over the pose copies |
| Silhouette-spin damping when backpedalling | known limitation | log body yaw (`R2`) vs camera yaw around the event (`head_look_log.py` style) |
| Hide the player's head/hood properly | FACE2 hides cloth only as a side effect | `PlayerChrIns+0x4D0` hit boxes and the draw-entity flags (`entity+0x1FC` bit 14 = drawn, `G_DrawEntityManager`) are untested leads; `SetDispMask` vtable slot is an empty `ret` and `Player Hide` `0x593E88E` had no effect |
| FPS for the aim cameras (ChrAimCam `mgr+0x68`, BallistaAimCam `mgr+0x78`) and the telescope item | the telescope is first-person with a narrow zoom FOV | read `ZoomInFovY/ZoomOutFovY`, `ZoomIn/OutOrg` (strings listed in [10](10-memory-map.md) section 11) via the aim-camera debug registration `0x18349B0`, dump `mgr+0x68` live with `read_cam.py` |
| Camera shake / head tilt on damage, roll lean | immersion | needs hooks on player state; first find a hit/stagger flag by differencing (`lock_diff*.py` method) |
| Using the head bone orientation for look direction on a controller | none found useful | not recommended: head yaw follows the body |
| A second toggle path (long press, options-combination) | FPS reset | extend the pad block: the ring entries have all buttons; see [90](90-open-questions.md) |
| Cutscene detection to switch FPS off | known limitation | find a cutscene flag (WorldChrMan or camera manager) by differencing before/after a cutscene |

## 7. Pitfalls recap

Never write the follow camera's rows or position; never trust a layout without a vtable check; never assume the bone-array slot; the model matrix translation is zero after a respawn; keep `vmovaps` operands 16-byte aligned; NaN-safe compares; the manager's rows must stay orthonormal if you rewrite them (AIM rebuilds them from the world up vector); compare camera behaviour in a 30 Hz-pose map (Yharnam) and a 60 Hz one.
