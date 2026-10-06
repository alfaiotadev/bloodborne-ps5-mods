# 10 - Memory map: addresses, structures, offsets

> All addresses are for Bloodborne GOTY `CUSA03173` **v01.09** (`eboot.bin`), measured on a **PS5 Pro, firmware 12.40**. They are fixed virtual addresses; other versions or regions need a new map. This file mirrors [registry.json](registry.json) (machine-readable, same data plus the generator-derived caves, hooks and data-block fields).

## How to read the tables

Confidence column:

* **confirmed-live** - read or written on the running game through ps5debug and the behaviour observed, or a mod using it ran from a cold start.
* **inferred** - deduced from behaviour, naming (debug-menu order) or neighbouring data; not directly verified. Treat as a hypothesis and verify before building on it.
* **static-only** - seen only in disassembly or debug strings of an unpatched dump; never exercised live.

"Verified where" names the scene or procedure. Heap addresses change every launch; only static (image) addresses and *relative layouts* are stable. Pointer notation: `[a]` = 8-byte dereference.

## 1. Image and memory layout

| Address | What | Confidence | Verified where |
|---|---|---|---|
| `0x400000` | `eboot.bin` image base. Dump index = address - `0x400000`. Cheat offsets are absolute VAs (`"absolute": true`). | confirmed-live | exec-time cheats; `0x243487E` holds the 1/30 constant at the absolute address |
| `0x400000..0x5AD4000` | Dump range used for verification (91,045,888 bytes). Data bytes in it are runtime state, only code is comparable. | confirmed-live | ps5debug dump of an unpatched run |
| `0x54A0000..0x54A4000` | Spare region for caves and data blocks (must be zeros in an unpatched dump). | confirmed-live | all release caves run here |
| `0x5A40000` | Lab diagnostic ring buffer (header, then 256 x 32 B at `0x5A40010`). Not used by release mods. | confirmed-live | lab hook |

### Release allocation map (what lives where in the cave region)

| Range | Size | Owner | Notes |
|---|---|---|---|
| `0x54A0400..0x54A0485` | 134 | Anisotropic stub | `make_aniso_mod.py` |
| `0x54A0500` | 4 | Wide-FOV constant | float `pi/180*scale` |
| `0x54A0780..0x54A0966` | 486 | Head camera: epilogue cave (FACE2) | `make_head_camera_mod.py` |
| `0x54A0E00..0x54A0FFF` | 0x200 | Head camera data block `D` | fields in section 9 |
| `0x54A1100..0x54A111A` | 27 | Head camera: camera-cast cave | |
| `0x54A1300..0x54A130C` | 13 | DLAA threshold cave | |
| `0x54A1340` | 4 | DLAA threshold constant | float 0.3 |
| `0x54A1140..0x54A1156` | 22 | Head camera: death slow motion cave (hook `0x1E196BB`) | |
| `0x54A1600..0x54A2506` | 3847 | Head camera: camera-manager cave (touchpad toggle, head position, close-character guard, death camera, killer selection and look-at, slow-motion state, aim) | written as three cheat entries (1000 + 1000 + 531 bytes) because of the 1024-byte entry cap, see [70](70-onionhen-cheat-engine.md) hazard 1 |

### Lab (dev-only) allocations that COLLIDE with the release ones

The lab pose-lock/call-service install (`tools/dev/make_cam_pose_cave.py`, `scenelib.py`, `scene.py`, `head_cam.py`, and `ab_loop.py` when `scenes` is used) writes its own caves and data into the **same region and the same hooks**:

| Range | Lab use | Conflict |
|---|---|---|
| `0x54A0600..0x54A060F`, caves `0x54A0620`, `0x54A0680` | "hood view" FPS mod (FLAG, DIST, HEIGHT, FWD) | none with release |
| `0x54A0700..0x54A077F` | pose-lock/call-service data (FLAG 0, CALL 2, CNT 4, ROW0..3 `0x10..0x40`, FN `0x50`, ARG0..3 `0x58..0x70`, RET `0x78`) | none with release |
| `0x54A0780..0x54A0B40` (961 B) | lab epilogue cave | **same address as the release epilogue cave** |
| `0x54A0C00/0C10/0C20` | MAPID / POS / ROT scratch for the game warp (older notes said `0x54A0900/10/20`; the script wins) | none |
| `0x54A0E00..` | lab head-camera data (FLAG, VALID, STATE, GOODV, BONEOFF `+4`, R/U/F `+8/0C/10`, ENTER2/LEAVE2, SAVED `+0x20`, PIVOT `+0x30`, GOOD `+0x40`, NOCOLL `+0x70`, FLAG2 `+0x71`, FACE `+0x72`, FACE2 `+0x73`, consts `+0x80..`) | **same base, different layout** (release: BONEOFF `+4` but ARROFF `+0x14`, MODE `+0x71`, AIM `+0x72` ...) |
| `0x54A1000` (57 B) | lab follow-camera entry cave | none |
| `0x54A1100` (27 B) | lab camera-cast cave | same as release |
| `0x54A1200` (228 B) | lab manager cave | release manager cave is at `0x54A1600` |

Rule: run **either** the lab tools **or** the release head-camera mod, never both. The lab head camera also uses bone 78 and a different chain (see section 4).

## 2. Global pointers and singletons

| Address | Name | Description | Confidence | Verified where |
|---|---|---|---|---|
| `0x593E878` | `G_WorldChrMan` | `[g]` = WorldChrMan; player ChrIns = `[[g]+0x60]` | confirmed-live | every head-camera cave, every frame |
| `0x593E860` | `G_CameraRoot` | `[[g]+0x2830]` = camera manager (object 0x1150 B) | confirmed-live | read_cam.py, caves |
| `0x59406C8` | `G_SprjGraphics` | `[g]` = SprjGraphics (0x6A0 B) | confirmed-live | gfx_inspect.py; sampler writes |
| `0x59406E0` | `G_SceneParams` | static scene post-effect parameter block (not a pointer) | confirmed-live | read in Hunter's Dream and Yharnam |
| `0x5865ED0` | `G_YebisContext` | `[g]` = YEBIS context | confirmed-live | yebis_probe.py, DBG probe `AA` |
| `0x5940340` | `G_SoloParamRepository` | `[g]` = repository; `[[[[g]+0x9C0]+0x70]+0x70]` = LOCK_CAM_PARAM_ST blob | confirmed-live | dump_cam_params.py; rows edited live |
| `0x59402D8` | `G_LodBankMan` | `[g]` = LodBankMan object; `[[[[g]+0x68]+0x70]+0x70]` = LOD_BANK blob | confirmed-live | read_lod.py; rows edited live |
| `0x593B168` | `G_DrawEntityManager` | block array `[M+0x28]`, block stride 0x1F8, count `+0xC8`, base `+0xD0`, entity 0x2E0 B, flags `+0x1FC` bit 14 = drawn | inferred | find_entities.py |
| `0x593B148` | `G_PlayerWarpContext` | ctx argument of the game warp `0x194B110` | confirmed-live | warp via call service |
| `0x593B120` | `G_MapState` | `[[g]+0xA7C]` = current map id compared by the warp | static-only | disassembly |
| `0x593D710` | `G_KeyValueStore` | PlayerWarp debug keys (`SprjEzSelectBot.PlayerWarp.igPosX/Y/Z`, `degX/degY`, `cDegX/cDegY`); get `0x24EC0F0`, set `0x24EC3B0` | static-only | disassembly |
| `0x593E88E` | `G_PlayerHide` | debug flag; no effect on rendering | confirmed-live | written live |
| `0x55289F8` / `0x55289FC` | `G_RenderResW/H` | render resolution u32 globals (1920x1080) | confirmed-live | resolution experiments |
| `0x59404D0` / `0x59404D4` | `G_UiScaleX/Y` | derived UI scale `W/1920.0`, `H/1080.0` | inferred | static + probe |
| `0x59404D8` / `0x59404DC` | `G_UiSizeCopy` | integer copies of UI W/H | confirmed-live | DBG probe `UI` |
| `0x4D25E58` | `G_PiOver180` | pi/180 float read by the FOV conversion | confirmed-live | generator asserts displacement bytes |
| `0x59406E4`, `0x5940A54` | `G_TimestepConstA/B` | static 1/60 constants (not live dt) | confirmed-live | read live |
| `0x5AA6C25`, `0x553AC88` | aniso debug globals | 'Aniso Debug' flag / 'MaxAnisotropy' global; readers not found | static-only | disassembly |
| `0x5527A94` | `G_CameraCollisionBit` | set every frame from a parameter; not a usable switch | inferred | |
| `0x57E5B30` | `G_ScePadImportSlot` | game import (GOT) slot holding the address of a libScePad function; the pad toggle derives the libScePad base from it (function offset `0xA30` in the module) and reads the pad report ring at module base + `0x28BDC` (12 reports x 0xE0 bytes, buttons dword first; touchpad = bit `0x100000`). The cave verifies the function prologue (`55 48 89 E5` ... `53 48 81 EC`) before trusting the layout | inferred | constants from the release generator; no live-verification record in the available notes |

## 3. Vtables used for validation

| Vtable | Object | Confidence |
|---|---|---|
| `0x579CF10` | `[pl+0x48]` model container | confirmed-live |
| `0x57A0820` | `[[pl+0x48]+0x18]` pose object | confirmed-live |
| `0x5770610` | `[pl+0x58]` module container | confirmed-live |
| `0x5735D70` | `[pl+0x3B0]` physics slot | confirmed-live |
| `0x57356F0` | `[[pl+0x3B0]+0x68]` physics body `X` | confirmed-live |
| `0x57A1500` | `[mod+0x5F8]` holder (after respawn) | confirmed-live |
| `0x57A0F10` | `[mod+0x20]` holder | confirmed-live |
| `0x57A1680` | `[mod+0x5F0]` | confirmed-live |
| `0x56E7980` | game-side AA pass (4 instances) | confirmed-live |
| `0x57B9080` | FFX effect scene controller (1 instance) | confirmed-live |

Finding all heap instances of a vtable: scan writable regions (excluding the big GPU arena) for the 8-byte vtable value at 8-byte alignment (`tools/dev/find_vtable_instances.py`, `ab_loop.py` `vt:`/`vtall:` addresses).

## 4. Player and world object graph

Player `pl = [[0x593E878]+0x60]`. *Verified where:* live reads in Hunter's Dream and Yharnam (cold start, death and respawn, teleports between the two maps) with `tools/dev/probes/*` and the head-camera caves running from the cheat JSON.

| Path / offset | What | Confidence | Notes |
|---|---|---|---|
| `pl+0x00` | vtable; slot `+0x458` (SetDispMask) is an empty `ret` for the player | inferred | hiding the player through it is impossible |
| `pl+0x48` | model container (vt `0x579CF10`) | confirmed-live | |
| `[pl+0x48]+0x18` | pose object (vt `0x57A0820`), `HOLD = 0x18` | confirmed-live | bone-array slots live here **before** a respawn |
| `[pl+0x48]+0x20` | holder (vt `0x57A0F10`), `HOLD = 0x20` | confirmed-live | one slot at `+0x110` seen |
| `[pl+0x48]+0x5F0` | object (vt `0x57A1680`) | confirmed-live | not searched by the cave |
| `[pl+0x48]+0x5F8` | holder (vt `0x57A1500`), `HOLD = 0x5F8` | confirmed-live | **after** a respawn: four pointers at `+0xC0/+0xC8/+0x1A0/+0x230` |
| `pl+0x58` | module container (vt `0x5770610`); `+8` = back pointer to `pl` | confirmed-live | model->world: R0 `+0x320`, R1 `+0x330`, R2 `+0x340`, translation `+0x350` |
| `[pl+0x58]+0x350` | model origin (translation row) | confirmed-live | **zero/NaN after a respawn**; use `X+0x1E0` |
| `pl+0x3B0` | physics slot (vt `0x5735D70`); `[+0x68]` = `X` | confirmed-live | |
| `X+0x1C0 / 0x1E0 / 0x1F0` | position copies; **`+0x1E0` is the one to read/write** (x,y,z,1; Y up; feet) | confirmed-live | example (-111.02, -56.44, -20.01) |
| `X+0x1D0` | angles `(pitchRad, yawRad, 0, 0)`; yaw `+0x1D4` (example -1.9228) | confirmed-live | writing yaw persists but the character does not turn until `0x1CBCF30(pl,1)` runs |
| `X+0x210` (u16) / `X+0x32A` (u8) | SetPosition flags `0x0101` / `1`; physics clears them | confirmed-live | |
| `pl+0xC0` | position copy equal to `X+0x1E0` | confirmed-live | do not write copies |
| `pl+0x3F8` | map id (u32), e.g. `0x18010000` (m24_01) | confirmed-live | warp only inside the same map |
| `pl+0x400 -> +0x30`, `[pl+0x60]+0x1B0` | further position copies | inferred | do not write |
| `pl+0x4D0 -> [+0xE8] -> +0xDD0` | 8 AABB-like elements, stride 0xA0; head element centre = head bone world position | confirmed-live | hit boxes |
| `pl+0xA68 -> [+0x50]` | **legacy** model-space `hkQsTransform[108]` pose (head = bone 78, neck 77); self-pointing/empty in fresh saves | confirmed-live | do not use; lab scripts still do |
| `pl+0xF8` / `pl+0x110` | observed `1` / `2` while locked on | inferred | |

### The bone arrays (head source of the FPS camera)

`BoneMatrixArray`: **170 bones x 3x4 float, row-major, stride 0x30**; translation = floats 3, 7, 11 of each entry; **head = bone 68** (byte offset `0xCC0`), neck 67 (`0xC90`). World space already: no model->world multiply. 3-4 copies exist, one pipeline stage (about one frame) apart. Where the array pointers sit inside the holder **differs per session and per model build** (seen: `+0x430/+0x570/+0x578`; `+0x320/+0x328/+0x400/+0x490`; `+0x450`; after respawn in the `0x5F8` holder `+0xC0/+0xC8/+0x1A0/+0x230`). The cave therefore stores the last working `(HOLD, ARROFF)` and rescans slots `0..0x5F8` (step 8) over holders `0x18, 0x20, 0x5F8` (older builds scanned only `0x300..0x600` of one holder). Plausibility test: the head must be within `(-0.5, 2.4)` m above the model origin and `< 1.5 m` horizontally, array pointer 16-byte aligned with high dword in `2..7`. Source: `confirmed-live`, Hunter's Dream and Yharnam, cold start, death/respawn, teleports.

The pose updates at **30 Hz in some maps** (Yharnam, every copy; change interval 33 ms) while origin and camera run at 60 Hz (`confirmed-live`, `cadence_probe.py`).

## 5. Camera structures

*Verified where:* live reads in Hunter's Dream and Yharnam (`camera/read_cam.py`, `camera/cam_persist.py`, lock-on entries by locked-versus-free differencing in Yharnam, FOV by image registration of screenshots). Manager `mgr = [[0x593E860]+0x2830]` (`confirmed-live`):

| Offset | Field | Notes |
|---|---|---|
| `+0x10/+0x20/+0x30/+0x40` | right / up / forward / position (R x U = F, lengths 1, orthogonal) | what the renderer gets; copied at `0x1836C54` (hook: rbx = mgr, xmm0..xmm2 = rows, xmm3 = position) |
| `+0x60` | follow camera `cam` | |
| `+0x68` | ChrAimCam (aim camera) | inferred |
| `+0x78` | BallistaAimCam | inferred |
| `+0x110 + n*0x80`, n = 0..5 | lock-on entries (identical): `+0x110` target ChrIns pointer (0 when not locked), `+0x120` lock point world (x,y,z,1), `+0x130..+0x15C` target model matrix, `+0x180` lock point local (y about 1.48) | confirmed-live (lock/free differencing) |

Follow camera `cam = [mgr+0x60]`:

| Offset | Field | Confidence |
|---|---|---|
| `+0x10/+0x20/+0x30/+0x40` | pose rows; orientation recomputed as look-at to the pivot every frame; **not writable from outside** (overwritten in < 12 ms) | confirmed-live |
| `+0x50` | FovY rad (0.7505 = 43.0 deg); approaches param-row `f5*pi/180` with a blend | confirmed-live |
| `+0x54 / +0x58 / +0x5C` | aspect 1.778 / near 0.05 / far 3000 | confirmed-live |
| `+0xA0..+0xD0` | pivot data; always 3.7 m along the view line | inferred |
| `+0x110 / +0x120` | right-stick rotation deltas, from `WorldChrMan+0x70/+0x80` | inferred |
| `+0x140 / +0x144` | pitch / yaw (rad) - **derived copies**, not state | confirmed-live |
| `+0x154` | lock factor, 1.0 when locked, ramps over about 1 s | confirmed-live |
| `+0x180 / +0x184 / +0x188` | FulcrumDist (3.33) / CamDistTarget (4.0) / CamDist (4.0); first two **recomputed every frame** | inferred names |
| `+0x18C / +0x190 / +0x194` | CamCastSphereRadius 0.05 / SafeMarginRate 0.1 / SafeMarginMax 0.3 | inferred names |
| `+0x198..` | chase fields (ChrTransChaseRate about 0.1 per frame: the camera "draws back" when walking starts) | inferred |
| `+0x2E0` | derived copy | confirmed-live |

`LOCK_CAM_PARAM_ST` (`repo+0x9C0`, 72 rows x 32 B, persistent): `f0` distance (4.0; bosses 3.7..6.2), `f1` -40, `f2` 0.45, `f3` 1.42, `f4` 22, **`f5` FOV degrees (43; a few 48)**, `f6/f7` int (9/5 or -1). The code clamps FOV to **38..48 degrees** at `0x183AF2B..0x183AF4E` (`confirmed-live`: FOV 60 was clamped to 48).

Param blob layout (`confirmed-live`): `+0x0A` u16 row count, `+0x0C` name string, `+0x40` row table of 24 B entries `{u32 id, u32 pad, u64 dataOffset, u64 nameOffset}`, row data at `blob+dataOffset`. The blob address changes every launch.

## 6. Graphics structures

*Verified where:* live reads and writes in Hunter's Dream and the four recorded Yharnam test scenes (`tools/dev/graphics/*`, `ab_loop.py`); resolution experiments by cheat-JSON writes and debugger crash analysis.

| Structure | Where | Contents | Confidence |
|---|---|---|---|
| SprjGraphics | `[0x59406C8]` | `+0x90` RT table (0xB0 B entries: `+0x68` colour RT, `+0x70` depth RT, `+0x80/+0x84` W/H); `+0xF0/+0xF4` W/H copies captured at creation; `+0x250` -> sampler container | confirmed-live |
| Sampler table | `[[0x59406C8]+0x250]+0x360` | 19 x 0x38 B: `+0` mipLODBias f32, `+4` MaxAnisotropy i32; aniso samplers (indices 8..15, 17) default 4 / bias 0, DisplacementMap 16 = 0, ShadowMap 0. **Post-init writes have no visible effect** | confirmed-live |
| Game AA pass | heap, vtable `0x56E7980` (4 instances, active one in `scene+0x1BC8`) | `+8` IgnoreParamFromOutside (u8), `+9` Enable (u8), `+0xC` mode i32 (0 FXAA, 1 FXAA3, 2 FXAA3HQ, **3 DLAA**), `+0x10..+0x1C` fxaa alpha/reduceMin/reduceMul/spanMax (1, 1/128, 1/8, 8), `+0x28` DLAA threshold (0.1), `+0x2C` lambda (static 2.0, live 2.44), `+0x30` epsilon (0.25) | confirmed-live |
| YEBIS context | `[0x5865ED0]` | `+0x130..+0x15F` init flags (`+0x145` ANTIALIAS_TEMPORAL, `+0x147` GAUSSIANBLUR, `+0x14F` ANTIALIAS, `+0x150` ANTIALIAS_DISTANCEFALLOFF); `+0x57C/+0x580` camera near/far; `+0x6D5` falloff dirty; `+0xB8C` TAA enable; `+0xB90` state (2); `+0xB98..+0xBA8` TAA params (0.05, 0, 0.1, 0.1, 0.001); `+0xBBC` AA enable (YEBIS FXAA2); `+0xBC0/+0xBC4` falloff near/far; `+0xC99` TAA active (computed) | confirmed-live |
| Scene params | `0x59406E0` (static) | `+0x1AC` DOF enable, `+0x1B0` focus distance (1.0), `+0x1B4` aperture F (5.6), `+0x1C0` CCD (43.27), `+0x220` YEBIS-AA enable, `+0x224` AntiAliasType (inferred position), `+0x2D0` CustomDof, `+0x2D4/+0x2D8` near/far custom, `+0x2EC/+0x2F0` far start/end (Hunter's Dream 10 / 50 m; Yharnam 100 / 150 m), `+0x2F4` far CoC size (0.3 / 0.05), `+0x2F8` far CoC scale (0.016 / 0.098), `+0x2FC` distance threshold | confirmed-live (read); **rewritten every frame** |
| LOD_BANK | `[[[[0x59402D8]+0x68]+0x70]+0x70]` | 64 rows x 20 B `{A,B,C,D floats, E u32}`; A and C are distances in metres (typical 5 / 20) | confirmed-live; meaning inferred |
| FFXSceneCtrl | heap, vtable `0x57B9080` | `+0x5C6` SFX-OFF u8, `+0x5C0` Update-MultThreadEnable | confirmed-live |
| Timestep object | heap (find the u32 `0x3C888889` at `+0x18`) | `+0x18` dt = 1/60 s with the 60 FPS mod; an init setting, **writing it does not freeze time** | confirmed-live |

## 7. Code sites and hooks used by the release build

| Address | Original bytes | Length | Patch | Mod | Confidence |
|---|---|---|---|---|---|
| `0x183F77B` | `48 81 C4 D8 03 00 00` (`add rsp,0x3D8`) | 7 | `jmp 0x54A0780` + 2 NOP; back `0x183F782` | head camera (FACE2) | confirmed-live |
| `0x1C090E0` | `55 48 89 E5 41 57` | 6 | `jmp 0x54A1100` + NOP; back `0x1C090E6` | head camera (NOCOLL) | confirmed-live |
| `0x1836C54` | `C5 F8 29 5B 40` (`vmovaps [rbx+0x40],xmm3`) | 5 | `jmp 0x54A1600`; back `0x1836C59` | head camera | confirmed-live |
| `0x125970F` | `C5 FA 10 46 18` (`vmovss xmm0,[rsi+0x18]`) | 5 | `jmp 0x54A1300`; back `0x1259714` | DLAA threshold | confirmed-live |
| `0x25D803D` | `E8 AE B7 9D FE` (`call 0xFB37F0`) | 5 | `call 0x54A0400` (stub tail-jumps to `0xFB37F0`) | Aniso 16x | confirmed-live (works; no visible effect) |
| `0x183AF5A` | `FA AE 4E 03` (disp32 -> `0x4D25E58`) | 4 | disp32 -> `0x54A0500` | Wide FOV | confirmed-live |
| `0x25D7A8B` | `0F 95 C0` (`setne al`) | 3 | `31 C0 90` | No DOF | confirmed-live |
| `0x243487E` | `41 C7 44 24 18 89 88 08 3D` (dt = 1/30) | 9 | `... 89 88 88 3C` (dt = 1/60) | 60 FPS | confirmed-live |
| `0x26A057B` | `74 16` | 2 | `EB 16` | No Motion Blur | confirmed-live |
| `0x269FAA8` | `8B 85 90 F5 FF FF 89 83 AC 00 00 00` | 12 | `C7 83 AC 00 00 00 00 00 00 00 90 90` | No CA | confirmed-live |
| `0x4D99138`, `0x4D99154`, `0x4D9916E` | `4C 00 6F 00` (UTF-16 "Lo") | 4 each | zeros | Skip Intro | confirmed-live |
| `0x23B67B3` | `49 C7 46 08 00 00 00 00` | 8 | `... 01 01 01 01` | DLC unlock | inferred (no maintainer test recorded) |
| `0x2FBF178`, `0x2483EC1` | assert entry / vsync call | 4 / 1 | `xor rax,rax; ret` / `ret` | 60 FPS | confirmed-live |

The 60 FPS mod has 128 entries between `0xFBC40F` and `0x2FBF178` (list: `tools/mods/data/base_mods.json`). Always rebuild `off` bytes from an unpatched dump (`tools/mods/fill_off_from_dump.py`, `verify_against_dump.py`).

Other sites worth knowing (all `confirmed-live` unless marked):

| Address | What |
|---|---|
| `0x25D802C` / `0x25D8034` / `0x25D803D` | scene AA apply: `cmp [r15+0x220],0` / `setne al` / `call SetAntialiasEnable` (per frame). Forcing `B0 01 90` at `0x25D8034` enables YEBIS FXAA2 on top of the game's DLAA (-30 % sharpness): not shipped |
| `0x25D7A84` / `0x25D7CA7` | DOF enable consumer (`cmp [rbx+0x1AC],0`, call `0xFB2960`) / CustomDof consumer (`cmp [0x59406E0+0x2D0],0`, call `0xFB3600`) |
| `0x25D32AB` -> 12, `0x25D32B5` -> 16 | YEBIS temporal-AA init flags (TAA enable then works but shows no effect) |
| `0xFB37F0` -> `0xFD31F0` | SetAntialiasEnable (writes `[ctx+0xBBC]`); `0xFB3810` GetAntialiasEnable; `0xFD3270` SetAntialiasFalloffDistance(near, far); `0xFD2CB0` SetTemporalAntialiasEnable; `0xFD2D20` ...Parameters; `0xFE7580` ApplyEffects_TemporalAntialias (static-only) |
| `0x1258940` / `0x1258D30` / `0x12596F0` / `0x1259730` / `0x1258C50` / `0x56E79A0` | AA pass ctor / execute / parameter copy (every frame) / debug registration / pass assembler / shader-name table (static + live) |
| `0x126C5D0` | interpolates scene AA parameters from two `scene_draw_param` rows (static-only) |
| `0x25E02B0` | debug-menu registration of the YEBIS AA parameter block (static-only) |
| `0x183AC60` | follow-camera update (entry `55 48 89 E5 41 57`); `0x183AE68` CamDist lerp load; `0x183AEEF` pivot height load; look-at/pose writers `0x183B399, 0x183B649, 0x183EBB2, 0x183EC5E, 0x183EFC0` |
| `0x183AF2B..0x183AF4E` | FOV clamp 38..48 degrees |
| `0x18368B0` | camera manager update (calls `0x183AC60`, then copies the pose); ctor `0x1835FC0` (static-only) |
| `0x183FB60`, `0x18349B0`, `0x18316A0` | follow / aim / ballista camera debug registrations (static-only) |
| `0x194B110` | game warp `(ctx=[0x593B148], &mapId, &pos, &rot)`; caller `0x1948740`; save `0x194EA30` |
| `0x1CC16A0` / `0x1CC1770` / `0x1CBCF30` | SetPosition / angle wrap / apply facing `(pl, 1)` |
| `0x17CA580` -> `0x19A6CA0` | SetDrawEnable (static-only) |
| `0x191E97B` | `call [rax+0x18]` in `CSChrThread4`: crash site after toggling an enemy-movement cheat at runtime (not our code) |
| `0x26FD9EB` / `0x26FD9F2` | SFX-OFF initialiser / byte `00 -> 01` static toggle candidate (never tested; static-only) |
| `0x2703570`, `0x27035F6`, readers `0x26FF427 (0x26FF340)`, `0x2701A8D`, `0x270207C`, `0x270292C` | SFX-OFF debug registration and readers (static-only) |

## 8. Resolution experiment addresses (all negative results, kept for reference)

| Address | What | Confidence |
|---|---|---|
| `0x55289F8/0x55289FC` | render resolution globals; 1280x720, 1600x900, 1920x1080 start, everything else crashes | confirmed-live |
| `0x15E48E9`, `0x15E4620` | video-out buffer attributes (hard-coded 1920x1080, pitch 1920, 2 buffers), swapchain creation | static-only |
| `0x2417770`, `0x2417700`, `0x219E850`, `0x241A2F0` | reads `SPRJ.WIN64.frameBufferW/H` and writes the W/H globals; setters | static-only |
| `0x2594AA6/0x2594ABD`, `0x2594EB7/0x2594EC2` | swapchain size / view-RT size loads (`mov ecx,[table]` -> `mov ecx,imm32; nop3`) | confirmed-live |
| `0x2358554` | Scaleform HUD viewport (18 bytes: `lea/mov/lea/mov` -> `mov eax,1920; nop4; mov ecx,1080; nop4`) | confirmed-live |
| `0x259F130` Texture::Create, `0x2565F90` CreateTexture2D, `0x2571D60`, `0x2AD5E90` swapchain surface, `computeSurfaceInfo` (tile mode 14) | surface creation chain; fails with error 8/9 for sizes other than 720p/900p/1080p | confirmed-live (debugger) |
| `0x259F874` | the fault site of every >1080p crash (main-buffer RT texture NULL); backtrace `0x2697B7A <- 0x219706A <- 0x219A57A` | confirmed-live |
| `0x1A44C55`, `0x1A452C7` | Lance's 23-byte pins keeping sun/light screen positions in 1080p space | confirmed-live |
| `0x21166D6`, rodata `0x4D29338..` | remaining hard-coded 1920x1080 pairs (movabs `0x438_00000780`) / divisors | static-only |

## 9. Head-camera data block `D = 0x54A0E00`

Derived from `tools/mods/make_head_camera_mod.py` (defaults of `build()`); all floats are live-tunable by writing the console with ps5debug (the cave reads them every frame). 16-byte vectors are 16-byte aligned. The core mod writes the tunables in three pieces on purpose: `BONEOFF..OFF_F` (16 B at `+0x04`), `LIMIT..R2` (20 B at `+0x18`), `HMIN..ALPHA` (12 B at `+0x30`); `ARROFF`, `COOL` and `HOLD` are the cave's own cached state (working holder/slot, scan back-off), start at zero and must **not** be rewritten when the cheat is toggled in a running game (a reset forces a full memory scan).

| Offset | Address | Name | Type | Default | Meaning |
|---|---|---|---|---|---|
| `+0x04` | `0x54A0E04` | BONEOFF | i32 | `0xCC0` (68*0x30) | head bone matrix offset |
| `+0x08` | `0x54A0E08` | OFF_R | f32 | 0 | right offset (m) along the game camera's right row |
| `+0x0C` | `0x54A0E0C` | OFF_U | f32 | 0.30 | up offset |
| `+0x10` | `0x54A0E10` | OFF_F | f32 | 0.32 | forward offset |
| `+0x14` | `0x54A0E14` | ARROFF | i32 | 0 (cave-owned) | working array-slot offset (self-healing); **not written by the cheat file** |
| `+0x18` | `0x54A0E18` | LIMIT | f32 | 100.0 | squared max head-to-game-camera distance |
| `+0x1C` | `0x54A0E1C` | MINN | f32 | 0.5 | FACE2 guard on cos^2+sin^2 |
| `+0x20` | `0x54A0E20` | YMIN | f32 | -0.5 | plausibility window lower bound (head above origin) |
| `+0x24` | `0x54A0E24` | YMAX | f32 | 2.4 | upper bound |
| `+0x28` | `0x54A0E28` | R2 | f32 | 2.25 | squared max horizontal distance head-origin |
| `+0x2C` | `0x54A0E2C` | COOL | u32 | 0 (cave-owned) | scan back-off counter (reloaded with 120); not written by the cheat file |
| `+0x30` | `0x54A0E30` | HMIN | f32 | 1.25 | camera height floor above the origin (feet) |
| `+0x34` | `0x54A0E34` | SNAP2 | f32 | 1.0 | squared snap distance of the smoothing |
| `+0x38` | `0x54A0E38` | ALPHA | f32 | 0.5 | smoothing factor |
| `+0x3C` | `0x54A0E3C` | HOLD | u32 | 0 (cave-owned) | which holder: offset in the model container (`0x18`, `0x20`, `0x5F8`) or, with flag `0x10000`, in `A = [mod+0x10]` (vtable `0x57A2AC0`: `0x10460`, `0x10470`, `0x10478`); not written by the cheat file |
| `+0x40` | `0x54A0E40` | LASTH | vec4 | runtime | latched head (30 Hz pose) |
| `+0x50` | `0x54A0E50` | LASTO | vec4 | runtime | latched origin of that frame |
| `+0x60` | `0x54A0E60` | OFFS | vec4 | runtime | smoothed head offset |
| `+0x70` | `0x54A0E70` | NOCOLL | u8 | 1 | camera collision casts return "no hit" |
| `+0x71` | `0x54A0E71` | MODE | u8 | 1 | position override on (written last) |
| `+0x72` | `0x54A0E72` | AIM | u8 | 0 | lock-on aim (own mod) |
| `+0x73` | `0x54A0E73` | FACE2 | u8 | 0 | display-only body facing (own mod) |
| `+0x74` | `0x54A0E74` | DEADF | u8 | runtime | death flag: HP `[[pl+0x3b0]+0x20]+0xf8` <= 0 (recomputed every frame while the head camera is on) |
| `+0x77` | `0x54A0E77` | SLOWON | u8 | 0 | death slow motion on (own mod; the hook at `0x1E196BB` is part of that mod) |
| `+0x75` | `0x54A0E75` | PADTOG | u8 | 1 | enables the touchpad double-click toggle of MODE (entry on `01` / off `00`) |
| `+0x76` | `0x54A0E76` | PADPREV | u8 | runtime | previous touchpad state (edge detection) |
| `+0x78` | `0x54A0E78` | FRAME | u32 | runtime | frame counter incremented by the pad code |
| `+0x7C` | `0x54A0E7C` | PADLAST | u32 | runtime | frame of the last rising edge (a second click within 30 frames toggles) |
| `+0x90` | `0x54A0E90` | FALLV | vec4 | (0, 1.53, 0, 0) | fallback head offset when no array found |
| `+0x140` | `0x54A0F40` | DALPHA | f32 | 0.2 | death camera: view smoothing factor `S += DALPHA*(T-S)` per frame |
| `+0x144` | `0x54A0F44` | DEPS | f32 | 1e-4 | death camera: minimum squared length before a vector is normalised (else the game's rows are kept) |
| `+0x148` | `0x54A0F48` | HA | u64 | runtime | address of the head matrix found this frame (0 = none); the death camera reads its rotation |
| `+0x150` | `0x54A0F50` | FS | vec4 | runtime | smoothed forward vector (seeded with the game's forward while alive) |
| `+0x160` | `0x54A0F60` | US | vec4 | runtime | smoothed up vector (seeded with the game's up while alive) |
| `+0x170` | `0x54A0F70` | DFLOOR | f32 | 0.30 | death camera: lowest camera height above the feet (m) |
| `+0x174` | `0x54A0F74` | DFLR | f32 | runtime | that floor as a world y coordinate for this frame |
| `+0x178` | `0x54A0F78` | TSCALE | f32 | 1.0 | global character time scale, multiplied into `[r13+0x374]` by the `0x1E196BB` hook (eased by the manager cave) |
| `+0x17C` | `0x54A0F7C` | PH1SCALE | f32 | 1.0 | time scale of phase 1 (the first PH1END frames after the death) |
| `+0x180` | `0x54A0F80` | PH1END | u32 | 300 | frames after the death during which PH1SCALE is the target (then PH2SCALE until PH2END) |
| `+0x184` | `0x54A0F84` | SLOWG | f32 | 0.25 | easing factor per frame |
| `+0x188` | `0x54A0F88` | DCNT | u32 | runtime | manager frames since the death (real time) |
| `+0x198` | `0x54A0F98` | KILLER | u64 | runtime | ChrIns the killer camera looks at (0 = none), chosen on the first dead frame |
| `+0x1A0` | `0x54A0FA0` | DEADP | u8 | runtime | the killer has been chosen for this death |
| `+0x1A1` | `0x54A0FA1` | KILLCAM | u8 | 0 | killer camera on (own mod) |
| `+0x1A4` | `0x54A0FA4` | KCNT | u32 | runtime | manager frames since the death (killer camera) |
| `+0x1A8` | `0x54A0FA8` | LOCKAT | u32 | 0 | frame after the death at which the view turns to the killer |
| `+0x1AC` | `0x54A0FAC` | KRANGE2 | f32 | 400.0 | squared search range (20 m) for the nearest living character |
| `+0x1B0` | `0x54A0FB0` | KHEIGHT | vec4 | (0, 1.3, 0, 0) | offset from the killer's feet to the aim point |
| `+0x1C0` | `0x54A0FC0` | WORLDUP | vec4 | (0, 1, 0, 0) | up vector of the killer view |
| `+0x1D0` | `0x54A0FD0` | DALPHA2 | f32 | 0.10 | easing of the turn to the killer |
| `+0x1D4` | `0x54A0FD4` | ALPHAUSE | f32 | runtime | easing factor in use this frame (DALPHA or DALPHA2) |
| `+0x1D8` | `0x54A0FD8` | NEARF | u8 | runtime | close-character guard active this frame (the game's camera is used; the FACE2 epilogue is skipped) |
| `+0x1DC` | `0x54A0FDC` | NEARC | u32 | runtime | frames left until the guard releases |
| `+0x1E0` | `0x54A0FE0` | NEARR2 | f32 | 0.25 | squared 3D distance (0.5 m) between the camera and a living character's torso point; 0 disables the guard |
| `+0x1E4` | `0x54A0FE4` | NEARHOLD | u32 | 90 | frames the guard stays on after the last detection |
| `+0x1F0` | `0x54A0FF0` | NEARTORSO | vec4 | (0, 1, 0, 0) | offset from a character's feet to its torso point |
| `+0x18C` | `0x54A0F8C` | PH2SCALE | f32 | 0.05 | time scale of phase 2 (slow motion after the YOU DIED screen has arrived) |
| `+0x190` | `0x54A0F90` | PH2END | u32 | 720 | frames after the death at which the time scale returns to 1.0 |
| `+0xA0` | `0x54A0EA0` | AIMMIN2 / AIMMAX2 / AIMCOS / AIMWMIN | 4 x f32 | 0.09 / 3600 / 0.3 / 0.05 | target distance window (0.3 m..60 m, squared), min cos(angle), AIMWMIN unused |
| `+0xB0` | `0x54A0EB0` | ONE / EPS / BETA / GAMMA | 4 x f32 | 1.0 / 1e-6 / 0.3 / 0.35 | constants; BETA = aim easing; GAMMA unused |
| `+0xC0` | `0x54A0EC0` | MASKXYZ | 4 x u32 | `FFFFFFFF x3, 0` | mask |
| `+0xD0` | `0x54A0ED0` | MASKRAND | 4 x u32 | `FFFFFFFF,0,FFFFFFFF,0` | mask |
| `+0xE0` | `0x54A0EE0` | SIGNZ | 4 x u32 | `0,0,80000000,0` | sign mask |
| `+0xF0` | `0x54A0EF0` | SIGNALL | 4 x u32 | `80000000 x4` | sign mask |
| `+0x118` | `0x54A0F18` | TR / TU | 2 x f32 | 0 / 0 | camera-space aim offset (persists after the lock is released) |
| `+0x120` | `0x54A0F20` | FPREV | vec4 | runtime | previous game forward row |
| `+0x130` | `0x54A0F30` | DECAY / MOTCOS / TINY | 3 x f32 | 0.97 / 0.99998 / 1e-6 | aim decay while turning, turn detection, "no offset" threshold |

## 10. Console-side files and formats

| Path (console) | Meaning |
|---|---|
| `/data/OnionHEN/cheats/CUSA03173_01.09.json` | the active cheat file (name = title id + version) |
| `/data/OnionHEN/config.ini` | onionHEN configuration (`[shortcuts]` key `cheats_menu`: `off`, `r3_l3`, `l2_triangle`, `long_options`, `long_share`, `share`) |
| `/data/OnionHEN/debug_probes.txt` | overlay probe definitions, hot-reloaded (about 5 s) |
| `/data/ps5_autoloader/onionHEN.elf`, `/data/OnionHEN/onionhen.elf` | launcher ELF / bootstrapper (the paths depend on the autoloader setup) |
| `/system_tmp/onionhen/fps_sample` | 128-byte daemon->ShellUI sample (below) |
| `/system_tmp/onionhen/screenshot_request`, `screenshot_ack`, `screenshot_state` | screenshot hook control files |
| `/user/av_contents/photo/NPXS40087/<title>/<hash>/<ts>.jxr` and `.meta` | screenshots; `.meta` has `absoluteTime` (epoch ms) |
| `/data/toast.txt` | text shown by the toast payload |

`fps_sample` layout (little endian, `confirmed-live`): `u32 magic @0`, `u32 seq @4` (seqlock), `i32 pid @8`, `u8 valid @12`, `u8 source @13`, `f32 fps @16`, `u64 unix_ns @24`, `char title_id[16] @32`, `u32 game_mem_mb @48`, `char dbg[72] @52`, `u8 reserved[4] @124`.

`debug_probes.txt` line: `<title_id> <label> <base_hex> <deref 0|1> <name:size:offset_hex>...` (up to 12 probes, 6 fields each, sizes 1/2/4/8, values printed as unsigned decimals, text capped at 71 characters). Example from the lab: `CUSA03173 AA 5865ED0 1 FX:1:BBC TA:1:B8C`.

## 11. Static string leads (not yet traced to consumers)

All `static-only`: fog (`FOG MANAGER` `0x4D9FE34`, `FogInterpRatio` `0x4DCC3C0`, `Fog Param` `0x4DD185E`, `DepthFogDensity` `0x4CACF08`, `FXBillboardParam` `0x4C95D5C`, `LightShaftMask` `0x3046387`, `hclSimpleWindAction` `0x4BAF1D5`); DOF (`fParam_FocusDistance` `0x306A657`, `...FactorScaleOffset` `0x306A5C0`, `...FactorThreshold` `0x306A5E9`, `CDepthOfField` `0x4AD78A0`, `DofGlareQuality` `0x4D830DA`, `DepthOfFieldQuality` `0x4DC7C2E`); LOD (`CSLod` `0x4D350BC`, `LodBankMan`/`LOD_BANK` `0x2142B20`/`0x231129D`, `Disable Entity Culling` `0x26B8841`, `Enable Primitive Culling` `0x26B8DDE`, `Prim Culling Model Count` `0x26B8E19`, `Lod%d` `0x2646DD2`, `NearFade/FarFade` `0x260BCC9`/`0x260BD7F`, `LodLevel` stats `0x25C7010`, `<LodLvBias/<LodLvDisp` `0x4DAD522`, Havok `numBonesPerLod`/`numTracksInLod`/`currentLod`); camera (`ChrCam` `0x4D52ACA`, `<CamDist` `0x4D52CC6`, `<CamDistTarget` `0x4D52CE6`, `ZoomInFovY/ZoomOutFovY` `0x4D52408`/`0x4D5242C`, `ZoomIn/OutOrg` `0x4D524C6..0x4D525D6`, `PrevCamZoom` `0x4D76C28`, `PrevCamZoomVel` `0x4D76D30`, `LockCamParam` `0x4DB2E94`, `CamPos`/`CamFov` `0x4CC807A`/`0x4CC80A8`, `camera_pos` `0x4DBC81C`); samplers (`Sampler` registration `0x25B29F0`); draw entities (`SprjModelDrawEntity` `0x4D34FAF`, `SprjAsmModelDrawEntity` `0x4D35003`).

Method for these: follow the debug-menu **registration** function of the string (`lea rsi,[rip+string]` in a register call) to find the struct offsets, then find the **consumer** by static xref of the field, then confirm live. Rewritten-every-frame fields need a consumer patch, not a data write.

## 12. Disagreements between sources (generator and live reads win)

| Topic | Older note | Current truth |
|---|---|---|
| YEBIS context address | `0x58C5ED0` (one lab note) | `0x5865ED0` (probe file and `yebis_probe.py`) |
| Head bone | 78 in the model-space `hkQsTransform` chain `[pl+0xA68]->[+0x50]` | **68** in the world-space 170-matrix arrays (release); the old chain is empty in fresh saves |
| Head-camera cave addresses | manager cave `0x54A1200`, epilogue `0x54A0780` | release: manager `0x54A1600`; epilogue `0x54A0780` is shared with the lab cave |
| `HMIN` | 1.40 | **1.25** (1.40 clipped walking bob) |
| Warp scratch | `0x54A0900/10/20` | `0x54A0C00/10/20` (lab script) |
| Camera cast hook cave | `0x54A0A80` (lab docstring) | `0x54A1100` (lab code and release) |
| `ARROFF` | `0x430` (generator docstring); `0x320` (older builds' initial value) | slot is session-dependent and cave-owned: the cheat file no longer writes `ARROFF`/`COOL`/`HOLD` (they start at 0 in zeroed memory, so the first run scans), self-healing |
