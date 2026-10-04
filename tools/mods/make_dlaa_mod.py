#!/usr/bin/env python3
"""DLAA threshold mod: makes Bloodborne's game-side DLAA anti-aliasing pass use a higher edge threshold (default 0.3 instead of 0.1) -> noticeably
sharper image (+1.7..3.2 % measured sharpness) while still anti-aliasing; a community favourite in our blink tests.

How it works: the game's AA pass object (vtable 0x56e7980) copies the scene's AA parameters every frame in the function at 0x12596f0
(`this` = rdi, scene params = rsi).  The DLAA threshold is copied by
    0x125970f  vmovss xmm0, [rsi+0x18]      (c5 fa 10 46 18, 5 bytes)
    0x1259714  vmovss [rdi+0x28], xmm0
We replace the 5-byte load with `jmp cave`; the cave loads a constant instead and jumps back to 0x1259714.  Heap objects move every run, so a static data patch is
impossible; this code patch is static.  Order when applying: constant + cave first, hook last (restore in reverse).

Usage: python3 make_dlaa_mod.py [--threshold 0.3]  -> prints the cheat mod JSON"""
import json, struct, sys
from caves import rip, hook5
CAVE, CONST = 0x54A1300, 0x54A1340
HOOK, BACK, ORIG = 0x125970F, 0x1259714, bytes.fromhex("c5fa104618")
def build(threshold=0.3):
    cave = b"\xc5\xfa\x10\x05" + rip(CAVE, 8, CONST) + b"\xe9" + rip(CAVE + 8, 5, BACK)      # vmovss xmm0,[rip+CONST] ; jmp BACK
    return {"name": "DLAA threshold %.2g (sharper anti-aliasing)" % threshold, "type": "checkbox", "enabled": True, "memory": [
        {"offset": "%08X" % CONST, "on": struct.pack("<f", threshold).hex(), "off": "", "absolute": True},
        {"offset": "%08X" % CAVE, "on": cave.hex(), "off": "", "absolute": True},
        {"offset": "%08X" % HOOK, "on": hook5(HOOK, CAVE).hex(), "off": ORIG.hex(), "absolute": True}]}
if __name__ == "__main__":
    t = float(sys.argv[sys.argv.index("--threshold") + 1]) if "--threshold" in sys.argv else 0.3
    print(json.dumps(build(t), indent=1))
