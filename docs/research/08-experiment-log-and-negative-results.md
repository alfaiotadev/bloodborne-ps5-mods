# 08 - Experiment log and negative results

A compact chronological table of what was tried and how it came out, followed by the negative
results grouped by topic. Dates are 2026 and from the lab notes; the order within one day is
approximate. Platform for everything: firmware 12.40, PS5 Pro, Bloodborne GOTY `CUSA03173` v01.09
([01](01-platform-and-tooling.md)).

Outcome legend: **works** (confirmed on the console and shipped or usable), **partial**,
**no effect** (controlled measurement against a noise floor), **failed**, **retracted** (first
result later shown wrong).

## 1. Chronological log

### Getting the 60 FPS patch to run (2026-09-30 to 2026-10-01)

| # | Date | Experiment | Outcome | Detail |
|---|------|------------|---------|--------|
| 1 | 09-30/10-01 night | Apply the 60 FPS patch as an onionHEN JSON cheat from the toolbox | **failed**: pre-write snapshot read fails on execute-only pages | [07](07-onionhen-integration.md#5-xom-fallback-for-the-rollback-snapshot) |
| 2 | 10-01 night | Write all 134 entries with ps5debug direct writes | partial: every write verifies, game crashes on entering gameplay (root cause found in #6) | [01](01-platform-and-tooling.md) |
| 3 | 10-01 night | Replace the engine's page-unprotect (`mmap` anonymous page) with an in-place `mprotect` | **works**: removes the zeroed-code-page crashes ("crash mid-run" and "crash at start" had this one cause) | [07](07-onionhen-integration.md#4-non-destructive-code-cave-mapping) |
| 4 | 10-01 night | Add `"enabled"`, create the session at `BigAppStarted`, freeze the game during the apply | **works** (128 writes in 23 ms) but game still crashed at start | [07](07-onionhen-integration.md#3-exec-time-auto-apply) |
| 5 | 10-01 evening | Dump the live image (91,045,888 bytes); decode the 19/18-write table of the community patcher; check sites with Capstone | partial: most sites match; one site looked broken at `0x283487E` | [01](01-platform-and-tooling.md#2-game-process-and-memory-model) |
| 6 | 10-01 | Test "executable variant mismatch" | **retracted**: the real cause was a **4 MB offset shift** (JSON used virtual addresses, engine added `0x400000`); `"absolute": true` fixes it. 60 FPS runs from the first menu | [01](01-platform-and-tooling.md#3-why-cheat-json-offsets-are-absolute-virtual-addresses) |
| 7 | 10-01 | Fix the CPU meter (idle threads `SceIdleCpu8..15`), retry thread for the session priming | **works** | [07](07-onionhen-integration.md#10-overlay-changes) |

### Image quality (2026-10-01 to 2026-10-03)

| # | Date | Experiment | Outcome | Detail |
|---|------|------------|---------|--------|
| 8 | 10-01 23:45 | Force YEBIS post-process AA (`0x25D8034`), A/B in the starting scene | partial: smoother edges. **Retracted interpretation** (see #36): it was FXAA2 on top of the game's DLAA | [03](03-anti-aliasing-and-image-quality.md) |
| 9 | 10-01 | TAA init flags (`0x25D32AB`, `0x25D32B5`) plus enable `[ctx+0xB8C]`; A/B on fences | **no effect** | [03](03-anti-aliasing-and-image-quality.md#temporal-anti-aliasing-enable-does-not-reach-the-screen) |
| 10 | 10-02 | Static analysis of supersampling; compare the community 720p and 1080p patch tables | Only the resolution constants differ; 720p control works | [03](03-anti-aliasing-and-image-quality.md#8-resolution-and-supersampling-failed) |
| 11 | 10-02 | 21 resolution configurations | **failed** except 720p, 900p, 1080p; every other size `SIGSEGV` at `0x259F874` | [03](03-anti-aliasing-and-image-quality.md#8-resolution-and-supersampling-failed) |
| 12 | 10-02 | Decouple swapchain and view render target from the render resolution ("supersampling works") | partial: starts at 1440p-2160p; HUD pinned at 1080p | [03](03-anti-aliasing-and-image-quality.md#the-working-variant-that-was-not) |
| 13 | 10-03 | Re-measure native 1080p against "4K to 1080p" | **retracted**: **no supersampling happens** (sharpness equal; 4K buffers allocated, not rendered). Biggest real gain of the series was removing chromatic aberration | [03](03-anti-aliasing-and-image-quality.md#the-working-variant-that-was-not) |
| 14 | 10-03 | Change of direction: stay at native 1080p/60, improve AA and LOD | decision | [03](03-anti-aliasing-and-image-quality.md) |
| 15 | 10-03 | Anisotropy 4x to 16x by live write, steps/pavement | partial: +9.2 % normalised (later shown to be fog drift) | [03](03-anti-aliasing-and-image-quality.md#anisotropic-filtering) |
| 16 | 10-03 | mip LOD bias 0 to -0.75, then to +2.0 | **no effect** (even +2.0 does not blur) | [03](03-anti-aliasing-and-image-quality.md#anisotropic-filtering) |
| 17 | 10-03 | Find the moving fog; effect-system flag `SFX-OFF` | **works** as a stabiliser: brightness sd 0.22 %, sharpness sd 0.2 % | [04](04-scene-automation-and-measurement.md#stabilising-the-environment-the-ffxsfx-layer) |
| 18 | 10-03 | Freeze time via the time-step object | **failed**: the field is an init value, not the per-frame delta | [04](04-scene-automation-and-measurement.md#stabilising-the-environment-the-ffxsfx-layer) |
| 19 | 10-03 | Depth of field parameters, live writes | values rewritten every frame; a one-frame write was visible | [03](03-anti-aliasing-and-image-quality.md#depth-of-field) |
| 20 | 10-03 | DOF off by code patch, Hunter's Dream | **partial**: far cells +14..+41 %, rest unchanged; a three-write version crashed the game (non-atomic write) | [03](03-anti-aliasing-and-image-quality.md#depth-of-field) |
| 21 | 10-03 | DOF off, Yharnam (ladder view, bonfire) | **no effect** (1.000 / 1.001) | same |
| 22 | 10-03 | LOD_BANK distances x4 | **no effect** on sharpness; a metal highlight widened | [03](03-anti-aliasing-and-image-quality.md#lod) |
| 23 | 10-03 | Forced YEBIS FXAA2, Yharnam bonfire | works as a change: **-33 %** sharpness, HUD softens too; rejected | [03](03-anti-aliasing-and-image-quality.md) |
| 24 | 10-03 | Per-frame anisotropy hook | works technically | [02](02-code-caves-and-hooks.md#per-frame-call-site-hook-anisotropy) |
| 25 | 10-03 | Anisotropy in the Yharnam corridor (4 to 16, 16 vs 1) and on the bridge (16 vs 1), then automated scenes | **no effect**; aniso work stopped; **the earlier +9 % was fog drift** | [03](03-anti-aliasing-and-image-quality.md#anisotropic-filtering) |
| 26 | 10-03 | Locate the camera, parameter table, FOV code clamp; FOV scale hook | **works** (x1.3 -> 55.9 degrees); x1.6 rejected as unpleasant | [03](03-anti-aliasing-and-image-quality.md#6-field-of-view) |
| 27 | 10-03 | Daily configuration deployed (60 FPS, no MB, no CA, no logos, FOV x1.3) | confirmed on hardware | [07](07-onionhen-integration.md#7-the-shipped-mods) |

### Automation and measurement (2026-10-03)

| # | Date | Experiment | Outcome | Detail |
|---|------|------------|---------|--------|
| 28 | 10-03 | Remote screenshot through a ShellUI hook | **works** (status 0, image time = ack - 1.0 s) | [04](04-scene-automation-and-measurement.md#2-screenshot-automation) |
| 29 | 10-03 | Player position structure; raw nudge; game warp | **works** inside a map; 27 m raw write reverted by the game | [04](04-scene-automation-and-measurement.md#3-player-position-and-warp) |
| 30 | 10-03 | External write of the camera pose rows | **failed** (undone in under 12 ms); solved with an epilogue hook (pose-lock + call service) | [04](04-scene-automation-and-measurement.md#4-camera-pose-lock-and-call-service) |
| 31 | 10-03 | Scenes: record/replay position and camera | **works**: 0.000 m error, shift (0, 0) | [04](04-scene-automation-and-measurement.md#5-scenes) |
| 32 | 10-03 | Race on the call flag read-back | fixed (no verify read); 2 of 8 warps had crashed | [02](02-code-caves-and-hooks.md#9-other-crash-stories-platform-level) |
| 33 | 10-03 | Texture streaming: settle time, warm-up pass | wait 5 s + one warm-up pass; sharpness spread -8..+15 % down to 0.2-5 % | [04](04-scene-automation-and-measurement.md#7-texture-streaming-and-other-gotchas) |
| 34 | 10-03 | End-to-end A/B runs: anisotropy (no effect), forced FXAA (positive control -30..-33 %) | the pipeline separates real effects from "no effect" | [04](04-scene-automation-and-measurement.md#6-the-ab-loop) |

### Anti-aliasing (2026-10-03)

| # | Date | Experiment | Outcome | Detail |
|---|------|------------|---------|--------|
| 35 | 10-03 | Static analysis of the debug menus: AA parameter struct, sampler table, LOD candidates | found the AA pass, sampler descriptors, `LOD_BANK` | [03](03-anti-aliasing-and-image-quality.md) |
| 36 | 10-03 | The game's own AA pass | **found: it is already DLAA** (mode 3, threshold 0.1, lambda 2.44, epsilon 0.25) | [03](03-anti-aliasing-and-image-quality.md#3-discovery-the-games-own-aa-pass-is-already-dlaa) |
| 37 | 10-03 | 11 AA states x 3 scenes | AA off +4..+10 %, FXAA -30 %, FXAA3 -15..-23 %, FXAA3 HQ +6..+11 % (no AA effect), lambda 4 -4..-7 %, lambda 1 +3..+8 % | [03](03-anti-aliasing-and-image-quality.md#4-aa-experiments-and-results) |
| 38 | 10-03 | YEBIS temporal AA: enable and weights 0.02-0.6 | **no effect**; parked | [03](03-anti-aliasing-and-image-quality.md#temporal-anti-aliasing-enable-does-not-reach-the-screen) |
| 39 | 10-03 | Distance-falloff FXAA2 | partial: falloff 3-15 keeps far sharpness; not shipped | [03](03-anti-aliasing-and-image-quality.md#yebis-fxaa2-on-top-and-distance-falloff) |
| 40 | 10-03 | DLAA threshold sweep 0.05-1.0 (and lambda / epsilon variants) | **works**: monotonic; 0.3 chosen by visual preference; one scene dropped after a death | [03](03-anti-aliasing-and-image-quality.md#choosing-a-default-the-dlaa-threshold-sweep) |

### The FPS head camera (2026-10-03 to 2026-10-04)

| # | Date | Experiment | Outcome | Detail |
|---|------|------------|---------|--------|
| 41 | 10-03 | FPS by follow-camera distance 0.05-0.3 m and pivot height | partial: hood in view; distance 0 unstable | [05](05-fps-head-camera.md#10-failure-and-crash-catalogue) |
| 42 | 10-03 | Negative distance (-0.15..-0.45 m) | **failed**: the camera turns to look at the character | same |
| 43 | 10-03 | `Player Hide` flag and mesh display mask | **no effect** on rendering | same |
| 44 | 10-03 | Forward offset +0.2 m; chase-rate experiments | partial: hood out of view; pull-back at walk start remains | [05](05-fps-head-camera.md#11-first-attempt-hood-view-by-parameters-history) |
| 45 | 10-04 | Camera on the head bone (model-space pose, bone 78), override inside the follow camera | **failed**: "tornado" (about 9400 degrees/s) | [05](05-fps-head-camera.md#10-failure-and-crash-catalogue) |
| 46 | 10-04 | Override only the manager's output copy (manager mode) | **works**; collision-cast hook fixes the pull-in flicker | [05](05-fps-head-camera.md#2-final-design-in-one-picture) |
| 47 | 10-04 | Forced body facing by writing yaw (FACE) | **failed**: tank controls; replaced by display-only FACE2 | [05](05-fps-head-camera.md#8-face2---the-body-faces-the-camera-display-only) |
| 48 | 10-04 | Ship as cheat JSON; new head source (170 world-space bones, bone 68); self-healing slot scan | works; revealed varying layouts and crashes | [05](05-fps-head-camera.md#4-bone-arrays-and-the-holder-search) |
| 49 | 10-04 | Debugger attach catches `SIGSEGV` at `0x54A1792` | root cause `0x1_0000_0003` pointer; **fixed** | [02](02-code-caves-and-hooks.md#8-the-sigsegv-root-cause-story) |
| 50 | 10-04 | Debugger attach catches `SIGSEGV` at `0x54A1C17` after dying (`rax = 0x500000CC0`) | packed integer `0x5_0000_0000` passed the window 2..7; **fixed** (window 2..3, low dword >= 0x10000); repeated deaths from a cold start no longer crash | [02](02-code-caves-and-hooks.md#8-the-crash-story) |
| 50 | 10-04 | Height floor `HMIN`, wider plausibility window | **works** (rolls, crouches) | [05](05-fps-head-camera.md#height-floor) |
| 51 | 10-04 | Death/respawn, teleports | holder moves, model matrix zero: origin from the physics body, three-holder search, fallback; **works** | [05](05-fps-head-camera.md#5-the-origin-the-latch-and-the-smoothing) |
| 52 | 10-04 | 30 Hz pose in Yharnam | latch + smoothing; **works** | same |
| 53 | 10-04 | FACE2 in the JSON build | coat/hood cloth disappears; shipped off | [05](05-fps-head-camera.md#8-face2---the-body-faces-the-camera-display-only) |
| 54 | 10-04 | Lock-on aim: find the target, camera-space offset | experimental mod, accepted after three iterations | [05](05-fps-head-camera.md#9-lock-on-aim-experimental) |

## 2. Negative results at a glance

### Rendering

- **Supersampling above 1080p does not work.** The swapchain surface computation accepts only 720p,
  900p and 1080p; decoupling the buffers lets the game start but nothing is rendered at the higher
  resolution. No render-then-downscale path exists in the engine.
- **No resolution table in the binary**: sizes other than 720p / 900p / 1080p fail at texture
  creation, including smaller ones (960x540).
- **Temporal AA enable does nothing** visible; it would need camera jitter and routing of the history
  output.
- **FXAA, FXAA3** are softer than the game's DLAA; **FXAA3 HQ** does nothing in this configuration.
  Forced YEBIS FXAA2 softens the HUD too.
- **Anisotropy and mip bias writes do not change the picture**; the 16x hook is technically sound
  and visually inert.
- **DOF off** matters only where the scene's far blur is strong (Hunter's Dream); mild or zero in the
  Yharnam areas tested.
- **LOD distances x4** gave no sharpness gain.
- **Wide FOV x1.6** is too much; 1.2-1.3 is the usable range.
- **Freezing time** through the time-step object does not work.

### Measurement

- Raw Laplacian sharpness is misleading under brightness drift; use a normalised metric.
- Fog and particles dominate unstabilised comparisons (+-6..10 % drift) until the effect layer is off.
- A warp does not unload textures; without a warm-up pass sharpness varies -8..+15 %.
- A death breaks texture streaming and moves heap objects; discard the run.
- A first "clear" result with the fog on (anisotropy +9 %) was an artefact.

### Camera and player

- The follow camera's pose rows cannot be written from outside (look-at recomputation).
- Moving the position inside the follow camera's own state produces the "tornado".
- Negative follow distance flips the camera to the front; distance 0 is a look-at singularity.
- `Player Hide` and the mesh display mask do nothing for the player model.
- Forcing the character's yaw gives tank controls; display-only rotation (FACE2) works but hides the
  coat and hood cloth.
- Stick values and a pad-button bitmask were not found by diff scans.
- Raw position writes over 1 m are reverted by the game; the game's own warp works inside one map.
- The old model-space pose chain is empty on a fresh save.

### Platform and engine

- Toggling frame-rate patches or enemy-AI cheats during play can crash the game.
- Stock onionHEN replaced the page it unprotected with zeros.
- Cheat offsets must be absolute virtual addresses.
- Code patches must be written as one atomic write; caves must be restored after the call sites.
- Mods with cave/data entries that have an empty `off` are probably not disable-able from the toolbox
  ([07](07-onionhen-integration.md#11-runtime-toggling-and-its-limits), inferred from the source).

## 3. Untested or open

- Anything on a base PS5, other firmware, other game versions or regions.
- FACE2 and the lock-on aim after a cold start (FACE2 explicitly untested when this log ended).
- Distance-falloff AA as a shipped mod; a custom downsample pass; real temporal AA.
- A pad toggle for the FPS camera; idle-animation damping; model scale mods.
