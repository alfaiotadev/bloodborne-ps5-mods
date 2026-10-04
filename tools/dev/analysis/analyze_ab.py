#!/usr/bin/env python3
"""Analyse a collect_shots.py output dir (manifest.json + .jxr): per scene and state, sharpness metrics and A/B differences with noise floors.
Usage (needs numpy, pillow, imagecodecs):  analyze_ab.py <dir> [--png] [--collage]
For every scene the states are compared pairwise; repeated shots of one state (ABAB) give the noise floor (same state, different time).
Metrics on 1080p-equivalent luma (2x2 reduce of the 4K capture): sharp = mean |Laplacian| / (blur sigma 6 + 8) over the whole frame and over the lower 40 % (ground / grazing
angles), mean|d| = mean absolute luma difference, shift = phase-correlation translation (0,0 = same framing).  --png writes the decoded PNGs, --collage <scene>_collage.png.
--ref "<state>"  compact table instead of all pairs: every state vs the reference state (mean of its shots); a state that occurs twice also gives the noise floor.
--crop x0,y0,x1,y1  (1080p-equivalent pixel box) writes crop_<scene>.png: the box of every state in order, 4x nearest-neighbour zoom, 3 per row (visual AA judgement)."""
import json, os, sys, itertools
import numpy as np
from PIL import Image, ImageFilter
import imagecodecs
from numpy.fft import fft2, ifft2
d = sys.argv[1]; man = json.load(open(os.path.join(d, "manifest.json")))
luma = lambda a: np.asarray(Image.fromarray(a).convert("L").reduce(2), dtype=np.float32)
def sharp(l):
    lap = np.abs(4 * l[1:-1, 1:-1] - l[:-2, 1:-1] - l[2:, 1:-1] - l[1:-1, :-2] - l[1:-1, 2:])
    bl = np.asarray(Image.fromarray(np.clip(l, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), dtype=np.float32)[1:-1, 1:-1]
    return lap / (bl + 8)
def shift(a, b):
    A, B = fft2(a - a.mean()), fft2(b - b.mean()); R = A * np.conj(B); R /= np.abs(R) + 1e-9; r = np.real(ifft2(R)); i = np.unravel_index(np.argmax(r), r.shape); h, w = r.shape
    return (int(i[0] if i[0] < h // 2 else i[0] - h), int(i[1] if i[1] < w // 2 else i[1] - w))
imgs = {}
for x in man:
    a = imagecodecs.jpegxr_decode(open(os.path.join(d, x["file"] + ".jxr"), "rb").read())[..., :3]
    if "--png" in sys.argv or "--collage" in sys.argv: Image.fromarray(a).save(os.path.join(d, x["file"] + ".png"))
    l = luma(a); s = sharp(l); H = s.shape[0]
    imgs[x["file"]] = {"scene": x["scene"] or "-", "state": x["state"], "luma": l, "sharp": float(s.mean()), "ground": float(s[int(H * 0.6):].mean()), "rgb": a}
scenes = list(dict.fromkeys(v["scene"] for v in imgs.values()))
arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
REF = arg("--ref"); CROP = arg("--crop")
for sc in scenes:
    if REF:
        items = [(f, v) for f, v in imgs.items() if v["scene"] == sc]; states = list(dict.fromkeys(v["state"] for _, v in items)); by = {st: [v for _, v in items if v["state"] == st] for st in states}
        r = by[REF]; rs = np.mean([v["sharp"] for v in r]); rg = np.mean([v["ground"] for v in r])
        nz = np.abs(r[0]["luma"] - r[-1]["luma"]).mean() if len(r) > 1 else float("nan")
        print("== scene %s   ref '%s' sharp %.4f ground %.4f   noise floor (ref first vs last) mean|d| %.2f, sharp spread %.2f%%" % (sc, REF, rs, rg, nz, 100 * (max(v["sharp"] for v in r) - min(v["sharp"] for v in r)) / rs if len(r) > 1 else 0))
        print("   %-26s %9s %9s %9s %8s" % ("state", "sharp", "d sharp", "d ground", "mean|d|"))
        for st in states:
            if st == REF: continue
            m = np.mean([v["sharp"] for v in by[st]]); g = np.mean([v["ground"] for v in by[st]]); dd = np.mean([np.abs(p["luma"] - q["luma"]).mean() for p in by[st] for q in r])
            print("   %-26s %9.4f %+8.1f%% %+8.1f%% %8.2f" % (st, m, 100 * (m - rs) / rs, 100 * (g - rg) / rg, dd))
        if CROP:
            x0, y0, x1, y1 = [int(x) for x in CROP.split(",")]; tiles = []
            for st in states:
                a = by[st][0]["rgb"]; box = a[2 * y0:2 * y1, 2 * x0:2 * x1]; tiles.append((st, Image.fromarray(box).resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.NEAREST)))
            w, h = tiles[0][1].size; cols = 3; rows = -(-len(tiles) // cols); sheet = Image.new("RGB", (w * cols, h * rows), (30, 30, 30))
            from PIL import ImageDraw
            for k, (st, t) in enumerate(tiles):
                sheet.paste(t, ((k % cols) * w, (k // cols) * h)); ImageDraw.Draw(sheet).text(((k % cols) * w + 6, (k // cols) * h + 4), st, fill=(255, 255, 0))
            sheet.save(os.path.join(d, "crop_%s.png" % sc)); print("   crop sheet ->", os.path.join(d, "crop_%s.png" % sc), sheet.size)
        continue
    items = [(f, v) for f, v in imgs.items() if v["scene"] == sc]; states = list(dict.fromkeys(v["state"] for _, v in items))
    print("== scene %s" % sc)
    by = {st: [v for _, v in items if v["state"] == st] for st in states}
    for st in states: print("   %-26s n=%d  sharp %s  ground %s" % (st, len(by[st]), " ".join("%.4f" % v["sharp"] for v in by[st]), " ".join("%.4f" % v["ground"] for v in by[st])))
    for st in states:                                                   # noise floor: same state, different shots
        if len(by[st]) > 1:
            ds = [np.abs(p["luma"] - q["luma"]).mean() for p, q in itertools.combinations(by[st], 2)]
            print("   noise  %-24s mean|d| %.2f   sharp spread %.1f%%" % (st, np.mean(ds), 100 * (max(v["sharp"] for v in by[st]) - min(v["sharp"] for v in by[st])) / np.mean([v["sharp"] for v in by[st]])))
    for s1, s2 in itertools.combinations(states, 2):
        m1, m2 = np.mean([v["sharp"] for v in by[s1]]), np.mean([v["sharp"] for v in by[s2]]); g1, g2 = np.mean([v["ground"] for v in by[s1]]), np.mean([v["ground"] for v in by[s2]])
        dd = np.mean([np.abs(p["luma"] - q["luma"]).mean() for p in by[s1] for q in by[s2]]); sh = shift(by[s1][0]["luma"], by[s2][0]["luma"])
        print("   %s  vs  %s:  sharp %+.1f%%  ground %+.1f%%  mean|d| %.2f  shift %s" % (s1, s2, 100 * (m2 - m1) / m1, 100 * (g2 - g1) / g1, dd, sh))
    if "--collage" in sys.argv:
        W, H = 640, 360; firsts = [by[st][0] for st in states][:3]; c = Image.new("RGB", (W * len(firsts), H))
        for j, v in enumerate(firsts): c.paste(Image.fromarray(v["rgb"]).resize((W, H), Image.LANCZOS), (j * W, 0))
        c.save(os.path.join(d, "collage_%s.png" % sc))
