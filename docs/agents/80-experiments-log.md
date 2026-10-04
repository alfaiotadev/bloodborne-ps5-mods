# 80 - Experiments log: methodology and outcomes (including the negative results)

> Everything below was done on **firmware 12.40 with a PS5 Pro**, Bloodborne `CUSA03173` v01.09, by the maintainer together with an AI assistant, between 2026-09-30 and 2026-10-04. Nothing was measured on a base PS5. Condensed narrative: [../research/08-experiment-log-and-negative-results.md](../research/08-experiment-log-and-negative-results.md). Reproduce or extend using [20](20-tooling.md) and [30](30-code-cave-playbook.md). "Retracted" means a first result was later shown wrong; both are listed on purpose.

## 1. Methodology that worked

1. **State the question and the metric first** (fps from the overlay sample; sharpness; FOV in degrees; a value read back).
2. **Smallest live write first.** Change one value through ps5debug (`ab_loop.py`, `flag_toggle.py`, `code_patch.py`), look at `persisted after hold` (does the game rewrite it?), look at the picture. Only if the effect is real, build a persistent patch.
3. **Repeatable scenes.** Player position + yaw + absolute camera pose recorded once and restored by the game's own warp and the pose-lock cave (error 0.000 m; image shift (0,0) px). Always one **warm-up pass** (a warp does not unload textures; an area change does). Compare only shots from one visit/run. Wait about 5 s after a warp for textures.
4. **Stabilise the environment:** SFX-OFF removes moving ground fog/particles (brightness sd 0.22 %, sharpness sd 0.2 % over 103 s versus about 7 % drift without). Enemies away or a safe spot; a death invalidates the run.
5. **Screenshots by automation**, taken a short time after each state switch; matched to states by the console epoch time (`.meta absoluteTime` is about `ack - 1.0 s`).
6. **Metric:** brightness-normalised sharpness `mean|Laplacian| / (blur sigma 6 + 8)` on 1080p-equivalent luma (2x2 reduce of the 4K capture), whole frame and lower 40 % (grazing angles), `mean|d|`, phase-correlation shift; per-cell maps for far/near regions. Raw Laplacian is biased by brightness drift.
7. **Noise floor and controls:** repeat states (`A,B,A,B`) give the same-state noise; a **positive control** (an effect known to show: forced FXAA2 = -30 %) and a negative control (aniso 1 vs 16 on a surface that should visibly blur) prove the pipeline can see and can reject.
8. **Human judgement last:** blink/slider/strip pages and zoom crops; the maintainer's eyes decide taste (FOV x1.6 "psychedelic", DLAA 0.3 favourite). Numbers do not replace taste, taste does not replace numbers.
9. **Cold-start test** of anything shipped; load/roll/death/respawn/teleport stress for anything per-frame.
10. **Log everything with the console's clock**; restore every touched address in `finally`; keep the previous cheat file backed up.

## 2. Evidence rules for agents

* A result needs: setup, controls, noise floor, scene(s), build/commit of the generator, and whether it survived a cold start. Without these write "unverified".
* Distinguish *live write works* from *persistent patch works* from *cold start works* from *visible effect measured*.
* Never generalise to a base PS5, another firmware, another game version/region, or another output resolution.
* A negative result is a result: add it here with the evidence.

## 3. Table of experiments

Legend: **+** worked and shipped or kept; **-** negative; **~** partial or superseded; **R** retracted.

### 3.1 Delivery and platform

| # | Date | Question / experiment | Outcome | Lesson |
|---|---|---|---|---|
| P1 | 09-30 | Install the 60 FPS update as a repacked pkg (route A) | **-** PlayGoCore rejects the repack (`0x80F00612`, `num_block=0`): `origin-deltainfo.dat` (CNT entry `0x0408`) missing; the repack PFS is fully rebuilt (2606/2607 blocks differ from the plain update) so transplanting is impossible without full DLT format work. The plain official 1.09 update installs fine. | pkg route dead; use runtime patching |
| P2 | 09-30 | CNT digest formulas (builder verified byte-exact against the plain update) | **~** `de1 = sha256(keys + imgkey + gends + entry_table + digests)`, `de2 = sha256(keys + imgkey + gends + table[:0xC0])`, `dtd@0x140 = sha256(digests)`, `dbd@0x160 = sha256(body 0x2000-0xA00000)`; sc-entries must form one chain from the body start; `GetRawContentInfo` reads only the first 64 KB | solved but useless for route A |
| P3 | 09-30/10-01 | 60 FPS from Lance McDonald's patch as an onionHEN cheat (128 writes) | first runs **crashed at start** | see P4-P6 |
| P4 | 10-01 | Hypothesis: offsets do not match the GOTY eboot ("orphan `de` byte" at `0x283487E`, eboot variant) | **-** false lead; at the right address `0x243487E` the original `mov [r12+0x18],0x3D088889` (1/30 s) is found and patched cleanly | verify on the live dump before theorising |
| P5 | 10-01 | Offsets semantics | **+** cheat offsets are absolute VAs; onionHEN computes `0x400000 + offset` unless `"absolute": true`; all 134 writes had landed 4 MB too high (valid code, so verify passed) | `"absolute": true` everywhere |
| P6 | 10-01 | Why do mid-run toggles and starts crash? | **+** root cause: `mapCodeCave` mapped an anonymous page over the code page (zeros). Fixed: `kernel_mprotect` only. Plus exec-time auto-apply with SIGSTOP/SIGCONT (128 writes in 23 ms) | patched onionHEN ([70](70-onionhen-cheat-engine.md)) |
| P7 | 10-01 | Live dump of the unpatched game | **+** 91,045,888 bytes (`0x400000..0x5AD4000`) at about 82 MB/s; basis for every `off` value | keep a private dump |
| P8 | 10-01 | Is the patched 60 FPS stable? | **+** 60 fps from the first menu, no physics problems seen; longer tests (elevators, cloth, blood, loads, a late boss) listed as open; a cutscene of a DLC boss (Laurence) can soft-lock at 60 FPS, a property of the patch (lab note, not re-verified) | |
| P9 | 10-01 | CPU meter of the overlay | **+** idle threads are `SceIdleCpu8..15` (+Rv) on this console; units were mixed; fixed; home about 10 %, Bloodborne menu about 11-13 % | |
| P10 | 10-03 | Remote screenshot hook (ShellUI payload) | **+** works; armed by one real press; replay acks `status 0`; `absoluteTime` about `ack - 1.0 s` | A/B automation |
| P11 | 10-03 | Lance's NexusMods table (19 writes exe / 18 in the other variant) | **~** authoritative reference but the JSON is a wider set; the exe variant is not 1:1 for GOTY (a 1-byte `eb` write assumes the next original byte) | |

### 3.2 Resolution and supersampling

| # | Date | Experiment | Outcome |
|---|---|---|---|
| R1 | 10-02 | Static analysis: Lance's 720p vs 1080p differ only by the resolution globals; two pinned 23-byte blocks are in both | **+** understanding |
| R2 | 10-02 | 1280x720 control | **+** HUD/menu/inventory intact |
| R3 | 10-02 | 2048x1152 and 2560x1440 (even minimal base) | **-** always crash at `0x259F874` about 1.2 s after start (main-buffer RT texture NULL: `Texture::Create` fails, error 8/9) |
| R4 | 10-02 | 18 sizes via a launch queue | **-** only 1280x720, 1600x900, 1920x1080 start; 960x540, 1440x810, 1760x1088, 1792x1080, 1888x1062, 1904x1071/1072, 1920x720, 1920x1088, 1936x1089, 1952x1098, 2048x960/1080/1152, 2240x1260, 2560x1440, 2880x1620, 1280x1080 crash (not memory, not display, not pure 16:9) |
| R5 | 10-02 | Patch timing: the init order (property read -> graphics creation) is a race; patch landing in between gives RES != GX in the DBG probe | **~** fix: write all copies (globals + UI scale + int copies) |
| R6 | 10-02 23:00 | Swapchain (`0x2594AA6/AD`), view RT (`0x2594EB7/C2`) and HUD viewport (`0x2358554`) pinned to 1080p while the render global is 1440p..4K | **R** "supersampling works" (Laplace energy 720p < 900p < 1440p) |
| R7 | 10-03 | A/B sliders + measurements of native 1080p vs "4K -> 1080p" | **-** identical (hard steps 8.78 % vs 8.72-8.75 %; spectra above Nyquist 0.210 % vs 0.210 %; arena data 1504 MB vs 1421 MB; fps 58.2 vs 58.7): 4K buffers allocated but not written at full resolution; no render->swapchain scaling path in the engine. The biggest real gain was CA removal. |
| R8 | 10-03 | Direction change: stay at 1080p/60 fps, improve AA and LOD | decision; `computeSurfaceInfo` diagnostic hook parked |

### 3.3 Anti-aliasing

| # | Date | Experiment | Outcome |
|---|---|---|---|
| A1 | 10-01 | Force YEBIS FXAA2 (`0x25D8034` `0F95C0` -> `B00190`), Hunter's Dream 3840x2160 shots | **~** smoother thin bars; later understood as FXAA2 over the game's DLAA |
| A2 | 10-01 | TAA init bytes (`0x25D32AB` -> 12, `0x25D32B5` -> 16) + `ctx+0xB8C = 1` | **-** no visible difference (no camera jitter) |
| A3 | 10-03 | Forced FXAA2 vs game default in Yharnam with SFX-OFF | **~** fine detail -33 %, staircase -28 %, but HUD softened; the "AA off" baseline was DLAA all along |
| A4 | 10-03 | Discovery of the game-side AA pass (vtable `0x56E7980`) | **+** Enable=1, mode 3 DLAA, thr 0.1, lambda 2.44, eps 0.25 in all 4 scenes |
| A5 | 10-03 | Mode sweep (11 states x 3 scenes) | **+** table in [50](50-aa-and-graphics.md): AA off +4..10 %, FXAA mode -30 %, FXAA3 -15..-23 %, FXAA3 HQ +5..11 % (jagged), lambda 4 -4..-7 %, lambda 1 +3.5..8 % |
| A6 | 10-03 | Distance-falloff YEBIS FXAA2 | **~** falloff 3-15 near DLAA (-2.7/-12 %), 10-60 near FXAA2; a third scene discarded (textures not streamed) |
| A7 | 10-03 | TAA enable with weights 0.02/0.05/0.3/0.6 | **-** `ctx+0xC99 = 1` but sharpness -0.2..-0.6 %, no tile difference |
| A8 | 10-03 | DLAA threshold sweep (0.05..1.0, lambda/epsilon variants) | **+** monotone sharpness; blink-test favourite **thr 0.3** (+3.2 / +1.7 %); FXAA and FXAA3 disliked; a scene run was ruined by a death |
| A9 | 10-03 | Persistent threshold patch | **+** hook at `0x125970F` -> cave constant (release mod) |

### 3.4 Texture filtering, DOF, LOD, environment

| # | Date | Experiment | Outcome |
|---|---|---|---|
| T1 | 10-03 | Aniso 4 -> 16 live, Hunter's Dream (sets 1, 2) | **R** +4 % raw, +9.2 % normalised, far stairs +18.9 % - later attributed to fog drift |
| T2 | 10-03 | mipLODBias 0 -> -0.75, then +2.0 | **-** no visible effect (field not applied after init, or ignored) |
| T3 | 10-03 | Aniso hook at the per-frame call `0x25D803D` (stub `0x54A0400`) | **~** technically works, stable; no effect |
| T4 | 10-03 | Aniso 4 vs 16 (corridor), 16 vs 1 (corridor), 16 vs 1 (steepest bridge angle), scene runs | **-** 0.999 / 1.001 / 1.000 / +0.1 / -0.1 %: table writes after init do not change rendering; mod shipped opt-in with that statement |
| D1 | 10-03 | DOF parameters live | **~** values overwritten every frame; one frame of effect visible; fields correct |
| D2 | 10-03 | DOF off via code (`0x25D7A8B`) in Hunter's Dream | **+** far cells +14..+41 %, whole frame +0.4 % |
| D3 | 10-03 | DOF off in Yharnam (long view; bonfire) | **-** 1.000-1.001; scene far DOF is weak (100-150 m, CoC 0.05); a first "crash" was the game dying after a 3-byte patch written as 3 writes (fixed: atomic write) |
| L1 | 10-03 | LOD_BANK found; A and C x4 | **-** sharpness 1.001; metallic glints on gate frames stronger (higher LOD brings material detail) |
| E1 | 10-03 | Time freeze via the timestep object `+0x18` | **-** init setting; nothing froze |
| E2 | 10-03 | `SFX-OFF` (`[FFXSceneCtrl+0x5C6]`) | **+** removes ground fog and sparkles; brightness sd 0.22 %, sharpness sd 0.2 %; flames removed, light stays; white fog wall remains |
| E3 | 10-03 | Texture streaming and warps | **~** a plain warp does not unload textures; warm-up pass stabilises (sharpness variation -8..+15 % without, +-3 % with); death breaks streaming until reload |

### 3.5 Camera and FOV

| # | Date | Experiment | Outcome |
|---|---|---|---|
| C1 | 10-03 | Camera manager/follow camera objects located; field persistence probe | **+** manager `[[0x593E860]+0x2830]`, follow cam `+0x60`; some fields persistent inputs, `+0x180/+0x184` recomputed, `+0x188/+0x50` blended |
| C2 | 10-03 | `LOCK_CAM_PARAM_ST` rows: distance x2, FOV 60 | **+** distance x2 works (whole staircase visible); FOV capped to 48 by code (`0x183AF2B..4E`) |
| C3 | 10-03 | Wide FOV by redirecting pi/180 constant | **+** measured 55.7-56.1 deg at x1.3 (expected 55.9), 68.8 at x1.6; **x1.6 rejected**; x1.3 default; deployed daily |
| C4 | 10-03 | "Hood view" FPS (distance 0.05 m, height 1.55, forward +0.2) | **~** works but the hood cloth sways into view; negative distance flips the camera to look at the character from the front; `Player Hide`, mesh mask and `SetDispMask` do not hide the player |
| C5 | 10-03 | Writing the camera rows/angles from outside | **-** overwritten in < 12 ms (look-at every frame, 5 code paths); no angle state exists; solution: epilogue hook (pose lock) |
| C6 | 10-03 | Pose lock + call service + game warp (scenes) | **+** repeatability 0.000 m; 27-100 m moves; same-map only |
| C7 | 10-03 | Raw position writes | **~** valid for about 1 m; 27 m reverted |

### 3.6 FPS head camera (all 2026-10-04)

| # | Experiment | Outcome |
|---|---|---|
| H1 | Camera bolted to the head bone (model-space `hkQsTransform`, bone 78) in the follow camera's epilogue | **~** works, but the camera "tornado" appears (pad code derives angles from the manager pose; squeeze/collision were not the cause) |
| H2 | Manager mode: override only the manager's output position (`0x1836C54`) | **+** tornado gone; height, bobbing, rolls, stick behaviour judged good |
| H3 | Camera collision off (`0x1C090E0` returns no hit) | **+** pull-in flicker (1.2 <-> 3.7 m) gone |
| H4 | Force the player's facing (FACE) | **-** "tank controls" |
| H5 | FACE2 (display-only rotation of model rows) | **+/-** strafing/backpedalling fine, coat/hood cloth vanishes; final guarded code **not** cold-start tested; default off |
| H6 | Cold start of the live-installed version (as cheat JSON) | **-** crashes at load: unvalidated pointers; later SIGSEGV at `0x54A1792` (`rax = 0x100000CC3`): the flag value `0x1_0000_0003` passed a `hi32 in 1..7` check; found with the debugger |
| H7 | Pose source changed to world-space arrays (bone 68, 170 matrices); slot offsets vary per session | **+** self-healing slot scan (`ARROFF`, `COOL`); head window `YMIN -0.5..YMAX 2.4` after rolls flicked the view to third person |
| H8 | Height floor `HMIN` 1.40 -> 1.25 | **+** 1.40 clipped walking bob; 1.25 final |
| H9 | Respawn: holder changes (`[mod+0x5F8]`), model matrix zero | **+** holder search over `0x18/0x20/0x5F8`; origin from the physics body `X+0x1E0`; fallback `FALLV` |
| H10 | 30 Hz pose in Yharnam | **+** latch + smoothing (`LASTH/LASTO`, ALPHA 0.5, SNAP2 1.0) |
| H11 | Cold-start stress: load, FPS, roll, death/respawn, teleports Hunter's Dream <-> Yharnam | **+** passes (maintainer: "perfect") |
| H12 | Lock-on aim: target found at `mgr+0x110/0x120`; iterations (hard conditions, game lock factor ramp, snap-back on release) | **+/~** final: immediate camera-space offset that persists after release, decays while turning; "good enough, someone else can make other profiles" |
| H13 | Runtime toggling of an enemy-movement cheat | **-** crash in `CSChrThread4` (not our code) |
| H14 | Button-combo toggle | the lab notes: pad bitmask not found; the **current generator** has a touchpad double-click toggle (pad report ring of libScePad); **no live-verification record available** - verify ([90](90-open-questions.md)) |
| H15 | Body silhouette spin when backpedalling starts | **-** accepted limitation |
| H16 | Death: the game's camera does not change when the player dies, the first-person view hovered at `HMIN` while the head fell to 0.17 m | **-** looked wrong |
| H17 | HP source: `pl+0x1178` aliases HP in one session only; `[[pl+0x3b0]+0x20]+0xf8` is stable across respawn (`[pl+0x3c0]+0x14` is a read-only mirror) | **+** `death_probe.py`; writing 0 there kills the player for tests |
| H18 | Death camera: no height floor, rows from the head bone (F = column 2, U = column 0), eased `DALPHA` 0.2 | **+** view tumbles with the head; maintainer: "great effect" |
| H19 | Camera clipped into the ground when lying (head 0.1 m above the feet) | **+** `DFLOOR` 0.30 on the final camera y; maintainer: better |
| H20 | Live-writing a cave whose code shifted while the game ran it | **-** crash; `apply_live.py` now restores the hook bytes first, writes the cave, then re-enables the hook |
| H22 | GTA-style slow motion at HP 0: scale the per-character speed factor `[[chr+0x3b0]+0x30]+0x374` (read at `0x1E196BB`, multiplies the character time step); the stock "Player's Speed x2" cheat has a PS4-era player check that never matches here | **+** `TSCALE` 1.0 -> 0.25 in ~0.5 s, held ~2 s; the head's fall slows to a third; maintainer: should be 10 % -> `SLOWMIN` 0.10 |
| H23 | "YOU DIED" appears when the death animation ends (maintainer observation); with the slow motion held for 50 s it took about a minute; snapshots of 237 global objects (`ui_probe.py`) and 25 Hz watching (`obj_watch.py`) found no single flag that starts the text (many timers/toggles); at a time scale of 3 the sequence from death to the load screen shrank from ~9.7 s to ~6.5 s | **~** profile changed to slow 75 frames, then `FASTMAX` 3.0 until 240 frames |
| H21 | World bone arrays not under `[mod+0x18/0x20/0x5F8]` in one session (holders under `[mod+0x10]` at `+0x460/0x470/0x478`) | **~** the cave scans these too (`HOLD` flag `0x10000`); that layout has not been seen again, so the path is untested live |

### 3.7 Not (yet) done

Player/enemy scale multipliers, foliage freeze, a real fog toggle for the white wall, TAA with jitter, true >1080p output, animation LOD, idle-animation damping in FPS, other firmware/base PS5 validation, cold-start test of the final FACE2. See [90](90-open-questions.md).

## 4. Cross-cutting lessons

* The baseline matters more than the effect: three "findings" (aniso +9 %, "AA off", "supersampling") came from an uncontrolled baseline.
* Measure with fog off, enemies away, warm start, noise floor, positive and negative controls.
* A value the game rewrites every frame cannot be changed by a data write; patch the consumer.
* Code patches: one atomic write, cave before hook, hooks restored first; a cave must be safe against objects that do not exist yet.
* Layouts that look stable are not (slot offsets, holders, matrices after respawn): search, validate, fall back.
* When the game crashes, attach the debugger instead of theorising.
* Judge visual changes with the maintainer's eyes **and** numbers; keep JXR originals.
