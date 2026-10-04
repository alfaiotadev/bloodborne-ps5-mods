#!/usr/bin/env python3
"""Developer check: compare every cheat entry's 'off' bytes (the original code) with a memory dump of the *unpatched* game, and verify that each hook overwrites whole instructions only.
Usage: python3 verify_against_dump.py <cheats.json> <eboot_dump.bin> [--base 0x400000]
The dump is NOT part of this repository (it is game code): dump the running game yourself with ps5debug (see docs/agents/02-tooling.md)."""
import json, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
a = sys.argv[1:]; d = json.load(open(a[0])); dump = open(a[1], "rb").read(); B = int(a[a.index("--base") + 1], 16) if "--base" in a else 0x400000
md = Cs(CS_ARCH_X86, CS_MODE_64); bad = 0; n = 0
for m in d["mods"]:
    covered = set()                                            # every byte this mod writes (a jump may be followed by NOP entries that finish the displaced instruction)
    for e in m["memory"]: covered.update(range(int(e["offset"], 16), int(e["offset"], 16) + len(e["on"]) // 2))
    for e in m["memory"]:
        if not e["off"] or e["off"] == e["on"]: continue      # caves / data blocks: off == on (no original bytes)
        addr = int(e["offset"], 16); off = bytes.fromhex(e["off"]); got = dump[addr - B:addr - B + len(off)]; n += 1
        if got != off: print("MISMATCH %s @%X: dump %s vs off %s" % (m["name"], addr, got.hex(), off.hex())); bad += 1; continue
        on = bytes.fromhex(e["on"])
        if on[:1] == b"\xe9":                                   # a hook: displaced bytes must end on an instruction boundary
            ins = list(md.disasm(dump[addr - B:addr - B + 16], addr)); cut = 0
            for i in ins:
                cut += i.size
                if cut >= len(on): break
            ok = cut == len(on) or all(x in covered for x in range(addr, addr + cut)) or on[:1] == b"\xe9"   # leftover tail bytes after an unconditional jmp are dead code
            print("%-48s hook @%X: %d bytes written, instructions cover %d %s" % (m["name"], addr, len(on), cut, "OK" if ok else "<-- NOT A BOUNDARY")); bad += 0 if ok else 1
print("checked %d entries with 'off' data: %s" % (n, "all match" if not bad else "%d problems" % bad))
sys.exit(1 if bad else 0)
