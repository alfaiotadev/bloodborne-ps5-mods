# 06 - Player, world and camera structures

Reference of every structure found during the research, for Bloodborne GOTY `CUSA03173` v01.09.
Addresses are absolute virtual addresses; heap objects move on every run (how to re-find them is in
section 14). Names come from the game's own debug-menu strings where possible; names in `code
font` that are not strings from the game are descriptive labels.

Confidence: **confirmed** = read or written on the console and behaved as described;
**inferred** = from static analysis or naming, or not exercised. Platform: firmware 12.40, PS5 Pro
([01](01-platform-and-tooling.md)).

## 1. Static globals

Fixed addresses in the image; they survive restarts.

| Address | What | Confidence |
|---------|------|------------|
| `0x593E878` | **WorldChrMan** pointer. Player ChrIns = `[[0x593E878]+0x60]` (handle 10000). Pad stick deltas at `WorldChrMan+0x70 / +0x80` feed `cam+0x110 / +0x120` | confirmed |
| `0x593E860` | Camera world/root singleton. **Camera manager** = `[[0x593E860]+0x2830]` | confirmed |
| `0x593E88E` | `Player Hide` debug byte; **no effect on rendering** | confirmed (negative) |
| `0x593B148` | Context pointer passed to the PlayerWarp tool (`0x194B110`) | confirmed |
| `0x593B120` | `[[0x593B120]+0xA7C]` is the current map id compared by the warp tool | inferred |
| `0x593B168` | Draw-entity lookup table (`SetDrawEnable` -> `0x17CA580` -> `0x19A6CA0`; id to entity by binary search) | inferred |
| `0x593D710` | Key/value store used by the warp tool (get `0x24EC0F0`, set `0x24EC3B0`) | inferred |
| `0x59402D8` | `LodBankMan` (FD4 singleton), leads to the `LOD_BANK` parameter blob | confirmed |
| `0x5940340` | `SoloParamRepository`; table at `+0x9C0` = `LOCK_CAM_PARAM_ST` | confirmed |
| `0x59406C8` | **SprjGraphics** pointer: sampler table (`+0x250 -> +0x360`), render-target chain (`+0x90`), W/H copies `+0xF0/+0xF4` | confirmed |
| `0x59406E0` | **Scene / post-effect parameter block** (a static struct, rewritten from the scene every frame): DOF, YEBIS AA enable, custom DOF | confirmed |
| `0x5865ED0` | **YEBIS context** pointer (a note wrote `0x58C5ED0`: typo) | confirmed |
| `0x55289F8`, `0x55289FC` | Render resolution W, H (u32). Hard-coded output buffers are separate (1920x1080) | confirmed |
| `0x59404D0` / `D4`, `D8` / `DC` | UI scale `W/1920.0`, `H/1080.0`; int copies of W, H | inferred (static) |
| `0x5527A94` | Camera collision bit; set every frame from a parameter (not a switch) | confirmed |
| `0x4D25E58` | `float` pi/180 used by the camera FOV conversion | confirmed |
| `0x5AA6C25`, `0x553AC88` | `Aniso Debug` / `MaxAnisotropy` debug-menu globals | inferred |

## 2. Player ChrIns (`pl = [[0x593E878]+0x60]`)

| Offset | Pointee / meaning | Vtable | Confidence |
|--------|-------------------|--------|------------|
| `+0x48` | **Model container** (`mod`) | `0x579CF10` | confirmed |
| `+0x58` | **Module container**: model-to-world rows, `[[pl+0x58]+8] == pl` | `0x5770610` | confirmed |
| `+0x3B0` | Slot object; `[+0x68]` = **physics body** `X` | `0x5735D70` | confirmed |
| `+0x3F8` | Map id (u32), e.g. `0x18010000` = area `m24_01` | - | confirmed |
| `+0xC0` | Position copy (same as `X+0x1E0`) | - | confirmed |
| `+0x60` -> `+0x1B0`, `+0x400` -> `+0x30` | Further position copies; **write `X`, not these** | - | confirmed |
| `+0x4D0` -> `[+0xE8]` `+0xDD0` | Hit boxes: AABBs, stride `0xA0`; the head box centre matches the head bone | - | confirmed |
| `+0xA68` -> `[+0x50]` | **Old** model-space pose: `hkQsTransform` array, 108 bones, head = bone 78; empty/self-pointer on a fresh save | - | confirmed (unreliable) |
| `+0x400` -> `[+0x910]` | Static base pose (inferred) | - | inferred |
| `+0xF8` = 1, `+0x110` = 2 | Values seen while locked on; meaning unknown | - | confirmed (values only) |

`SetPosition` `0x1CC16A0(chr, &pos)`: sets `X+0x1E0 = X+0x1F0 = pos`, word `X+0x210 = 0x0101`,
byte `X+0x32A = 1` (the physics step consumes and clears the flags). Angle wrapping to `[-pi, pi]`:
`0x1CC1770`, result into `X+0x1D0`. Applying a written yaw to the character: `0x1CBCF30(pl, 1)`.

## 3. Module container (`[pl+0x58]`, vtable `0x5770610`)

| Offset | Meaning | Confidence |
|--------|---------|------------|
| `+0x320`, `+0x330`, `+0x340` | Model-to-world rows R0, R1, R2 (row-vector convention; model forward is `-R2`) | confirmed |
| `+0x350` | Model-to-world translation row (the origin). **Zero/NaN after a respawn** | confirmed |

Rotating R0/R2 about the root changes only the *displayed* body (FACE2, [05](05-fps-head-camera.md#8-face2---the-body-faces-the-camera-display-only)).

## 4. Physics body `X = [[pl+0x3B0]+0x68]` (vtable `0x57356F0`)

| Offset | Meaning | Confidence |
|--------|---------|------------|
| `+0x1C0` | Previous position copy | confirmed |
| `+0x1D0` | Angles `(pitchRad, yawRad, 0, 0)`; yaw at `+0x1D4` (writes stay in memory but do not turn the character) | confirmed |
| **`+0x1E0`** | **Position `(x, y, z, 1)`**, Y up, the character's feet | confirmed |
| `+0x1F0` | Position copy (current/next) | confirmed |
| `+0x210` | Word `0x0101` = "position changed" flags (consumed by physics) | confirmed |
| `+0x32A` | Byte flag set with the above | confirmed |

A raw 1 m nudge holds; a 27 m raw write is reverted by the game: use the game's warp
([04](04-scene-automation-and-measurement.md#3-player-position-and-warp)).

## 5. Model container and the bone arrays (`mod = [pl+0x48]`)

| Item | Detail | Confidence |
|------|--------|------------|
| `[mod+0x18]` | Pose object, vtable `0x57A0820`; holds the animated world-space bone-array pointers in a sub-structure at slot offsets that vary per session (`+0x430/+0x570/+0x578`, `+0x320/+0x328/+0x400/+0x490`, `+0x450`) | confirmed |
| `[mod+0x20]` | Holder, vtable `0x57A0F10`, slot `+0x110` | confirmed |
| `[mod+0x5F0]` | Holder, vtable `0x57A1680` | confirmed |
| `[mod+0x5F8]` | Holder after a respawn, vtable `0x57A1500`; slots `+0xC0/+0xC8/+0x1A0/+0x230` | confirmed |
| Sub-structure | Four array pointers at relative `+0`, `+8`, `+0xE0`, `+0x170` | confirmed |
| Array | **170 bones** x 3x4 float matrix (row-major, **stride `0x30`**, translation = floats 3, 7, 11), 16-byte aligned, world space. **Head = bone 68** (neck 67) | confirmed |
| Copies | 3-4 per frame (pipeline stages, about 1 frame apart). Re-evaluated at **30 Hz** in Yharnam, while the origin and camera run at 60 Hz | confirmed |
| `[[mod+0x18]+0x170]` | 128-bit mesh display mask; **no effect** on rendering (the player's `SetDispMask` slot is an empty `ret`) | confirmed (negative) |

Old model-space array (stride `0x30`: translation vec4, quaternion `(x,y,z,w)` at `+0x10`, scale; 108
bones; head 78, neck 77) is described in [05](05-fps-head-camera.md#3-head-bone-source). Head-local
axes in the world: forward `+z`, up `+x`, right `-y`.

## 6. Camera manager and the cameras

`mgr = [[0x593E860]+0x2830]`: object size `0x1150` bytes, constructor `0x1835FC0` (caller `0x1D379D9`),
update function `0x18368B0` (calls the follow-camera update, then copies its pose).

| Offset | Meaning | Confidence |
|--------|---------|------------|
| `+0x10 / +0x20 / +0x30 / +0x40` | **Final pose rows**: right, up, forward, position (w = 1); R x U = F. The renderer's camera | confirmed |
| `+0x60` | **Follow camera** (`ChrFollowCam` / `ChrExFollowCam`; debug registration `0x183FB60`) | confirmed |
| `+0x68` | `ChrAimCam` (aim camera; registration `0x18349B0`: FovY, ZoomInFovY/ZoomOutFovY, ZoomRate, ZoomIn/OutOrg, ChrTargetDist, RotRage) | inferred |
| `+0x78` | `BallistaAimCam` (registration `0x18316A0`) | inferred |
| `+0x110 + n*0x80` (n = 0..5) | **Lock-on entries**; all zero when not locked | confirmed |
| `+0x110` | pointer to the locked target's ChrIns | confirmed |
| `+0x120` | lock point in the world `(x, y, z, 1)` | confirmed |
| `+0x130..+0x15C` | target model matrix (3x4) | confirmed |
| `+0x180` | lock point in the target's local space (y about 1.48 m) | confirmed |

The pose is stored into `mgr+0x40` by `vmovaps [rbx+0x40], xmm3` at **`0x1836C54`** (right/up/forward
still in `xmm0`-`xmm2`): the place the head-camera hook uses.

### Follow camera (`cam = [mgr+0x60]`, an object of about 4 KB; update `0x183AC60`, only epilogue `0x183F77B`)

| Offset | Meaning | Confidence |
|--------|---------|------------|
| `+0x10 / +0x20 / +0x30 / +0x40` | Pose rows (right/up/forward, position). **Not writable from outside** (overwritten within 12 ms); orientation is a look-at from the position to the pivot | confirmed |
| `+0x50` | `FovY` radians (0.7505 = 43.0 degrees); eased towards the parameter row | confirmed |
| `+0x54` | Aspect (1.778) | confirmed |
| `+0x58`, `+0x5C` | Near 0.05, far 3000 | confirmed |
| `+0x110`, `+0x120` | Stick deltas (from `WorldChrMan+0x70/+0x80`) | confirmed |
| `+0x140` / `+0x144` | Pitch / yaw (radians), **derived copies** | confirmed |
| `+0x154` | Lock factor, 1.0 when locked, ramps over about 1 s | confirmed |
| `+0xA0..+0xD0` | Pivot point; with lock-on the player's head lies on the view ray 3.7 m ahead | confirmed |
| `+0x17C..` | Persistent inputs | confirmed |
| `+0x180` | `FulcrumDist`? (about 3.33), computed every frame | inferred |
| `+0x184` | `CamDistTarget`, computed every frame | inferred |
| `+0x188` | `CamDist`, eased towards the row value | inferred |
| `+0x18C` | `CamCastSphereRadius` 0.05 | inferred |
| `+0x190`, `+0x194` | `CamSafeMarginRate/Max` 0.1 / 0.3 | inferred |
| `+0x198..+0x1B4`, `+0x1C0..+0x1C8` | Chase rates (`ChrTransChaseRate`...; the camera lags the character by 0.1 per frame) | inferred |
| `+0x2E0` | Derived copy | confirmed |

The `ChrCam` debug group (string `0x4D52ACA`) lists, in order: `ChrOrgOffset(x,y,z)`,
`FulcrumDistRateByLrMoveMaxDist`, `FulcrumDistRateMinByLrMove/MaxByLrMove`, `FulcrumDistRate`,
`FulcrumDist`, `CamDist`, `CamDistTarget`, `CamCastSphereRadius`, `CamSafeMarginRate/Max`; the offsets
above are deduced from that order. Update details (`0x183AC60`): `CamDist += ([row+0] - CamDist) *
blend`; `FovY += ([row+0x14]*k - FovY) * blend`. Other strings: `ZoomInFovY` `0x4D52408`, `ZoomOutFovY`
`0x4D5242C`, `ZoomIn/OutOrg.x..w` `0x4D524C6..0x4D525D6`, `CamDist` `0x4D52CC6`, `CamDistTarget`
`0x4D52CE6`, `PrevCamZoom` `0x4D76C28`, `PrevCamZoomVel` `0x4D76D30`, `LockCamParam` `0x4DB2E94`,
`CamPos`/`CamFov` `0x4CC807A`/`0x4CC80A8`, `camera_pos` `0x4DBC81C`.

Camera functions: collision cast `0x1C090E0` (six callers, all in the follow-camera update, filter
`0x25`); camera-pose write paths in the follow-camera update `0x183B399`, `0x183EBB2` (look-at),
`0x183EC5E`, `0x183EFC0`; CamDist load `0x183AE68`; pivot-height load `0x183AEEF`; FOV clamp
`0x183AF2B..0x183AF4E`; FOV degrees-to-radians multiply `0x183AF56`.

## 7. Parameter tables

### `LOCK_CAM_PARAM_ST` (camera rows) - `SoloParamRepository(0x5940340) + 0x9C0`

72 rows x 32 bytes (the blob moves; re-find through the repository). Rows are persistent data:
editing sticks.

| Field | Offset | Meaning |
|-------|--------|---------|
| `f0` | `+0x00` | Camera distance (4.0; bosses 3.7-6.2) |
| `f1` | `+0x04` | Pitch (-40) |
| `f2` | `+0x08` | 0.45 |
| `f3` | `+0x0C` | 1.42; pivot height (inferred) |
| `f4` | `+0x10` | 22 |
| **`f5`** | `+0x14` | **FOV in degrees** (43; a few 48); clamped 38..48 by code |
| `f6`, `f7` | `+0x18`, `+0x1C` | ints (9 / 5 or -1) |

### `LOD_BANK` - `[[[LodBankMan+0x68]+0x70]+0x70]` (`LodBankMan` = `0x59402D8`)

PARAM blob, 64 rows (id 0..63); row table at blob`+0x40`, 24 bytes per entry `{u32 id, u32 pad, u64
dataOffset, u64 nameOffset}`; row data 20 bytes `{f32 A, f32 B, f32 C, f32 D, u32 E}`; referenced
by `common_parts_lod_param_id`. A and C are distances in metres (A = LOD0 to LOD1, C = LOD1 to LOD2;
inferred). Writing the rows takes effect live ([03](03-anti-aliasing-and-image-quality.md#lod)).

Other tables are listed by `tools/dev/list_params.py`; none other was needed. The `scene_draw_param`
rows (AA, fog, DOF per scene) were inspected only through the scene block.

## 8. Scene / post-effect parameter block (`0x59406E0`, static)

Rewritten from the scene every frame: **do not write, patch the consumer.**

| Offset | Field | Observed |
|--------|-------|----------|
| `+0x1AC` | DOF enable | 1 |
| `+0x1B0` | FocusDistance | 1 |
| `+0x1B4` | ApertureF | 5.6 |
| `+0x1C0` | CCD | 43.27 |
| `+0x220` | YEBIS FXAA2 enable (consumer `0x25D802C`) | 0 |
| `+0x224` | AA type | - |
| `+0x228..+0x234` | FXAA parameters | - |
| `+0x2D0` | CustomDof | 1 |
| `+0x2D4`, `+0x2D8` | Near/far custom DOF | 1 |
| `+0x2EC`, `+0x2F0` | Far blur start / full (m) | 10 / 50 (Hunter's Dream); 100 / 150 (Yharnam) |
| `+0x2F4`, `+0x2F8` | CocSize, CocScale | 0.3 / 0.016 (Hunter's Dream); 0.05 / 0.098 (Yharnam) |

`+0x220` and the DOF/custom-DOF fields were read live and match the consumers' compare instructions;
`+0x224..+0x234` are inferred from the debug-registration layout. The function that pushes scene
parameters to YEBIS spans about `0x25D7A00..0x25D8140` (`r15`/`rbx` = this block).

## 9. Game-side AA pass (vtable `0x56E7980`)

Four instances; one active. Located in the scene object at `scene+0x1BC8`.

| Offset | Field |
|--------|-------|
| `+0x08` | IgnoreParamFromOutside (bool) |
| `+0x09` | Enable (bool) |
| `+0x0C` | mode: 0 FXAA, 1 FXAA3, 2 FXAA3 HQ, 3 DLAA |
| `+0x10..+0x1C` | FXAA alpha, reduceMin, reduceMul, spanMax |
| `+0x28` | DLAA threshold (0.1) |
| `+0x2C` | DLAA lambda / "Ramda" (2.44 live) |
| `+0x30` | DLAA epsilon (0.25) |

Functions: constructor `0x1258940`, execute `0x1258D30`, parameter copy `0x12596F0`, debug
registration `0x1259730`, pass setup `0x1258C50`, shader name table `0x56E79A0`, scene-parameter
interpolation `0x126C5D0`. Hook point for the threshold: `0x125970F`. Confirmed live (see
[03](03-anti-aliasing-and-image-quality.md#3-discovery-the-games-own-aa-pass-is-already-dlaa)).

## 10. YEBIS context (`[0x5865ED0]`)

| Offset | Meaning | Confidence |
|--------|---------|------------|
| `+0x130..` | Init flags: `+0x145` ANTIALIAS_TEMPORAL, `+0x147` GAUSSIANBLUR, `+0x14F` ANTIALIAS, `+0x150` ANTIALIAS_DISTANCEFALLOFF | confirmed |
| `+0x57C`, `+0x580` | Camera near/far planes (0.05, 3000) | confirmed |
| `+0x6D5` | Dirty flag for the falloff setter | confirmed |
| `+0x6F6` | Condition input for the TAA-active flag | inferred |
| `+0xB8C` | Temporal AA enable | confirmed |
| `+0xB90` | TAA state (2) | confirmed |
| `+0xB98`, `+0xB9C`, `+0xBA0`, `+0xBA4`, `+0xBA8` | TAA parameters: weight 0.05, 0, 0.1, 0.1, 0.001 | confirmed |
| `+0xBBC` | AA (FXAA2) enable | confirmed |
| `+0xBC0`, `+0xBC4` | AA falloff near / far (m) | confirmed |
| `+0xC99` | TAA-active flag (recomputed per frame) | confirmed |

Functions: `SetAntialiasEnable` wrapper `0xFB37F0` -> `0xFD31F0`, getter `0xFB3810`, falloff setter
`0xFD3270`, `SetTemporalAntialiasEnable` `0xFD2CB0`, parameters `0xFD2D20`,
`ApplyEffects_TemporalAntialias` `0xFE7580`, `SetDepthOfFieldEnable` `0xFB2960`, custom DOF setter
`0xFB3600`.

## 11. Sampler table

`[[0x59406C8]+0x250]+0x360`: 19 descriptors x `0x38` bytes: `+0` mipLODBias (f32), `+4`
MaxAnisotropy (i32). Aniso samplers: indices 8-15 and 17 (GI map), value 4; 16 (DisplacementMap) and
ShadowMap 0. Rewriting after init **does not change the rendering** ([03](03-anti-aliasing-and-image-quality.md#anisotropic-filtering));
the sampler debug menu is registered at `0x25B29F0`. Confirmed (the table exists and is writable; the
lack of effect is also confirmed).

## 12. Graphics and resolution objects

| Item | Address / path | Confidence |
|------|----------------|------------|
| Main buffer render target | `[0x59406C8] -> +0x90 -> entry 0 -> +0x68`; texture at `+0x40` | confirmed |
| Swapchain | `0x2AD5E90`; surface computation `computeSurfaceInfo` (tile mode 14) accepts only 720p / 900p / 1080p | confirmed |
| Output buffers | `0x15E48E9` (pixel format `0x80000000`, 1920x1080, two buffers), swapchain `0x15E4620` | confirmed (static) |
| Texture creation | `Texture::Create` `0x259F130` -> `CreateTexture2D` `0x2565F90` -> `0x2571D60` | confirmed |
| View render-target size table | loads at `0x2594EB7` / `0x2594EC2`; swapchain size loads `0x2594AA6` / `0x2594ABD` | confirmed |
| Scaleform HUD viewport | `0x2358554` (`SetViewport`, vtable `+0x68`); pixels are 1080p units | confirmed |
| Property init | `0x2417770` (`SPRJ.WIN64.frameBufferW/H`); setters `0x2417700`, `0x219E850`, `0x241A2F0` | confirmed (static) |

Details in [03](03-anti-aliasing-and-image-quality.md#8-resolution-and-supersampling-failed).

## 13. FFX effect system (`SFX-OFF`)

Scene effect controller (`FFXSceneCtrl`), vtable `0x57B9080`: byte `+0x5C6` = `SFX-OFF` (1 removes
ground fog, particles, flames; keeps light glow and the distance-fog wall); `+0x5C0`
`Update-MultThreadEnable`. Debug registration `0x27035F6` (function `0x2703570`, in the class vtable).
Readers `0x26FF427`, `0x2701A8D`, `0x270207C`, `0x270292C`; initialisation `0x26FD9EB`. Confirmed live
([04](04-scene-automation-and-measurement.md#stabilising-the-environment-the-ffxsfx-layer)).

## 14. Finding things after a restart

| Object | Method |
|--------|--------|
| Player, physics body, camera manager, follow camera | Pointer chains from `0x593E878` / `0x593E860` (section 1) |
| AA pass instances, FFX controller | Vtable scan over writable mappings (skip the largest mapping, the GPU arena); `vtall:` for all instances |
| Bone arrays | Cave-side holder and slot search ([05](05-fps-head-camera.md#4-bone-arrays-and-the-holder-search)) |
| Parameter blobs (`LOCK_CAM_PARAM_ST`, `LOD_BANK`) | Through the repository / `LodBankMan` chains |
| Any vtable-identified object | Scan, then check the vtable pointer before every write |

## 15. Vtable index

| Vtable | Class (descriptive) |
|--------|---------------------|
| `0x56E7980` | Game-side AA render pass |
| `0x5735D70` | Player slot object (`[pl+0x3B0]`) |
| `0x57356F0` | Physics body `X` |
| `0x5770610` | Module container (`[pl+0x58]`) |
| `0x579CF10` | Model container (`[pl+0x48]`) |
| `0x57A0820` | Pose object (`[[pl+0x48]+0x18]`) |
| `0x57A0F10` | Holder `[mod+0x20]` |
| `0x57A1500` | Holder `[mod+0x5F8]` (after respawn) |
| `0x57A1680` | Holder `[mod+0x5F0]` |
| `0x57B9080` | FFX scene controller |
