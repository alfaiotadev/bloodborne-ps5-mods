/* Generated data for the comparison tool. Image sizes are in bytes. */
window.CMP_DATA = {
 "version": 1,
 "sets": [
  {
   "id": "aa",
   "title": "Anti-aliasing: DLAA threshold",
   "feature": "DLAA threshold 0.3",
   "default_on": false,
   "summary": "The game already runs its own DLAA anti-aliasing pass. The mod raises its edge threshold from 0.1 to 0.3, which keeps anti-aliasing on but leaves slightly more fine detail. The effect is subtle by design, so use blink mode, zoom in, or open the difference view.",
   "verdict": "Subtle but consistent: with threshold 0.3 thin geometry (fence spikes, rails, wheel spokes) is slightly crisper than with the game default. We measured +1.7 and +3.2 percent normalised sharpness in two pose-locked scenes. Plain FXAA is clearly softer. A higher threshold sharpens further but lets stair-stepping show.",
   "scenes": [
    {
     "id": "aa-fence",
     "title": "Fence and carriage",
     "kind": "crop",
     "w": 960,
     "h": 540,
     "desc": "Yharnam: wrought-iron fence, carriage and wheel.",
     "hint": "Look at the spike tips along the fence and the spokes of the carriage wheel.",
     "states": [
      {
       "id": "off",
       "label": "AA off (game AA pass disabled)",
       "short": "AA off",
       "file": "aa_fence_off.webp",
       "bytes": 114022,
       "role": "other",
       "note": "Anti-aliasing pass switched off: more stair-stepping on thin edges."
      },
      {
       "id": "game",
       "label": "Game default (DLAA, threshold 0.1)",
       "short": "Game default",
       "file": "aa_fence_game.webp",
       "bytes": 101270,
       "role": "default",
       "note": "What the game does without any mod."
      },
      {
       "id": "thr03",
       "label": "Mod: DLAA threshold 0.3",
       "short": "Mod: thr 0.3",
       "file": "aa_fence_thr03.webp",
       "bytes": 105026,
       "role": "mod",
       "note": "The mod: same DLAA pass, higher edge threshold."
      },
      {
       "id": "fxaa",
       "label": "Plain FXAA (not used by the mod)",
       "short": "Plain FXAA",
       "file": "aa_fence_fxaa.webp",
       "bytes": 81874,
       "role": "other",
       "note": "The game's simple FXAA mode: clearly softer. Shown for reference only."
      }
     ],
     "a": "game",
     "b": "thr03"
    },
    {
     "id": "aa-rails",
     "title": "Bridge balustrade and rails",
     "kind": "crop",
     "w": 960,
     "h": 540,
     "desc": "Stone bridge stairs with a balustrade and diagonal iron rails (right).",
     "hint": "Look at the diagonal rails on the right and the balustrade posts. This scene is dark, so differences are small.",
     "states": [
      {
       "id": "off",
       "label": "AA off (game AA pass disabled)",
       "short": "AA off",
       "file": "aa_bal_off.webp",
       "bytes": 62276,
       "role": "other",
       "note": "Anti-aliasing pass switched off: more stair-stepping on thin edges."
      },
      {
       "id": "game",
       "label": "Game default (DLAA, threshold 0.1)",
       "short": "Game default",
       "file": "aa_bal_game.webp",
       "bytes": 57056,
       "role": "default",
       "note": "What the game does without any mod."
      },
      {
       "id": "thr03",
       "label": "Mod: DLAA threshold 0.3",
       "short": "Mod: thr 0.3",
       "file": "aa_bal_thr03.webp",
       "bytes": 59124,
       "role": "mod",
       "note": "The mod: same DLAA pass, higher edge threshold."
      },
      {
       "id": "fxaa",
       "label": "Plain FXAA (not used by the mod)",
       "short": "Plain FXAA",
       "file": "aa_bal_fxaa.webp",
       "bytes": 45790,
       "role": "other",
       "note": "The game's simple FXAA mode: clearly softer. Shown for reference only."
      }
     ],
     "a": "game",
     "b": "thr03"
    },
    {
     "id": "aa-sweep",
     "title": "Threshold sweep",
     "kind": "crop",
     "w": 960,
     "h": 540,
     "desc": "Same fence scene captured in a separate session with four thresholds.",
     "hint": "Compare 0.1 and 1.0 on the diagonal rails: higher thresholds give harder, more stair-stepped edges.",
     "states": [
      {
       "id": "t01",
       "label": "Threshold 0.1 (game default)",
       "short": "thr 0.1",
       "file": "aa_sweep_01.webp",
       "bytes": 94428,
       "role": "default",
       "note": "Game default."
      },
      {
       "id": "t03",
       "label": "Threshold 0.3 (the mod)",
       "short": "thr 0.3",
       "file": "aa_sweep_03.webp",
       "bytes": 97578,
       "role": "mod",
       "note": "The mod."
      },
      {
       "id": "t06",
       "label": "Threshold 0.6",
       "short": "thr 0.6",
       "file": "aa_sweep_06.webp",
       "bytes": 102594,
       "role": "other",
       "note": "Sharper, more aliasing."
      },
      {
       "id": "t10",
       "label": "Threshold 1.0",
       "short": "thr 1.0",
       "file": "aa_sweep_10.webp",
       "bytes": 105788,
       "role": "other",
       "note": "Closest to no filtering of edges."
      }
     ],
     "a": "t01",
     "b": "t03"
    }
   ]
  },
  {
   "id": "dof",
   "title": "No depth of field",
   "feature": "No depth of field",
   "default_on": false,
   "summary": "The mod turns the depth-of-field blur pass off. Whether you can see it depends on how strong the game's far blur is in the scene.",
   "verdict": "Small. In the foggy Hunter's Dream garden the distant fence and foliage are slightly crisper with depth of field off. In the Yharnam plaza we could not see or measure a difference, because the game's far blur starts very far away there. The mod also removes depth of field in cutscenes.",
   "scenes": [
    {
     "id": "dof-fence",
     "title": "Distant fence, Hunter's Dream",
     "kind": "crop",
     "w": 840,
     "h": 472,
     "desc": "The garden in the Hunter's Dream with a thick fog wall behind the far fence.",
     "hint": "Look at the far fence slats and the leaf edges against the fog.",
     "states": [
      {
       "id": "on",
       "label": "Depth of field on (game default)",
       "short": "DOF on",
       "file": "dof_fence_on.webp",
       "bytes": 48068,
       "role": "default",
       "note": "Game default."
      },
      {
       "id": "off",
       "label": "Depth of field off (mod)",
       "short": "DOF off",
       "file": "dof_fence_off.webp",
       "bytes": 48174,
       "role": "mod",
       "note": "Mod enabled."
      }
     ],
     "a": "on",
     "b": "off"
    },
    {
     "id": "dof-plaza",
     "title": "Yharnam plaza (no visible difference)",
     "kind": "crop",
     "w": 960,
     "h": 540,
     "desc": "Yharnam, first bonfire plaza, enemies frozen by a cheat for the capture.",
     "hint": "Expected result: no visible difference. Try the difference view.",
     "states": [
      {
       "id": "on",
       "label": "Depth of field on (game default)",
       "short": "DOF on",
       "file": "dof_plaza_on.webp",
       "bytes": 73588,
       "role": "default",
       "note": "Game default."
      },
      {
       "id": "off",
       "label": "Depth of field off (mod)",
       "short": "DOF off",
       "file": "dof_plaza_off.webp",
       "bytes": 72856,
       "role": "mod",
       "note": "Mod enabled."
      }
     ],
     "a": "on",
     "b": "off"
    }
   ]
  },
  {
   "id": "aniso",
   "title": "Anisotropic filtering 16x",
   "feature": "Anisotropic filtering 16x",
   "default_on": false,
   "summary": "The mod sets the engine's sampler anisotropy to 16x. Anisotropic filtering matters on textures seen at a grazing angle, such as floors and stairs.",
   "verdict": "No visible difference in the scenes we tested. In our pose-locked Yharnam captures the 1x and 16x frames differed by no more than capture noise. The toggle is kept as an opt-in because it is harmless, but do not expect a visible change. If you find a scene where it matters, please open an issue.",
   "scenes": [
    {
     "id": "aniso-steps",
     "title": "Bridge steps at a grazing angle",
     "kind": "crop",
     "w": 960,
     "h": 540,
     "desc": "Stone stairs seen at a shallow angle, a typical case where anisotropic filtering should show.",
     "hint": "Expected result: no visible difference. Try blink mode and the difference view.",
     "states": [
      {
       "id": "a1",
       "label": "Anisotropy 1x (filtering off)",
       "short": "1x",
       "file": "aniso_steps_1x.webp",
       "bytes": 35210,
       "role": "other",
       "note": "Engine sampler anisotropy set to 1."
      },
      {
       "id": "a16",
       "label": "Anisotropy 16x",
       "short": "16x",
       "file": "aniso_steps_16x.webp",
       "bytes": 34826,
       "role": "mod",
       "note": "Engine sampler anisotropy set to 16."
      }
     ],
     "a": "a1",
     "b": "a16"
    }
   ]
  },
  {
   "id": "fov",
   "title": "Wide FOV",
   "feature": "Wide FOV x1.3",
   "default_on": false,
   "summary": "The mod multiplies the follow camera's field of view. The game's vertical FOV is 43 degrees; x1.3 gives about 56 degrees (about 87 degrees horizontal at 16:9), which we confirmed by measuring the screenshots. These are full frames scaled to 1280x720, not pixel crops.",
   "verdict": "A clearly visible change: more of the scene fits on screen and the character looks smaller. x1.6 (about 69 degrees) was tested and rejected as too distorted; it is not in the default cheat file. The multiplier can be changed when building the cheat file.",
   "scenes": [
    {
     "id": "fov-a",
     "title": "Bridge stairs, wide view",
     "kind": "frame",
     "w": 1280,
     "h": 720,
     "desc": "Full frame at 1280x720.",
     "hint": "Blink between the states and watch the balustrades and lamp posts move outwards.",
     "states": [
      {
       "id": "n",
       "label": "Normal (43 degrees vertical)",
       "short": "Normal",
       "file": "fov_a_normal.webp",
       "bytes": 56790,
       "role": "default",
       "note": "Game default."
      },
      {
       "id": "w13",
       "label": "Wide FOV x1.3 (about 56 degrees)",
       "short": "x1.3",
       "file": "fov_a_x13.webp",
       "bytes": 63054,
       "role": "mod",
       "note": "The mod."
      },
      {
       "id": "w16",
       "label": "Wide FOV x1.6 (about 69 degrees)",
       "short": "x1.6",
       "file": "fov_a_x16.webp",
       "bytes": 62132,
       "role": "other",
       "note": "Tested and rejected: too distorted. Not in the default file."
      }
     ],
     "a": "n",
     "b": "w13"
    },
    {
     "id": "fov-b",
     "title": "Bridge stairs, second capture",
     "kind": "frame",
     "w": 1280,
     "h": 720,
     "desc": "Full frame at 1280x720, same states, captured in a different run.",
     "hint": "Compare the size of the character and the amount of sky.",
     "states": [
      {
       "id": "n",
       "label": "Normal (43 degrees vertical)",
       "short": "Normal",
       "file": "fov_b_normal.webp",
       "bytes": 56622,
       "role": "default",
       "note": "Game default."
      },
      {
       "id": "w13",
       "label": "Wide FOV x1.3 (about 56 degrees)",
       "short": "x1.3",
       "file": "fov_b_x13.webp",
       "bytes": 62036,
       "role": "mod",
       "note": "The mod."
      },
      {
       "id": "w16",
       "label": "Wide FOV x1.6 (about 69 degrees)",
       "short": "x1.6",
       "file": "fov_b_x16.webp",
       "bytes": 64900,
       "role": "other",
       "note": "Tested and rejected: too distorted. Not in the default file."
      }
     ],
     "a": "n",
     "b": "w13"
    }
   ]
  },
  {
   "id": "cam",
   "title": "FPS head camera (experimental)",
   "feature": "FPS head camera (experimental)",
   "default_on": false,
   "summary": "A first-person camera attached to the character's head. These two frames come from an early prototype build (the camera sat inside the hood); the current version follows the head bone. See the gallery on the main page for a newer shot.",
   "verdict": "Experimental. It changes where the camera sits, not how the game plays, but it has known rough edges: see the known-issues page. Toggle the camera off and on again to reset it.",
   "scenes": [
    {
     "id": "cam-proto",
     "title": "Third person versus first person (early prototype)",
     "kind": "frame",
     "w": 1280,
     "h": 720,
     "desc": "Same spot, same moment, camera toggled. Full frames at 1280x720.",
     "hint": "Drag the slider to wipe between the normal chase camera and the head view.",
     "states": [
      {
       "id": "third",
       "label": "Normal third-person camera",
       "short": "Third person",
       "file": "cam_third.webp",
       "bytes": 63534,
       "role": "default",
       "note": "Game default."
      },
      {
       "id": "fps",
       "label": "Head camera (early prototype)",
       "short": "Head camera",
       "file": "cam_fps.webp",
       "bytes": 67848,
       "role": "mod",
       "note": "Prototype: the current build uses the head bone."
      }
     ],
     "a": "third",
     "b": "fps"
    }
   ]
  }
 ]
};
