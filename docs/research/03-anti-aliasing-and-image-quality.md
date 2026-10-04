# 03 - Anti-aliasing and image quality

What was found about the game's rendering pipeline, what was tried to improve image quality, and what
the measurements said. Positive and negative results are both recorded.

> Platform: firmware 12.40, PS5 Pro, 1080p native render, 4K output (see [01](01-platform-and-tooling.md)).
> The game's post-processing is resolution- and scene-dependent; other output modes were not tested.

## 1. Summary

| Topic | Result |
|-------|--------|
| Chromatic aberration removal | **Biggest real improvement** of the whole series (shipped, default on). Motion blur removal also shipped. |
| The game's own AA | The game already runs a post-process AA pass that is **DLAA** (`DLAA.ppo`), enabled in all four test scenes. Its parameters are copied from the scene every frame. |
| Forcing YEBIS FXAA on top | Softens the whole frame including the HUD (about -30 % sharpness). Rejected. |
| Switching the pass to FXAA / FXAA3 | Softer (-15..-31 %). FXAA3 HQ effectively does nothing in this configuration. |
| DLAA threshold sweep | Sharpness rises monotonically with the threshold; 1.0 equals "AA off". **0.3** (+1.7..3.2 %) was chosen by visual preference; shipped as an opt-in mod. |
| Temporal AA (YEBIS) | Can be enabled (the pass runs) but **has no visible effect** in this pipeline. Parked. |
| Distance-falloff FXAA2 | Works as a parameter; trades near-edge smoothing against far sharpness. Not shipped. |
| Anisotropic filtering 16x | The sampler table can be rewritten, but **no controlled test showed an effect**. An early +9 % result was fog drift. Shipped as opt-in; expect nothing. |
| mip LOD bias | Writes have no effect (even +2.0 does not blur). |
| Depth of field off | +14..41 % in the farthest cells of one scene, **no effect** in the two Yharnam scenes tested. Shipped as opt-in. |
| LOD distances x4 | Live-patchable, **no measurable sharpness effect**. Not shipped. |
| Wide FOV | Works (x1.3 -> 55.9 degrees vertical). Shipped as opt-in. |
| Supersampling / render resolution above 1080p | **Failed.** Only 720p, 900p and 1080p start; a "working" 4K-to-1080p variant was a measurement error: no supersampling happens. |

## 2. Measurement method

All quantitative claims rely on one method, developed to get below the noise floor of a game that
animates fog, foliage, particles and the camera constantly. The tooling is described in
[04](04-scene-automation-and-measurement.md); this section defines the numbers.

### Capture

- Screenshots taken by the console's own function (3840x2160 JPEG XR). The 4K image is an upscale of
  the native 1080p render: the spectral energy above the 1080p Nyquist limit is identical in a
  native-1080p and a "4K" capture (0.210 % vs 0.210 %), so there is no extra information in the 4K
  pixels.
- Decoded with `imagecodecs.jpegxr_decode`, converted to luma and **reduced 2x2** (box) to a
  1080p-equivalent image.
- The original JXR (about 0.5 MB) is kept as the archive; lossless PNG/WebP only for viewing.

### Metrics

| Metric | Definition |
|--------|------------|
| **Normalised sharpness** | `mean( abs(Laplacian(L)) / (GaussianBlur(L, sigma = 6) + 8) )` over the interior, where the Laplacian is the 4-neighbour kernel on 1080p-equivalent luma. The blur term normalises local brightness, so exposure drift and eye adaptation do not masquerade as sharpness. |
| **Ground sharpness** | The same value over the lower 40 % of the frame (floor, grazing angles, far ground). |
| **mean abs diff** | Mean absolute luma difference between two shots (0-255 scale) |
| **Shift** | Phase-correlation translation between two shots; `(0, 0)` px means identical framing. |
| **Cells** | The frame is split into a grid; per-cell ratios show *where* an effect appears. |
| **Edge stair-step** | Laplacian / gradient magnitude on strong edges, and the fraction of strong-edge pixels (used for AA, where "sharper" is not "better"). |

A raw (un-normalised) Laplacian was misleading: dark areas are weighted differently when the image
brightness drifts. The first anisotropy result read +4 % raw and +9.2 % normalised (see "Anisotropic filtering" in
section 5 for why even that was wrong).

### Controls and noise floors

- **Fixed view.** Camera pose and player position are locked ([04](04-scene-automation-and-measurement.md)),
  so shots align pixel for pixel (shift `(0, 0)`).
- **ABAB ordering.** States alternate A, B, A, B inside one run. Two shots of the *same* state give
  the noise floor; a linear drift term can be fitted out.
- **Warm-up pass.** Visit every scene once before measuring so texture streaming is in a repeatable
  state (04).
- **Same visit.** Only compare shots from the same run, never across game sessions.
- **Stabilised environment.** Switching off the engine's FFX/SFX effect layer (ground fog, shimmering
  particles, flames) removes most drift; see 04.
- **Positive control.** An effect known to be real (forced FXAA, -30 %) is run through the same
  pipeline to prove that "no effect" results are real.
- **Reject runs with a death or enemy interference.** A death breaks texture streaming and moves
  heap objects (04).

Typical noise floors obtained:

| Condition | Noise |
|-----------|-------|
| Static scene, cold, no warm-up, fog on | sharpness +-4..8 %, mean abs diff 1-5; brightness drifted 58.6 to 54.6 over a run |
| After warm-up | sharpness spread 0.2..5 % (-2.8 / +5.2 / +4.3 / +0.2 against -8 / +14.6 / +0.6 / -0.6 without) |
| Fog layer off, 7 shots over 103 s | brightness sd 0.22 %, sharpness sd 0.2 % (0.2-0.6 % per region), drift 0.00 % per 10 s |
| AA mode series (fog off, pose-locked) | sharpness sd 0.05 %, mean abs diff 0.5-0.9 |
| Yharnam DOF/LOD tests | 0.0-0.1 % |

With the stabilised environment a 1-2 % effect is detectable with one shot per state.

### What the metric cannot say

Sharpness is not quality. A noisier or more aliased image scores higher. For AA the numbers must be
read together with zoomed crops and blink comparisons; the choice of 0.3 for the DLAA threshold is a
visual preference, not an optimum of any metric.

## 3. Discovery: the game's own AA pass is already DLAA

### Timeline of the misunderstanding

1. Early on, the post-process stage was found to toggle YEBIS's built-in FXAA (`SetAntialiasEnable`)
   from a scene parameter. In the starting scene the parameter was 0 (debug probe `FX:0`).
2. Forcing it to 1 (patch at `0x25D8034`, `0F 95 C0` -> `B0 01 90`, i.e. `setne al` -> `mov al,1; nop`)
   visibly smoothed edges, which looked like "no AA versus AA".
3. Static analysis of the debug-menu registration at `0x25E02B0` revealed a **separate, game-side AA
   render pass**, and live inspection showed that it was already running **DLAA** in every test scene.
   The "forced FXAA" experiment had therefore been **YEBIS FXAA2 on top of DLAA** (hence the -30 %
   sharpness), not "AA versus no AA".

### The game-side AA pass (confirmed live and by disassembly)

| Item | Value |
|------|-------|
| Vtable | `0x56E7980` |
| Constructor / execute | `0x1258940` / `0x1258D30` |
| Parameter copy per frame | `0x12596F0(this, src)` |
| Debug-menu registration | `0x1259730` |
| Shader selection setup | `0x1258C50`; shader name table `0x56E79A0` |
| Location | Part of the scene object at `scene+0x1BC8` |
| Instances | Four exist; only the one belonging to the active scene has `Enable = 1` (found by vtable scan) |

| Field | Offset | Type | Meaning |
|-------|--------|------|---------|
| IgnoreParamFromOutside | `+0x08` | bool | `0`: copy the scene's parameters every frame; `1`: keep the pass's own values |
| Enable | `+0x09` | bool | pass enabled |
| mode | `+0x0C` | i32 | `0` FXAA.ppo, `1` FXAA3.ppo, `2` FXAA3HQ.ppo, `3` DLAA.ppo |
| Fxaa alpha / reduceMin / reduceMul / spanMax | `+0x10`..`+0x1C` | 4 x f32 | defaults 1, 1/128, 1/8, 8 |
| DLAA threshold | `+0x28` | f32 | default 0.1 |
| DLAA lambda ("Ramda") | `+0x2C` | f32 | default 2.0 in the struct; **2.44 observed live** in all test scenes |
| DLAA epsilon | `+0x30` | f32 | 0.25 |

How the scene drives it (`0x12596F0`): if `[this+8] == 0` the function copies, every frame,
`Enable = src[0] != 0`, `mode = src[1] - 1` (scene `AntiAliasType` 0 = YEBIS's internal FXAA2, 1..4 =
FXAA, FXAA3, FXAA3_HQ, DLAA_GS) and the parameters; if `[this+8] == 1` the pass keeps its local
values. The scene parameters come from interpolating two `scene_draw_param` rows (`0x126C5D0`); the
row is chosen by `scene_draw_param_antialias_id`. The threshold copy is `vmovss xmm0,[rsi+0x18]` at
`0x125970F`, stored to `[rdi+0x28]` (see "Choosing a default" in section 4).

Live reading in the four test scenes: the active pass had `Enable = 1`, `mode = 3` (DLAA), threshold
0.1, lambda 2.44, epsilon 0.25; the other three instances had `Enable = 0`. YEBIS's own FXAA2
(`[scene block + 0x220]`) was off.

The name "DLAA" here is almost certainly the classic post-process *directionally localised
anti-aliasing* (a threshold / lambda / epsilon edge-directed blur), **not** NVIDIA's DLSS-based
"DLAA" (inferred from the parameter set; the shader source is not available).

### YEBIS context (engine post-effect library)

The post-effect library is YEBIS; its context is reached through a global pointer (`0x5865ED0`,
confirmed by the debug probe and several live specs; two notes wrote `0x58C5ED0`, a typo).

| Field / function | Address / offset | Notes |
|------------------|------------------|-------|
| `SetAntialiasEnable` wrapper -> setter | `0xFB37F0` -> `0xFD31F0` | writes `[ctx+0xBBC]`; getter `0xFB3810` |
| AA falloff distance setter | `0xFD3270` | `[ctx+0xBC0]` near, `[ctx+0xBC4]` far (metres); dirty flag `[ctx+0x6D5] = 1` (consumed immediately) |
| Camera near/far planes | `[ctx+0x57C]` / `[ctx+0x580]` | 0.05 / 3000 |
| Init flags | `ctx+0x130`.. | `+0x145` ANTIALIAS_TEMPORAL, `+0x14F` ANTIALIAS, `+0x150` ANTIALIAS_DISTANCEFALLOFF, `+0x147` GAUSSIANBLUR |
| Temporal AA enable | `[ctx+0xB8C]` | 0 by default; the game never calls `SetTemporalAntialiasEnable` (`0xFD2CB0`) |
| Temporal AA parameters | `+0xB98` weight (0.05), `+0xB9C` (0), `+0xBA0` / `+0xBA4` (0.1), `+0xBA8` (0.001); setter `0xFD2D20`; state `+0xB90` = 2 | |
| Temporal AA active flag | `[ctx+0xC99]` | recomputed every frame (`0xFDD440`, `0xFE0553`: enable and `[ctx+0x6F6] == 0`); apply function `0xFE7580` starts with `cmp [ctx+0xC99],0` |
| Depth of field | `SetDepthOfFieldEnable` `0xFB2960`, custom DOF `0xFB3600` | see section 5 |

The scene parameter block that YEBIS reads is a **static** structure at `0x59406E0` (not a pointer),
rewritten from the scene every frame: YEBIS AA enable is `[0x59406E0+0x220]` (consumer at `0x25D802C`,
`cmp [r15+0x220],0 ; setne al ; call SetAntialiasEnable`), the type is `+0x224`, the FXAA parameters
`+0x228`..`+0x234`. The YEBIS-side debug registration (`0x25E02B0`) lists the AA parameter struct:
`+0x68` Enable, `+0x6C` AntiAliasType (5-valued enum), `+0x70`..`+0x7C` Fxaa alpha/reduceMin/reduceMul/spanMax,
then DLAA Threshold, `+0x84` Ramda, Epsilon.

## 4. AA experiments and results

All sharpness numbers are relative to the game's own DLAA (threshold 0.1) in the same scene, from
the AA-mode series (three scenes, 11 states each, pose-locked, fog layer off, noise: sharpness sd
0.05 %, mean abs diff 0.5-0.9). Scenes: **S1** long fences in the sickroom (flat light), **S2** bonfire
horizon with ladders (distance), **S3** bridge cobblestone at a shallow angle.

| State (written live to all four pass instances) | S1 | S2 | S3 | Comment |
|-------|----|----|----|---------|
| Pass disabled (AA off) | +10.4 % | +4.8 % | +4.4 % | Sharper, visibly aliased |
| Pass `mode = 0` (FXAA) | -30.7 % | -31.0 % | -29.0 % | Very soft |
| Pass `mode = 1` (FXAA3) | -23.2 % | -20.4 % | -14.9 % | Soft; ranked worst in blink tests |
| Pass `mode = 2` (FXAA3 HQ) | +10.8 % | +5.7 % | +7.5 % | In zoom as jagged as "AA off": effectively does nothing in this configuration |
| `IgnoreParam = 1`, `mode = 3`, game's own values | -0.1 % | -0.3 % | -0.2 % | Proves the bypass path is clean |
| DLAA lambda 4 | -7.2 % | -6.7 % | -4.2 % | Softer |
| DLAA lambda 1 | +8.2 % | +4.2 % | +3.5 % | Sharper |
| DLAA threshold 0.05 | -1.8 % | -1.0 % | -1.0 % | |
| DLAA threshold 0.3 | +3.2 % | +1.7 % | +1.9 % | The chosen default |

Method notes: the `vtall:` write format writes one value to **all** instances, because only the
scene's active instance matters and which one is active changes with the scene. Heap addresses
change every run, so a permanent change needs a code hook ("Choosing a default" in section 4).

### YEBIS FXAA2 on top, and distance falloff

YEBIS's FXAA2 can be restricted by distance (`PFXINIT_ANTIALIAS_DISTANCEFALLOFF`,
`SetAntialiasFalloffDistance(near, far)`). Forced with the `0x25D8034` patch, with the game's DLAA
switched off for comparison, sharpness against the game's DLAA (S1 / S3; S2's textures had not
streamed in during that run and was discarded):

| State | S1 | S3 | Comment |
|-------|----|----|---------|
| FXAA2 plain (DLAA off) | -30.6 % | -29.0 % | |
| Falloff 3-15 m | **-2.7 %** | **-12.0 %** | Ground -14 / -17 %; close to DLAA |
| Falloff 10-60 m | -22.1 % | -26.4 % | Close to plain FXAA2 |
| Falloff 30-300 m | -29.5 % | -28.3 % | = plain |
| DLAA + FXAA2 falloff 10-60 m | -25.9 % | -27.5 % | |

Smaller `far` makes the AA fade earlier and keeps distant sharpness. In a close-up crop FXAA2
smooths near-field stair-steps clearly better than DLAA; falloff 3-15 is between the two. Not
shipped and not pursued further once the DLAA threshold sweep gave a simpler route (no extra pass
on top of DLAA, no per-frame writes needed).

### Forced YEBIS FXAA2 on top of DLAA (Yharnam, bonfire scene)

Fog layer off, noise 0.1 %: fine-detail metric **-33 %** (0.2329 to 0.1554), edge stair-step
**-28 %** (1.706 to 1.227), strong-edge pixel share 10.3 % to 6.2 %. Wheelchair surfaces and an iron
fence look smoother, but **the whole frame softens, including the HUD** (numbers, icons, text). The
positive control in the scene automation gave -33.1 % (fences) and -30.0 % (bridge) in an
independent run. Decision: do not ship.

### Temporal anti-aliasing: enable does not reach the screen

- The game never requests temporal AA; the init-flag bit 20 for it is not set. Two single-byte writes
  at `0x25D32AB` and `0x25D32B5` (values recorded as `12` and `16`; the notes do not say hex or
  decimal) initialise the machinery, and writing `[ctx+0xB8C] = 1` turns it on.
- With enable = 1, `[ctx+0xC99]` became 1 (the pass runs). Three scenes in ABAB order: sharpness
  -0.2..-0.6 %, mean abs diff = noise level, no difference even in the moving tiles of the character.
- Weights `[ctx+0xB98]` 0.02 / 0.05 / 0.3 / 0.6: no difference.
- A working TAA would need (a) per-frame sub-pixel projection jitter and (b) the pass's result routed
  into the final image. That is a large, risky project; parked. The TAA init patch is not in the
  release.

### Choosing a default: the DLAA threshold sweep

Sharpness against the game's DLAA (threshold 0.1), S1 (fences) / S3 (bridge). The third scene
(under the bridge) was discarded because an enemy killed the player during that run (04).

| Setting | S1 | S3 |
|---------|----|----|
| threshold 0.2 | +2.0 % | +0.8 % |
| **threshold 0.3** | **+3.2 %** | **+1.7 %** |
| threshold 0.45 | +5.6 % | +3.2 % |
| threshold 0.6 | +8.1 % | +4.2 % |
| threshold 0.8 | +9.7 % | +4.6 % |
| threshold 1.0 | +10.4 % | +4.7 % (= AA-off level) |
| 0.3 + lambda 1.5 | +6.3 % | +3.1 % |
| 0.3 + lambda 3.5 | +1.2 % | +1.1 % |
| 0.3 + epsilon 0.1 | +0.5 % | +0.9 % |
| 0.3 + epsilon 0.6 | +7.4 % | +3.4 % |

Sharpness grows monotonically with the threshold: a higher threshold makes the filter skip more
edges, until it equals "AA off". In the maintainer's blink comparisons the favourite was
**threshold 0.3**; FXAA and FXAA3 were the least liked. 0.3 therefore is a **visual-preference
compromise** (still anti-aliased, measurably crisper), not an optimum. It ships as the opt-in mod
"DLAA threshold 0.3 (sharper anti-aliasing)".

Implementation (`tools/mods/make_dlaa_mod.py`): the threshold copy at `0x125970F`
(`C5 FA 10 46 18`, `vmovss xmm0,[rsi+0x18]`) is hooked with a 5-byte `jmp` to a 13-byte cave at
`0x54A1300` which loads a constant from `0x54A1340` and jumps back to `0x1259714`. Heap objects
move every run, so only a code patch can make this permanent. Details and bytes in
[02](02-code-caves-and-hooks.md#3-anatomy-of-a-hook). (One lab note gives the threshold copy
address as `0x1259714`; the generator, `0x125970F`, is authoritative.)

## 5. Texture filtering

### Anisotropic filtering

**Where the settings live** (confirmed by reading live memory): `[[0x59406C8]+0x250]+0x360` is a
table of 19 sampler descriptors, 0x38 bytes each: `+0` `mipLODBias` (f32), `+4` `MaxAnisotropy` (i32).
Aniso samplers (indices 8-15 and 17, the latter the GI map) had `MaxAnisotropy = 4`, bias 0;
index 16 (DisplacementMap) and the ShadowMap had 0. A global override pair `Aniso Debug`
(`0x5AA6C25`) + `MaxAnisotropy` (`0x553AC88`) exists in the debug menu; the loop over the table in
code (stride `0x38`, bound `0x98`) is only in the debug-menu code.

**Test history:**

| Test | Result |
|------|--------|
| Hunter's Dream, 4x -> 16x live (steps/pavement, fog on) | Raw Laplacian +4 %; normalised **+9.2 %**, distant stairs +18.9 %, path +11.7 %, perpendicular wall -1.7 %: apparently only oblique surfaces benefit. File size +3 %. Almost invisible by eye. |
| mip LOD bias 0 -> -0.75 | -2.3 % whole frame, regions -17..+7 %, drift larger than the effect: nothing |
| mip LOD bias 0 -> +2.0 (should blur visibly) | 0.914 (noise +-10 %), HUD (unaffected by the table) 0.90; crops identical: **the bias field has no effect** |
| Yharnam corridor, 4x -> 16x (hook installed) | 0.999, cells +-1 %, noise 0.1 %: nothing |
| Yharnam corridor, 16x vs **1x** | 1.001, all cells 0.99-1.02: even *disabling* anisotropy changes nothing |
| Bridge, steepest angle, 16x vs 1x | 1.000, cells +-1-2 % |
| Automated scenes (bridge / under bridge), 16x vs 1x | +0.1 % / -0.1 % (noise <= 0.2 %) |

**Conclusion:** writing the sampler table after initialisation does **not** change the rendering; the
early Hunter's Dream gain was fog/drift noise (far regions have the most fog), measured before the
fog-off stabilisation existed. Hypotheses (unproven): the samplers are created from other data at
initialisation; the table is read only by the debug menu. A per-frame hook exists and works
technically (section 6 of [02](02-code-caves-and-hooks.md)), but is useless. It ships as the
opt-in "Anisotropic filtering 16x" for completeness; **do not expect a visible change**. One lab
note called the hook variant "the one that has an effect"; that statement is not supported by the
later controlled tests.

### Depth of field

**Parameters** (scene block `0x59406E0`, rewritten every frame; a one-frame write was visible as a
horizon "flicker" of the far blur resetting, proving the fields are right): `+0x1AC` DOF enable,
`+0x1B0` FocusDistance (1), `+0x1B4` ApertureF (5.6), `+0x1C0` CCD (43.27), `+0x2D0` CustomDof,
`+0x2D4` / `+0x2D8` near/far custom (1), `+0x2EC` far blur start, `+0x2F0` full blur distance,
`+0x2F4` CocSize, `+0x2F8` CocScale.

| Scene | far start | far full | CocSize | CocScale |
|-------|-----------|----------|---------|----------|
| Hunter's Dream | 10 m | 50 m | 0.3 | 0.016 |
| Yharnam (first area) | 100 m | 150 m | 0.05 | 0.098 |

**Consumers:** `0x25D7A84 cmp [rbx+0x1AC],0` / `0x25D7A8B setne al` / `call 0xFB2960`
(`SetDepthOfFieldEnable`); `0x25D7CA7 cmp [0x59406E0+0x2D0],0 ; setne ; call 0xFB3600` (custom DOF).
The patch changes `0F 95 C0` to `31 C0 90` (pass "false" every frame), which also removes DOF in
cutscenes.

**Results:**

| Scene | Result |
|-------|--------|
| Hunter's Dream (fog layer off, 4 shots) | Whole frame +0.4 % (noise); farthest cells (fence, trees) **+14..+41 %**; rest +-1 % |
| Yharnam, top of the first lamp's ladder, long view | whole frame 1.000, cells +-1 % (one +5 %); brightness noise 0.1 % |
| Yharnam bonfire (enemies frozen) | 1.001, cells +-2 %, pixel difference 0.57 |

The effect is **scene specific** and mild in most gameplay areas, so "no DOF" is not a general
distance-sharpness improvement. It ships as opt-in. *Pitfall:* the first live test crashed the game
because the three-byte patch was written as three separate writes ([02](02-code-caves-and-hooks.md#9-other-crash-stories-platform-level)).

### LOD

`LodBankMan` is an FD4 singleton at `0x59402D8`; the chain `[[[obj+0x68]+0x70]+0x70]` leads to the
parameter blob `LOD_BANK` (64 rows, ids 0-63; row table at blob+`0x40`, 24 bytes per entry
`{u32 id, u32 pad, u64 dataOffset, u64 nameOffset}`; each row is 20 bytes
`{f32 A, f32 B, f32 C, f32 D, u32 E}`). `common_parts_lod_param_id` indexes the rows. A and C are
distances in metres: typically A = 5, C = 20; rows 0-7: 15/30, 40/1000, 15/1000, 1000/2000;
rows 19 and 63: 9998/9999 (never switches); row 15: 30/100. Interpretation (inferred): **A =
LOD0 -> LOD1 switch distance, C = LOD1 -> LOD2**.

Test: A and C multiplied by 4 (rows below 900 m, 60 rows, atomic row writes), Yharnam bonfire,
enemies frozen, fog layer off: sharpness **1.001**, cells +-1 %, noise 0.1 %, i.e. **nothing
measurable**. The only visible change: the metal highlight on a distant gate frame got wider and
brighter, which the maintainer attributed to the door frames' material/specular appearing at a
higher LOD. The parameter write works live (the rows are persistent data), but raising distances
does not add image sharpness. Not shipped.

Other LOD candidates seen only as strings (not investigated): `CSLod` (`0x4D350BC`, assert/tag use
only), `LodBankMan` / `LOD_BANK` (`0x2142B20`, `0x231129D`), Havok animation LOD (`numBonesPerLod`,
`numTracksInLod`, `currentLod`), physics `hknpLodShape`, culling menus `Disable Entity Culling`
(`0x26B8841`), `Enable Primitive Culling` (`0x26B8DDE`), `Prim Culling Model Count` (`0x26B8E19`),
`Lod%d` (`0x2646DD2`), `NearFade/FarFade Start/Range[m]` (`0x260BCC9`, `0x260BD7F`), `Far Fade
Start/Dist` (`0x2667E9A`, `0x266E5E8`, `0x26CD551`), shadow fade distances. `LodLevel`
(`0x25C7010`) is only a statistics view; `<LodLvBias`/`<LodLvDisp` exist as text (`0x4DAD522`) with
no code reference found.

## 6. Field of view

The follow camera stores its FOV in the parameter table `LOCK_CAM_PARAM_ST` (72 rows x 32 bytes at
`SoloParamRepository + 0x9C0`; `SoloParamRepository` = `0x5940340`). A row is
`f0` camera distance (4.0; bosses 3.7-6.2), `f1` pitch (-40), `f2` 0.45, `f3` 1.42 (height?),
`f4` 22, **`f5` (`+0x14`) FOV in degrees (43; a few 48)**, `f6/f7` ints (9/5 or -1). The update
function `0x183AC60` eases `CamDist` and `FovY` towards the row values (`FovY += ([row+0x14]*k - FovY)*blend`),
so editing the camera object directly does not stick; editing the rows does.

**The code clamps FOV to 38..48 degrees** (`0x183AF2B`..`0x183AF4E`: below 38 becomes 38 = 0.6632 rad,
above 48 becomes 48). A "60 degrees" test was therefore clipped to 48. The fix is not to edit the
rows but to scale the degrees-to-radians multiplication that happens after the clamp:
`vmulss xmm1,xmm1,[0x4D25E58]` (pi/180) at `0x183AF56`; the operand displacement at `0x183AF5A` is
redirected to a cave constant `pi/180 x scale` at `0x54A0500`
([02](02-code-caves-and-hooks.md#constant-redirect-fov)).

Measured by image registration (camera and player locked, fog layer off):

| Scale | Expected vertical FOV | Measured | Horizontal at 16:9 |
|-------|----------------------|----------|--------------------|
| 1.0 (control) | 43.0 | 43.0 | about 70 |
| 1.2 | 51.6 | - | about 82 |
| 1.3 | 55.9 | 55.7-56.1 | about 87 |
| 1.6 | 68.8 | 68.8 | - |

x1.6 was judged unpleasant ("psychedelic") on the console; **1.2-1.3 is the recommendation**, 1.3
the generator default. Confirmed after a cold start: the constant and the redirected displacement
are in place and the camera's `FovY` is 0.9756 rad = 55.9 degrees. Distance scaling (x2 on every row
works: the camera is clearly farther away) was also demonstrated; a code hook for a permanent
distance multiplier (the `CamDist` load at `0x183AE68`) was identified but not shipped.

## 7. Chromatic aberration and motion blur

Removing chromatic aberration (`0x269FAA8`: a 12-byte load/store pair that copies a value into
`[rbx+0xAC]` is replaced by a store of zero; the field's meaning follows from the mod's behaviour,
not from named symbols) was the **largest real image-quality improvement** found. Motion blur is
disabled by turning a conditional jump unconditional (`0x26A057B`, `74 16` -> `EB 16`). Both
come from the community patch collection, are default-on in the release, and have no side effects
that were observed.

## 8. Resolution and supersampling (failed)

The goal was to render above 1080p and downsample. It **did not work**; this section is a map of
why.

### Facts established

| Fact | Address / value |
|------|-----------------|
| Difference between Lance McDonald's 720p and 1080p patcher builds ([credits](../../CREDITS.md)) | exactly one write: the resolution constants at `0x55289F8` / `0x55289FC` (1280x720); two "pinned 1080p" blocks (`0x1A44C55`, `0x1A452C7`) are present in both |
| Output buffers are hard-coded 1920x1080 | `sceVideoOutSetBufferAttribute` at `0x15E48E9`: pixel format `0x80000000`, 1920, 1080, pitch 1920, two buffers registered; swapchain `0x15E4620`. The game renders at R and scales to the 1080p buffer itself |
| Resolution globals are written, not just read | init `0x2417770` reads the properties `SPRJ.WIN64.frameBufferW/H` (default = globals) and writes the globals back; setters `0x2417700`, `0x219E850`, `0x241A2F0` |
| Derived UI scale | `0x59404D0 = W/1920.0`, `0x59404D4 = H/1080.0`, int copies `0x59404D8/DC`; users `0x1C16A50`, `0x1C17690`, `0x1C179C0` |
| HUD | Scaleform; viewport set at `0x2358554` (`SetViewport`, vtable `+0x68`); pixel units are 1080p space; sun/light screen positions (`0x1A44C55` / `0x1A452C7` producers) use the same space |
| Hard-coded 1920x1080 pairs that remain | `0x21166D6` (`movabs 0x438_00000780`), divisors in rodata from `0x4D29338` |

### Outcomes

- **Control:** 1280x720 starts and the HUD and menus are intact: the pipeline reproduces the
  community 720p patch.
- **Larger sizes crash**: 2048x1152 and 2560x1440 crashed every time (also with a minimal base: only
  60 FPS and the resolution), about 1.2 s after start, identical fault: `SIGSEGV` at `0x259F874`,
  fault address `0x44`, backtrace `0x2697B7A <- 0x219706A <- 0x219A57A` (SprjGraphics init). The
  main-buffer render-target object (`[0x59406C8]+0x90 -> entry 0 -> +0x68`) has a NULL texture at
  `+0x40`: texture creation (`Texture::Create 0x259F130 -> CreateTexture2D 0x2565F90 -> 0x2571D60`,
  surface size `0x2FA6AF0`, allocator vtable `+0x58`, error 8/9) fails when R > 1080p.
- **Not out of memory:** only about 700 MB of the 3325 MB GPU arena were in use.
- **Matrix of sizes** (minimal base):

  | Started | Crashed (same fault) |
  |---------|---------------------|
  | 1280x720, 1600x900, 1920x1080 | 960x540, 1440x810, 1760x1088, 1792x1080, 1888x1062, 1904x1071, 1904x1072, 1920x720, 1920x1088, 1936x1089, 1952x1098, 2048x960, 2048x1080, 2048x1152, 2240x1260, 2560x1440, 2880x1620, 1280x1080 |

  Not a memory limit (some crashing sizes are smaller than 1080p), not a display limit, not "16:9
  only" (960x540 and 1440x810 crash). There is no resolution table in the binary. An earlier "21:9
  works" observation was a patch that landed *after* graphics creation (the picture was anchored in
  the top-left corner and the excess was cropped): any size "starts" if the buffers stay 1080p.
- **Patch timing is a race.** The game reads the properties (`0x2417770`) and then creates the
  graphics objects (SprjGraphics copies W/H at `+0xF0/+0xF4`). The patch landed before the first, between the two, or after
  the second on different runs (evidence: a debug probe row `RES 1280x720 / UI 1920x1080 / GX
  1280x720`). The generator therefore also writes the UI copies and scale, so the first step no
  longer matters.
- **Cause of the >1080p crash:** the display *swapchain* (`0x2AD5E90`) is created with the same W x H
  as the render, and its surface computation (`computeSurfaceInfo`, tile mode 14) **rejects every
  size except 720p, 900p and 1080p** (error 5 -> no swapchain -> NULL main-buffer texture -> crash).

### The "working" variant that was not

Decoupling swapchain and view render target from the render resolution made the game start at
R = 1440p..2160p with R in the globals: swapchain size fixed to 1920x1080 at `0x2594AA6` /
`0x2594ABD` (`mov ecx,[table]` -> `mov ecx,imm32 ; nop3`), view render target size at `0x2594EB7` /
`0x2594EC2` (same shape), and the Scaleform viewport at `0x2358554` (18 bytes -> `mov eax,1920 ; nop4 ;
mov ecx,1080 ; nop4`; without it the HUD was 1.33x too big). Main menu, HUD, inventory and Hunter's
Dream looked fine at 59.5 fps and unchanged memory (5070 MB), and a slider comparison suggested softer
edges with increasing R.

**This was retracted the next day.** Careful comparison showed native 1080p and "4K -> 1080p" are
equal in sharpness (hard one-pixel steps 8.78 % vs 8.72-8.75 %; differences only in clouds, plants,
the character and particles). The GPU arena had 1504 MB written at native 1080p vs 1421 MB in the
4K test; fps 58.2 vs 58.7: the 4K buffers were **allocated but not rendered at full resolution**.
The 3D viewport/size comes from the view render target (table at `0x2594EB7`...), which the patch
pinned to 1080p; the resolution global R only changes some render-target allocations, and the
engine has no path that renders at R and scales to the swapchain (making R smaller than the
swapchain just copies 1:1 into the top-left corner). The main-menu text was pixel-identical to native
because the UI always draws at 1080p.

Remaining options noted: (a) a custom downsample pass (GPU code), (b) understand the swapchain
surface-computation condition for a real >1080p output, (c) stay at native 1080p and improve AA and
LOD instead. The project took (c).

## 9. Open questions

- Where the game's real sampler objects are created (the writable descriptor table has no effect).
- A working temporal AA needs camera jitter and routing of the history pass's output.
- Whether a true downsample pass can be injected.
- Per-scene far depth-of-field and fade distances in the large outdoor areas.
- Effects on a base PS5 (everything here is PS5 Pro, firmware 12.40).
