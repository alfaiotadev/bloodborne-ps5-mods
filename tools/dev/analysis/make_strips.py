#!/usr/bin/env python3
"""Full-frame strip comparison: one scene, N states -> ONE image where the frame is cut into N vertical strips (or horizontal bands), each strip from a different state.
The camera is pose-locked, so the strips join seamlessly; every strip spans the whole depth range (near ground to far horizon).
Usage (needs numpy, pillow, imagecodecs):
  make_strips.py <collect_shots dir> <scene> "<state 1>" "<state 2>" ... [--out base] [--bands] [--pick first|last] [--no-label]
Writes <out>_4k.png (full 3840x2160) and <out>_1080p.png.  Labels (state name) sit at the top of each strip; thin separators between strips."""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imagecodecs
a, skip = [], False
for x in sys.argv[1:]:                                    # positional args: skip options and the values of --out / --pick
    if skip: skip = False; continue
    if x in ("--out", "--pick"): skip = True; continue
    if not x.startswith("--"): a.append(x)
opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
d, scene, states = a[0], a[1], a[2:]
out = opt("--out") or os.path.join(d, "strips_%s" % scene); pick = opt("--pick") or "first"; bands = "--bands" in sys.argv
man = json.load(open(os.path.join(d, "manifest.json")))
imgs = []
for st in states:
    cands = [x for x in man if x["scene"] == scene and x["state"] == st]
    assert cands, "no photo for scene=%s state=%r (have: %s)" % (scene, st, sorted({x["state"] for x in man if x["scene"] == scene}))
    x = cands[0] if pick == "first" else cands[-1]
    imgs.append(imagecodecs.jpegxr_decode(open(os.path.join(d, x["file"] + ".jxr"), "rb").read())[..., :3])
H, W = imgs[0].shape[:2]; n = len(imgs); canvas = np.zeros_like(imgs[0])
edges = [round(i * (H if bands else W) / n) for i in range(n + 1)]
for i, im in enumerate(imgs):
    if bands: canvas[edges[i]:edges[i + 1]] = im[edges[i]:edges[i + 1]]
    else: canvas[:, edges[i]:edges[i + 1]] = im[:, edges[i]:edges[i + 1]]
img = Image.fromarray(canvas); dr = ImageDraw.Draw(img)
try: font = ImageFont.load_default(size=44)
except TypeError: font = ImageFont.load_default()
for i in range(1, n):                                                     # separators
    if bands: dr.rectangle([0, edges[i] - 1, W, edges[i] + 1], fill=(255, 255, 255))
    else: dr.rectangle([edges[i] - 1, 0, edges[i] + 1, H], fill=(255, 255, 255))
if "--no-label" not in sys.argv:
    for i, st in enumerate(states):
        x, y = (14, edges[i] + 12) if bands else (edges[i] + 14, 14)
        tb = dr.textbbox((x, y), st, font=font); dr.rectangle([tb[0] - 8, tb[1] - 6, tb[2] + 8, tb[3] + 6], fill=(0, 0, 0)); dr.text((x, y), st, fill=(255, 255, 0), font=font)
img.save(out + "_4k.png"); img.resize((W // 2, H // 2), Image.LANCZOS).save(out + "_1080p.png"); print("wrote", out + "_4k.png", "and _1080p.png", img.size)
