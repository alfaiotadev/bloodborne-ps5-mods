# 50 - Anti-aliasing and graphics: what is known, what failed, what to try

> Tested only on firmware 12.40 with a PS5 Pro; Bloodborne runs in backward-compatibility mode at **native 1080p** (output buffers hard-coded 1920x1080; a 4K screenshot is the console's upscale of that frame). All sharpness numbers come from 4K screenshots of that setup and are **not** valid for other consoles or outputs. Narrative: [../research/03-anti-aliasing-and-image-quality.md](../research/03-anti-aliasing-and-image-quality.md). Structures: [10](10-memory-map.md) section 6.

## 1. Results at a glance

| Topic | Result | Shipped |
|---|---|---|
| Chromatic aberration off | the single largest real image-quality gain | yes (default on) |
| Motion blur off | clean | yes (default on) |
| Game AA is already **DLAA** | all 4 tested scenes: Enable=1, mode 3, threshold 0.1, lambda 2.44, epsilon 0.25; YEBIS FXAA2 off | - |
| DLAA threshold 0.3 | +3.2 % / +1.7 % sharpness, the maintainer's favourite in blink tests | yes (opt-in) |
| Forced YEBIS FXAA2 | -30 %, softens HUD too; it was FXAA2 **on top of** DLAA | no |
| FXAA / FXAA3 modes of the game pass | worst in blink tests (-30 % / -15..-23 %); FXAA3 HQ does effectively nothing | no |
| YEBIS FXAA2 distance falloff | falloff 3-15 m close to DLAA, 10-60 close to plain FXAA2 | no |
| Temporal AA (YEBIS) | enabling works (`ctx+0xC99 = 1`) but no effect on the image | no |
| Anisotropic filtering 16x | hook works; **no measurable effect** (earlier +9 % was fog noise) | yes (opt-in, off) |
| mipLODBias | live writes have no effect | no |
| Depth of field off | far cells +14..+41 % in Hunter's Dream, **no effect** in Yharnam (far DOF 100-150 m) | yes (opt-in) |
| LOD_BANK distances x4 | no sharpness change | no |
| Supersampling / >1080p | **does not work**: only 720p, 900p, 1080p start; the "4K -> 1080p" test produced no extra detail | no |
| Fog layers | `SFX-OFF` flag removes ground fog/sparkles and stabilises A/B images; a white fog wall remains | research tool |

## 2. Pipeline facts

* Render at 1080p -> YEBIS post effects (DOF, bloom, tonemap, AA) -> game AA pass -> Scaleform HUD -> video-out buffers (hard-coded 1920x1080, pitch 1920, 2 buffers, `0x15E48E9`).
* **Two AA systems**: (1) the game's own render pass (vtable `0x56E7980`, class constructed `0x1258940`, executed `0x1258D30`, parameter copy `0x12596F0` every frame, debug registration `0x1259730`); (2) YEBIS' built-in FXAA2 (`SetAntialiasEnable`, off by default; scene enable at `[0x59406E0+0x220]`, applied at `0x25D802C..0x25D803D`). The old label "AA normal (off)" in early notes meant **only** YEBIS-FXAA2 off; the game was running DLAA the whole time.
* Scene parameters (`scene_draw_param_*` rows, interpolated by `0x126C5D0`) decide the per-scene AA values; `0x12596F0(this, src)` copies them into the pass each frame unless `[this+8]` (IgnoreParamFromOutside) is 1.

## 3. The game's DLAA pass

Fields (`confirmed-live`): `+8` IgnoreParamFromOutside (u8), `+9` Enable (u8), `+0xC` mode (i32: 0 `FXAA.ppo`, 1 `FXAA3.ppo`, 2 `FXAA3HQ.ppo`, **3 `DLAA.ppo`**), `+0x10..+0x1C` FXAA alpha/reduceMin/reduceMul/spanMax (1, 1/128, 1/8, 8), **`+0x28` threshold (0.1)**, `+0x2C` lambda (static default 2.0, live scene value 2.44), `+0x30` epsilon (0.25). 4 instances exist, only the active one has Enable=1. Assembling the pass: `0x1258C50` (mode + parameters; shader-name table `0x56E79A0`). Setting `+8 = 1` with the same values reproduces the game's look within -0.1..-0.3 % (the bypass path works).

### How the release mod works

`0x125970F` `vmovss xmm0,[rsi+0x18]` (copy of the scene's threshold into `pass+0x28`) -> 5-byte hook to a 13-byte cave that loads a constant (default 0.3) and jumps to `0x1259714`. Heap objects move every run, so only a code patch is persistent. Other thresholds: `python3 tools/mods/make_dlaa_mod.py --threshold X`.

### Sharpness sweeps (normalised Laplacian, relative to the game's own DLAA; scenes: sickroom fences / bonfire horizon / bridge)

| State | Sharpness change |
|---|---|
| AA off (Enable 0) | +10.4 / +4.8 / +4.4 % |
| YEBIS-style FXAA (mode 0) | -30.7 / -31.0 / -29.0 % |
| FXAA3 | -23.2 / -20.4 / -14.9 % |
| FXAA3 HQ | +10.8 / +5.7 / +7.5 % (zoom: as jagged as AA off) |
| DLAA lambda 4 | -7.2 / -6.7 / -4.2 % (softer) |
| DLAA lambda 1 | +8.2 / +4.2 / +3.5 % |
| threshold 0.05 | -1.8 / -1.0 / -1.0 % |
| threshold 0.3 | +3.2 / +1.7 / +1.9 % |

Threshold series (two valid scenes): 0.2 +2.0/+0.8; **0.3 +3.2/+1.7**; 0.45 +5.6/+3.2; 0.6 +8.1/+4.2; 0.8 +9.7/+4.6; 1.0 +10.4/+4.7 (= AA-off level); 0.3 with lambda 1.5 +6.3/+3.1, lambda 3.5 +1.2/+1.1, epsilon 0.1 +0.5/+0.9, epsilon 0.6 +7.4/+3.4. Sharpness rises monotonically with the threshold; more edge pixels stay unsmoothed. Eye judgement of blink comparisons (maintainer): **threshold 0.3 preferred; FXAA and FXAA3 worst**. One third scene was discarded because an enemy killed the player during the run.

Noise floors for these runs: sharpness sd 0.05 % (state repeats), `mean|d|` 0.5-0.9; the pipeline separates real effects from noise (positive control: FXAA2 on gave -30 % reproducibly).

## 4. YEBIS FXAA2, distance falloff and TAA

* **Forced YEBIS FXAA2** (`0x25D8034`: `0F 95 C0` -> `B0 01 90`): Yharnam scene: fine-detail metric -33 %, edge staircase measure -28 % (1.706 -> 1.227), strong edge pixel share 10.3 -> 6.2 %. Smoother wheelchair/iron fence, but the **whole image softens, including HUD text and icons**. Not shipped (the maintainer chose against it).
* **Distance falloff** (`SetAntialiasFalloffDistance(near, far)` `0xFD3270`: `ctx+0xBC0/+0xBC4` in metres, dirty flag `ctx+0x6D5` = 1 consumed immediately; needs `"noverify": true` in specs; requires the init flag `ANTIALIAS_DISTANCEFALLOFF` which is already set). With YEBIS AA forced on and DLAA off: falloff 3-15: -2.7 / -12.0 % (ground -14 / -17 %); 10-60: -22.1 / -26.4 %; 30-300: -29.5 / -28.3 % (= plain); DLAA + FXAA2 falloff 10-60: -25.9 / -27.5 %. Near zoom: FXAA2 smooths near-edge stairs clearly better than DLAA; falloff 3-15 is close to DLAA, 10-60 close to FXAA2. (A nearby bonfire scene was discarded: textures did not stream in.)
* **TAA** (init flags `0x25D32AB` -> 12, `0x25D32B5` -> 16 give `ctx+0x145`; enable byte `ctx+0xB8C` = 1 makes `ctx+0xC99` = 1): sharpness -0.2..-0.6 %, mean difference = noise, even in moving tiles; weights `+0xB98` 0.02/0.05/0.3/0.6 no difference. A working TAA would need (a) a per-frame sub-pixel projection jitter and (b) wiring the pass result into the final image: big and risky; parked.
* YEBIS context `[0x5865ED0]`: see [10](10-memory-map.md); read with `tools/dev/graphics/yebis_probe.py`; the AA pass instances with `tools/dev/graphics/aa_probe.py [scene...]`.

## 5. Anisotropic filtering and texture bias

Sampler table `[[0x59406C8]+0x250]+0x360`: 19 x 0x38 B, `+0` mipLODBias, `+4` MaxAnisotropy; aniso samplers (indices 8..15 and 17) default to 4. A live write of 16 is re-read immediately, and the first measurements (Hunter's Dream) suggested +9 % (far stairs +19 %). **That was fog noise**: with SFX-OFF the same comparison showed no effect in four tests: corridor 4 -> 16 (0.999), corridor 16 vs 1 (1.001, all cells 0.99-1.02), the steepest bridge angle 16 vs 1 (1.000), and two scene runs (+0.1 / -0.1 %). Table writes after init do not affect rendering (the table loop exists only in the debug-menu code), and mipLODBias +2.0 / -0.75 showed no visible change either. The shipped mod (`make_aniso_mod.py`: per-frame call-site hook at `0x25D803D`, stub `0x54A0400` writing 16 into the nine fields) works technically but is **too late**: samplers are created at initialisation. It stays opt-in and is documented as having no measurable effect. After removing the hook the table is **not** restored to 4 (the stub wrote 16 permanently).

To make it real: find the sampler creation code (consumer of the table; not found, only the debug menu registration `0x25B29F0`) and patch the values before creation, or patch the init that fills the table with 4.

## 6. Depth of field

`0x25D7A8B` (`setne al` feeding `SetDepthOfFieldEnable`) -> `31 C0 90` disables DOF (also in cutscenes). Scene DOF block (`0x59406E0`): `+0x1AC` enable, focus distance +0x1B0 (1.0), aperture F +0x1B4 (5.6), CCD +0x1C0 (43.27), far blur start/end +0x2EC/+0x2F0 and far CoC size/scale +0x2F4/+0x2F8. Hunter's Dream: 10 m / 50 m / 0.3 / 0.016 -> distant cells +14..+41 % when off (whole frame +0.4 %). **Yharnam: 100 m / 150 m / 0.05 / 0.098: no difference** (bonfire and long-view scenes: 1.000-1.001, cell changes +-1-2 %). DOF is **scene-specific and mild** in gameplay areas; the mod is optional. Live writes of the scene block revert within a frame (one frame of effect was visible: a "snap" of the far blur resetting), so a far-only tweak needs a patch at the consumer of the near/far values (not found; `0x25D7CA7` is the CustomDof enable).

## 7. Level of detail

`LOD_BANK` param (`[[[[0x59402D8]+0x68]+0x70]+0x70]`, 64 rows x 20 B `{A,B,C,D,E}`; A and C are distances in metres, typical 5 and 20; rows 19 and 63 are 9998/9999 = never; meaning inferred): multiplying A and C by 4 (all rows below 900 m, atomic row writes) gave **no sharpness change** (1.001, cells +-1 %, noise 0.1 %), but the maintainer saw the blue metallic glint of a gate frame stronger: the higher LOD adds material/specular detail to distant objects. Parameter edits take effect live. Unexplored LOD leads (strings only): Havok animation LOD (`numBonesPerLod`, `numTracksInLod`, `currentLod`), `<LodLvBias/<LodLvDisp` (`0x4DAD522`), debug menus `Disable Entity Culling`, `Enable Primitive Culling`, `Prim Culling Model Count`, `NearFade/FarFade Start/Range`, `Shadow Fade Start Dist`, `Lod%d` (lights).

## 8. Resolution and supersampling (negative result)

* Render-resolution globals `0x55289F8/0x55289FC` (+ UI scale `0x59404D0..DF`, Lance's pins `0x1A44C55/0x1A452C7`): **720p, 900p and 1080p start; every other size crashes** at `0x259F874` (main-buffer RT texture NULL after `Texture::Create` fails with error 8/9). 18 sizes tested: 960x540, 1440x810, 1760x1088, 1792x1080, 1888x1062, 1904x1071/1072, 1920x720, 1920x1088, 1936x1089, 1952x1098, 2048x960/1080/1152, 2240x1260, 2560x1440, 2880x1620, 1280x1080 all crash (not memory: sizes below 1080p crash too; not a pure 16:9 rule). The swapchain (`0x2AD5E90`) is created with the same size and its `computeSurfaceInfo` (tile mode 14) rejects everything else.
* A brief "supersampling works" result (swapchain, view RT and HUD viewport pinned to 1920x1080 while the render global was 2560x1440; patch sites `0x2594AA6/AD`, `0x2594EB7/C2`, `0x2358554`) was **retracted**: A/B sliders and measurements showed native 1080p and "4K -> 1080p" identical (hard 1-px steps 8.78 % vs 8.72-8.75 %; spectra above the 1080p Nyquist limit 0.210 % vs 0.210 %; GPU-arena data written 1504 MB native vs 1421 MB in the 4K test; fps 58.2 vs 58.7): the 4K buffers were allocated but not written at full resolution, the view RT size (table `0x2594EB7`) still decides the 3D viewport. There is no render-resolution -> swapchain scaling path in the engine.
* Menu/HUD at 720p are intact (the UI renders at the render resolution and is scaled), at 4K-like sizes the UI is always 1080p.
* Parked ideas: (a) a custom down-sampling pass (GPU code), (b) find the condition in the swapchain surface calculation that rejects other sizes for a real >1080p output (a hook experiment on `computeSurfaceInfo` and `CreateTexture2D` was designed and is not finished), (c) stay at 1080p and tune AA (the current direction). The maintainer's notes say that another modder reportedly achieved >1080p in BC mode; that is unverified here.

## 9. Fog, particles and a stable comparison environment

* **FFX/SFX layer:** the FFX scene controller (vtable `0x57B9080`, 1 instance) byte `+0x5C6` = "SFX-OFF". Setting it removes ground fog and sparkling particles (also bonfire/torch flames; their light source/glow stays). A second layer, the white **fog wall** outside the playable area, remains (`FogA/FogB`, `FogInterpRatio`, `Fog Param`, `DepthFogDensity`: strings only).
* **Effect on measurements:** with SFX on, brightness drifted 58.6 -> 54.6 and the apparent sharpness changed -23 % (static wall -33 %); with SFX-OFF over 103 s: brightness sd 0.22 %, normalised sharpness sd 0.2 % (cells 0.2-0.6 %), drift 0.00 %/10 s; foliage animation does not matter for the metric. Hence: **use SFX-OFF in every image-quality experiment** (`"fixed": [{"addr": "vt:0x57b9080+0x5C6", "fmt": "B", "val": 1}]`).
* Freezing time via the fixed time-step object (`+0x18`, `0x3C888889`) did nothing (initialisation setting). `Inner Simulation Time`/`Time Rate` debug menus belong to the sea-wave effect. A static SFX-OFF toggle (`0x26FD9F2` `00 -> 01`) was never tested.

## 10. How to run a graphics experiment properly

1. Record two or more test scenes in safe spots (no enemies nearby), same map, different content (long edges/fences for AA, grazing floors for aniso, long views for DOF/LOD). Warm-up pass before measuring ([20](20-tooling.md) section 9).
2. SFX-OFF held in `fixed`; state sequence with repeats (`A,B,A,B`) for the noise floor; `shot_delay` 2 s; `"noverify": true` for values consumed within a frame.
3. Include a **positive control** (an effect known to show: forced FXAA2 = -30 %) and a **negative control** (A vs A).
4. `analyze_ab.py --ref "<state>"`; look at `persisted after hold`; discard runs with a death or `persisted: NO`.
5. Judge by numbers **and** zoom crops (`--crop`) **and** the maintainer's eyes (blink/slider pages); report the noise floor next to every effect.
6. Reproduce it from a **cold start** before shipping.

## 11. Ideas not yet tried

| Idea | Why | First step |
|---|---|---|
| Permanent DLAA lambda/epsilon (not only threshold) | lambda 1 gave +8.2 %, epsilon 0.6 +7.4 % with different look | find the copies of `src+0x1C/+0x20` (or the matching offsets) in `0x12596F0`: `bb_ctx.py 125970f` and the instructions after `0x1259714`; extend `make_dlaa_mod.py` with one more constant per field |
| Scene-dependent AA | AA parameters come from `scene_draw_param` rows | dump rows with `list_params.py`, look for `scene_draw_param`; edit persistent rows rather than the pass |
| Distance-falloff YEBIS FXAA2 as a real option | near edges smoother than DLAA, far detail kept | a cave that calls `0xFD3270(3, 15)` once after YEBIS init, force enable at `0x25D8034`, DLAA off (`pass+8 = 1`, `pass+9 = 0`); measure with `spec_aa_falloff_scenes`-style specs |
| Working TAA | the engine has a full temporal AA implementation | find the projection matrix upload, add sub-pixel jitter, then route the TAA result into the final composite |
| Make anisotropy real | table is read at creation | find the sampler creation code (consumer of `[g+0x250]+0x360`) |
| True >1080p output | maintainer interest; others reportedly got >1080p in BC mode (unverified here) | finish the `computeSurfaceInfo`/`CreateTexture2D` diagnostic hook (log size and error code), then bisect the rejection condition |
| Animation LOD and culling flags | LOD tweaks still untested beyond LOD_BANK | toggle the debug-menu flags (`Disable Entity Culling`, ...) live: follow the registration function of each string to its flag byte |
| Fog wall and foliage wind | A/B stabilisation, visual options | trace readers of the `FogA/FogB` parameters; `FXBillboardParam`/`LightShaftMask`; wind is probably a shader time constant (`hclSimpleWindAction` is cloth only) |
| Sharpen/CAS-like post pass | HUD stays crisp while 3D is sharper | needs GPU code; out of reach without a shader patching path |
| Texture streaming after death/warps | blurry textures until an area reload; cause unknown | read the streaming manager state before/after a death (`scan_rt.py` for texture descriptors) |
| Other YEBIS post effects (bloom/glare/vignette quality) | image-quality toggles | follow the debug-menu registrations around `0x25E02B0` |
