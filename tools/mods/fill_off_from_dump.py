#!/usr/bin/env python3
"""Developer tool: fill every cheat entry's 'off' value with the ORIGINAL bytes taken from a dump of the unpatched running game, so that switching a mod off at runtime
restores the original code/data (many community cheat files leave 'off' empty or use placeholder zeros).
Usage: python3 fill_off_from_dump.py data/base_mods.json <unpatched_eboot_dump.bin> [--base 0x400000]
The dump is not part of this repository (it is game code); produce it yourself with ps5debug (docs/agents/02-tooling.md)."""
import json, sys
a = sys.argv[1:]; d = json.load(open(a[0])); dump = open(a[1], "rb").read(); B = int(a[a.index("--base") + 1], 16) if "--base" in a else 0x400000
n = changed = 0
for m in d["mods"]:
    for e in m["memory"]:
        addr = int(e["offset"], 16); orig = dump[addr - B:addr - B + len(e["on"]) // 2].hex(); n += 1
        if e["off"] != orig: e["off"] = orig; changed += 1
json.dump(d, open(a[0], "w"), indent=1); print("filled %d entries (%d changed)" % (n, changed))
